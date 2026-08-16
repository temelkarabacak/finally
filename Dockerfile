# syntax=docker/dockerfile:1

# Stage 1 — build the Next.js static export.
FROM node:24-slim AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2 — FastAPI backend serving the API and the exported frontend.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

# The backend lives at /app/backend so that app/db/connection.py resolves its
# default database path to /app/db/finally.db, which is the volume mount target.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/backend/.venv/bin:$PATH" \
    FINALLY_DB_PATH=/app/db/finally.db

WORKDIR /app/backend

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-install-project

COPY backend/ ./
RUN uv sync --frozen

COPY --from=frontend /frontend/out ./static

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
