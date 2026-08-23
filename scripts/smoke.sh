#!/usr/bin/env bash
# End-to-end smoke gate: fresh DB, boot, health, static page, watchlist, SSE frame.
# Exits non-zero on the first failed assertion.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"

TMP_DB="$(mktemp -u /tmp/finally-smoke-XXXXXX.db)"
export FINALLY_DB_PATH="${TMP_DB}"

SERVER_PID=""

cleanup() {
    if [ -n "${SERVER_PID}" ] && kill -0 "${SERVER_PID}" 2>/dev/null; then
        kill "${SERVER_PID}" 2>/dev/null || true
        wait "${SERVER_PID}" 2>/dev/null || true
    fi
    rm -f "${TMP_DB}" "${TMP_DB}-wal" "${TMP_DB}-shm"
}
trap cleanup EXIT

if [ ! -f "${BACKEND_DIR}/static/index.html" ]; then
    echo "==> Building frontend static export (backend/static/index.html not found)"
    npm --prefix "${REPO_ROOT}/frontend" run build
    mkdir -p "${BACKEND_DIR}/static"
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --delete --exclude=".gitkeep" "${REPO_ROOT}/frontend/out/" "${BACKEND_DIR}/static/"
    else
        find "${BACKEND_DIR}/static" -mindepth 1 ! -name ".gitkeep" -exec rm -rf {} +
        cp -R "${REPO_ROOT}/frontend/out/." "${BACKEND_DIR}/static/"
    fi
else
    echo "==> backend/static/index.html already exists, skipping frontend build"
fi

echo "==> Starting uvicorn (FINALLY_DB_PATH=${TMP_DB})"
uv run --directory "${BACKEND_DIR}" --extra dev uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    >/tmp/finally-smoke-server.log 2>&1 &
SERVER_PID=$!

echo "==> Waiting for /api/health"
READY=0
for _ in $(seq 1 40); do
    if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 0.5
done
if [ "${READY}" -ne 1 ]; then
    echo "FAIL: server did not answer /api/health within 20s"
    cat /tmp/finally-smoke-server.log || true
    exit 1
fi

echo "==> Assert: GET /api/health returns ok status and simulator market_source"
HEALTH_BODY="$(curl -sf http://127.0.0.1:8000/api/health)"
if [ "${HEALTH_BODY}" != '{"status":"ok","market_source":"simulator"}' ]; then
    echo "FAIL: unexpected /api/health body: ${HEALTH_BODY}"
    exit 1
fi

echo "==> Assert: fresh database has six tables, one seeded user, ten watchlist rows"
uv run --directory "${BACKEND_DIR}" --extra dev python -c "
import sqlite3
import sys

conn = sqlite3.connect('${TMP_DB}')
tables = {r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")}
expected = {'users_profile', 'watchlist', 'positions', 'trades', 'portfolio_snapshots', 'chat_messages'}
if tables != expected:
    print(f'FAIL: unexpected table set: {tables}')
    sys.exit(1)

row = conn.execute('SELECT COUNT(*), MIN(cash_balance), MAX(cash_balance) FROM users_profile').fetchone()
if row[0] != 1 or row[1] != 10000.0:
    print(f'FAIL: users_profile not seeded correctly: {row}')
    sys.exit(1)

count = conn.execute('SELECT COUNT(*) FROM watchlist').fetchone()[0]
if count != 10:
    print(f'FAIL: expected 10 watchlist rows, got {count}')
    sys.exit(1)

print('OK: database schema and seed data verified')
"

echo "==> Assert: GET / returns HTML containing terminal-root"
INDEX_BODY="$(curl -sf http://127.0.0.1:8000/)"
if ! echo "${INDEX_BODY}" | grep -q "terminal-root"; then
    echo "FAIL: GET / did not contain terminal-root"
    exit 1
fi

echo "==> Assert: GET /api/watchlist returns ten entries"
WATCHLIST_BODY="$(curl -sf http://127.0.0.1:8000/api/watchlist)"
uv run --directory "${BACKEND_DIR}" --extra dev python -c "
import json
import sys

data = json.loads('''${WATCHLIST_BODY}''')
if len(data) != 10:
    print(f'FAIL: expected 10 watchlist entries, got {len(data)}')
    sys.exit(1)
print('OK: watchlist has 10 entries')
"

echo "==> Assert: SSE stream emits a data: frame with every seeded symbol"
SSE_OUTPUT="$(curl -sN --max-time 4 http://127.0.0.1:8000/api/stream/prices || true)"
DATA_LINE="$(echo "${SSE_OUTPUT}" | grep '^data:' | head -1 || true)"
if [ -z "${DATA_LINE}" ]; then
    echo "FAIL: no data: frame received from SSE stream"
    exit 1
fi
if ! echo "${DATA_LINE}" | grep -q '"direction"'; then
    echo "FAIL: SSE data frame missing 'direction' field"
    exit 1
fi
for TICKER in AAPL GOOGL MSFT AMZN TSLA NVDA META JPM V NFLX; do
    if ! echo "${DATA_LINE}" | grep -q "\"${TICKER}\""; then
        echo "FAIL: SSE data frame missing ticker ${TICKER}"
        exit 1
    fi
done

echo "==> All smoke assertions passed"
