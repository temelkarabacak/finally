#!/usr/bin/env bash
# Build (if needed) and run the FinAlly container. Safe to run repeatedly.
set -euo pipefail

IMAGE=finally:latest
CONTAINER=finally
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL=http://localhost:8000

if [ "${1:-}" = "--build" ] || [ -z "$(docker images -q "$IMAGE")" ]; then
  echo "Building $IMAGE ..."
  docker build -t "$IMAGE" "$ROOT"
fi

if [ -n "$(docker ps -q -f "name=^${CONTAINER}$")" ]; then
  echo "FinAlly is already running at $URL"
  exit 0
fi

docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

ENV_ARGS=()
if [ -f "$ROOT/.env" ]; then
  ENV_ARGS=(--env-file "$ROOT/.env")
else
  echo "No .env found at $ROOT/.env - starting with simulator market data and no LLM key."
fi

mkdir -p "$ROOT/db"

docker run -d \
  --name "$CONTAINER" \
  -p 8000:8000 \
  -v "$ROOT/db:/app/db" \
  "${ENV_ARGS[@]}" \
  "$IMAGE"

echo "FinAlly is starting at $URL"

if command -v open >/dev/null 2>&1; then
  open "$URL" >/dev/null 2>&1 || true
fi
