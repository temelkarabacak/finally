#!/usr/bin/env bash
# One-command stop: bounded docker stop only. Never removes the container or
# the db/ bind mount -- stopping must never destroy the user's portfolio data.
# Idempotent -- safe to run repeatedly, always exits 0.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

NAME="finally-app"

echo "==> Checking Docker is running"
if ! docker info >/dev/null 2>&1; then
    echo "Docker does not appear to be running."
    echo "Please start Docker Desktop (or the Docker daemon) and try again."
    exit 1
fi

if STATE="$(docker inspect -f '{{.State.Running}}' "${NAME}" 2>/dev/null)"; then
    STATE="$(printf '%s' "${STATE}" | tr -d '[:space:]')"
else
    STATE="absent"
fi
case "${STATE}" in
    true)
        echo "==> Stopping ${NAME} (timeout 15s)"
        docker stop --timeout 15 "${NAME}" >/dev/null
        echo "finally has been stopped. Your data in ${REPO_ROOT}/db is preserved."
        ;;
    *)
        echo "finally is not running."
        ;;
esac
