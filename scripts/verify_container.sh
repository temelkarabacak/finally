#!/usr/bin/env bash
# Repeatable DEPLOY-01/DEPLOY-02 gate: build the image, run it, assert the app
# surface, assert bind-mount persistence across stop/start, and assert bounded
# shutdown with a live SSE connection open.
# Exits non-zero on the first failed assertion.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

IMAGE="finally"
NAME="finally-verify"
HOST_PORT="8010"

VERIFY_DB_DIR="$(mktemp -d)"
SSE_LOG="$(mktemp)"
SSE_PID=""

cleanup() {
    if [ -n "${SSE_PID}" ] && kill -0 "${SSE_PID}" 2>/dev/null; then
        kill "${SSE_PID}" 2>/dev/null || true
        wait "${SSE_PID}" 2>/dev/null || true
    fi
    if docker inspect "${NAME}" >/dev/null 2>&1; then
        docker stop --timeout 15 "${NAME}" >/dev/null 2>&1 || true
        docker rm "${NAME}" >/dev/null 2>&1 || true
    fi
    rm -rf "${VERIFY_DB_DIR}"
    rm -f "${SSE_LOG}"
}
trap cleanup EXIT

# Idempotent: a leftover finally-verify container from an aborted earlier run
# is bounded-stopped and removed before the fresh run starts, not an error.
if docker inspect "${NAME}" >/dev/null 2>&1; then
    echo "==> Removing leftover ${NAME} container from a previous run"
    docker stop --timeout 15 "${NAME}" >/dev/null 2>&1 || true
    docker rm "${NAME}" >/dev/null 2>&1 || true
fi

echo "==> Building image ${IMAGE}"
docker build -t "${IMAGE}" "${REPO_ROOT}"

echo "==> Starting ${NAME} (host db dir: ${VERIFY_DB_DIR})"
docker run -d --name "${NAME}" \
    -v "${VERIFY_DB_DIR}":/app/db \
    -p "${HOST_PORT}:8000" \
    -e LLM_MOCK=true \
    --stop-timeout 15 \
    "${IMAGE}" >/dev/null

wait_for_health() {
    local ready=0
    for _ in $(seq 1 40); do
        if curl -sf "http://127.0.0.1:${HOST_PORT}/api/health" >/dev/null 2>&1; then
            ready=1
            break
        fi
        sleep 0.5
    done
    if [ "${ready}" -ne 1 ]; then
        echo "FAIL: server did not answer /api/health within 20s"
        docker logs "${NAME}" || true
        exit 1
    fi
}

echo "==> Waiting for /api/health"
wait_for_health

echo "==> Assert: /api/health body"
HEALTH_BODY="$(curl -sf "http://127.0.0.1:${HOST_PORT}/api/health")"
if [ "${HEALTH_BODY}" != '{"status":"ok","market_source":"simulator"}' ]; then
    echo "FAIL: unexpected /api/health body: ${HEALTH_BODY}"
    exit 1
fi

echo "==> Assert: GET / contains terminal-root"
INDEX_BODY="$(curl -sf "http://127.0.0.1:${HOST_PORT}/")"
if ! echo "${INDEX_BODY}" | grep -q "terminal-root"; then
    echo "FAIL: GET / did not contain terminal-root"
    exit 1
fi

echo "==> Assert: GET /api/watchlist returns 10 entries"
WATCHLIST_BODY="$(curl -sf "http://127.0.0.1:${HOST_PORT}/api/watchlist")"
python3 -c "
import json, sys
data = json.loads('''${WATCHLIST_BODY}''')
if len(data) != 10:
    print(f'FAIL: expected 10 watchlist entries, got {len(data)}')
    sys.exit(1)
print('OK: watchlist has 10 entries')
"

echo "==> Assert: SSE stream emits a data: frame with 'direction'"
SSE_OUTPUT="$(curl -sN --max-time 4 "http://127.0.0.1:${HOST_PORT}/api/stream/prices" || true)"
DATA_LINE="$(echo "${SSE_OUTPUT}" | grep '^data:' | head -1 || true)"
if [ -z "${DATA_LINE}" ]; then
    echo "FAIL: no data: frame received from SSE stream"
    exit 1
