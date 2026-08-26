# syntax=docker/dockerfile:1

# ---- Stage 1: build the Next.js static export ----
FROM node:20-slim AS frontend-builder
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ---- Stage 2: build the Python backend venv ----
FROM python:3.12-slim AS backend-builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project
COPY backend/ .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked
# Frontend export lands at /app/static: app.frontend() in backend/app/main.py
# resolves Path(__file__).resolve().parents[1] / "static" from /app/app/main.py.
# Do not rename or relocate this directory.
COPY --from=frontend-builder /fe/out ./static

# ---- Stage 3: minimal runtime (SAME base tag as backend-builder to avoid a
#      GLIBC mismatch across stages when numpy is imported) ----
FROM python:3.12-slim
WORKDIR /app
COPY --from=backend-builder /app /app
ENV PATH="/app/.venv/bin:$PATH"

# Load-bearing, not optional convenience: resolve_db_path()'s fallback computes
# Path(__file__).resolve().parents[3], which from /app/app/db/connection.py
# resolves to the filesystem root. Without this, the container silently writes
# its database to /db/finally.db in the throwaway writable layer instead of the
# bind-mounted host directory, and every restart resets the portfolio.
ENV FINALLY_DB_PATH=/app/db/finally.db

EXPOSE 8000

# python:3.12-slim has no curl/wget; use the interpreter already on PATH.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health', timeout=2).status==200 else 1)"

# --timeout-graceful-shutdown is required, not cosmetic: uvicorn's default is
# unbounded, and the SSE generator in backend/app/market/stream.py only breaks
# its loop on client disconnect, so an open stream would make shutdown hang.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "10"]
