#!/usr/bin/env bash
# Build the frontend static export, mirror it into backend/static/, and run the
# FastAPI dev server on port 8000.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Building frontend static export"
npm --prefix "${REPO_ROOT}/frontend" run build

echo "==> Mirroring frontend/out/ into backend/static/"
mkdir -p "${REPO_ROOT}/backend/static"
if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude=".gitkeep" "${REPO_ROOT}/frontend/out/" "${REPO_ROOT}/backend/static/"
else
    find "${REPO_ROOT}/backend/static" -mindepth 1 ! -name ".gitkeep" -exec rm -rf {} +
    cp -R "${REPO_ROOT}/frontend/out/." "${REPO_ROOT}/backend/static/"
fi

echo "==> Starting FastAPI dev server on http://localhost:8000"
exec uv run --directory "${REPO_ROOT}/backend" --extra dev uvicorn app.main:app --host 0.0.0.0 --port 8000
