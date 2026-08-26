#!/usr/bin/env bash
# One-command start: builds the finally image if needed, runs the container
# with the db/ bind mount, and waits for it to become healthy.
# Idempotent -- safe to run repeatedly. Exits non-zero only on genuine failure.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

IMAGE="finally"
NAME="finally-app"
HOST_PORT="8000"

echo "==> Checking Docker is running"
if ! docker info >/dev/null 2>&1; then
    echo "Docker does not appear to be running."
    echo "Please start Docker Desktop (or the Docker daemon) and try again."
    exit 1
fi

if ! docker image inspect "${IMAGE}" >/dev/null 2>&1 || [ "${1:-}" = "--build" ]; then
    echo "==> Building image ${IMAGE}"
    docker build -t "${IMAGE}" "${REPO_ROOT}"
else
    echo "==> Image ${IMAGE} already built, skipping build (pass --build to force a rebuild)"
fi

ENV_ARGS=()
if [ -f "${REPO_ROOT}/.env" ]; then
    ENV_ARGS+=(--env-file "${REPO_ROOT}/.env")
else
    echo "==> No .env file found -- AI chat will be unavailable without OPENROUTER_API_KEY (prices and trading still work)"
fi

mkdir -p "${REPO_ROOT}/db"

if STATE="$(docker inspect -f '{{.State.Running}}' "${NAME}" 2>/dev/null)"; then
    STATE="$(printf '%s' "${STATE}" | tr -d '[:space:]')"
else
    STATE="absent"
fi
case "${STATE}" in
    true)
        echo "finally is already running at http://localhost:${HOST_PORT}"
        exit 0
        ;;
    false)
        echo "==> Starting existing container ${NAME}"
        docker start "${NAME}" >/dev/null
        ;;
    absent)
        echo "==> Running new container ${NAME}"
        docker run -d --name "${NAME}" \
            -v "${REPO_ROOT}/db:/app/db" \
            -p "${HOST_PORT}:8000" \
            --stop-timeout 15 \
            "${ENV_ARGS[@]}" \
            "${IMAGE}" >/dev/null
        ;;
esac

echo "==> Waiting for /api/health"
READY=0
for _ in $(seq 1 40); do
    if curl -sf "http://127.0.0.1:${HOST_PORT}/api/health" >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 0.5
done
if [ "${READY}" -ne 1 ]; then
    echo "FAIL: server did not answer /api/health within 20s"
    docker logs --tail 20 "${NAME}" || true
    exit 1
fi

echo "Open http://localhost:${HOST_PORT}"

if command -v open >/dev/null 2>&1; then
    open "http://localhost:${HOST_PORT}" 2>/dev/null || true
fi
