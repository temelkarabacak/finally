#!/usr/bin/env bash
# Stop and remove the FinAlly container. The db/ directory is left untouched.
set -euo pipefail

CONTAINER=finally

if [ -n "$(docker ps -aq -f "name=^${CONTAINER}$")" ]; then
  docker rm -f "$CONTAINER" >/dev/null
  echo "Stopped and removed $CONTAINER (data in db/ kept)."
else
  echo "$CONTAINER is not running."
fi