fi
if ! echo "${DATA_LINE}" | grep -q '"direction"'; then
    echo "FAIL: SSE data frame missing 'direction' field"
    exit 1
fi

echo "==> Assert: bind-mounted host directory contains finally.db"
if [ ! -f "${VERIFY_DB_DIR}/finally.db" ]; then
    echo "FAIL: ${VERIFY_DB_DIR}/finally.db does not exist -- FINALLY_DB_PATH is not routing writes to the bind mount"
    exit 1
fi

echo "==> Executing a buy trade via the API"
TRADE_BODY='{"ticker":"AAPL","quantity":1,"side":"buy"}'
TRADE_RESPONSE="$(curl -sf -X POST "http://127.0.0.1:${HOST_PORT}/api/portfolio/trade" \
    -H 'Content-Type: application/json' -d "${TRADE_BODY}")"
if [ -z "${TRADE_RESPONSE}" ]; then
    echo "FAIL: buy trade request failed"
    exit 1
fi

PORTFOLIO_BEFORE="$(curl -sf "http://127.0.0.1:${HOST_PORT}/api/portfolio")"
BEFORE_LINE="$(python3 -c "
import json
data = json.loads('''${PORTFOLIO_BEFORE}''')
aapl = next((p for p in data['positions'] if p['ticker'] == 'AAPL'), None)
if aapl is None:
    raise SystemExit('FAIL: no AAPL position found after buy')
print(data['cash_balance'], aapl['quantity'])
")"
CASH_BEFORE="$(echo "${BEFORE_LINE}" | cut -d' ' -f1)"
QTY_BEFORE="$(echo "${BEFORE_LINE}" | cut -d' ' -f2)"

echo "==> Opening a background SSE reader to keep a live connection open"
curl -sN --max-time 30 "http://127.0.0.1:${HOST_PORT}/api/stream/prices" >"${SSE_LOG}" 2>&1 &
SSE_PID=$!
sleep 1

echo "==> Stopping ${NAME} with an SSE connection open, timing the shutdown"
STOP_START=$(date +%s)
docker stop --timeout 15 "${NAME}" >/dev/null
STOP_END=$(date +%s)
STOP_ELAPSED=$((STOP_END - STOP_START))
echo "==> docker stop took ${STOP_ELAPSED}s"
if [ "${STOP_ELAPSED}" -ge 20 ]; then
    echo "FAIL: docker stop took ${STOP_ELAPSED}s (>= 20s) -- bounded shutdown is not working"
    exit 1
fi

if [ -n "${SSE_PID}" ] && kill -0 "${SSE_PID}" 2>/dev/null; then
    kill "${SSE_PID}" 2>/dev/null || true
    wait "${SSE_PID}" 2>/dev/null || true
fi
SSE_PID=""

echo "==> Starting ${NAME} again"
docker start "${NAME}" >/dev/null

echo "==> Waiting for /api/health after restart"
wait_for_health

PORTFOLIO_AFTER="$(curl -sf "http://127.0.0.1:${HOST_PORT}/api/portfolio")"
AFTER_LINE="$(python3 -c "
import json
data = json.loads('''${PORTFOLIO_AFTER}''')
aapl = next((p for p in data['positions'] if p['ticker'] == 'AAPL'), None)
if aapl is None:
    raise SystemExit('FAIL: no AAPL position found after restart')
print(data['cash_balance'], aapl['quantity'])
")"
CASH_AFTER="$(echo "${AFTER_LINE}" | cut -d' ' -f1)"
QTY_AFTER="$(echo "${AFTER_LINE}" | cut -d' ' -f2)"

echo "==> Assert: cash_balance and AAPL quantity unchanged across stop/start"
if [ "${CASH_BEFORE}" != "${CASH_AFTER}" ] || [ "${QTY_BEFORE}" != "${QTY_AFTER}" ]; then
    echo "FAIL: portfolio state changed across restart"
    echo "  before: cash=${CASH_BEFORE} qty=${QTY_BEFORE}"
    echo "  after:  cash=${CASH_AFTER} qty=${QTY_AFTER}"
    exit 1
fi

echo "==> All container verification assertions passed"
