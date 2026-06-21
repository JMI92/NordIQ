#!/bin/sh
# API container entrypoint — runs Alembic migrations then starts uvicorn.
set -e

echo "[entrypoint] Running Alembic migrations…"
alembic upgrade head

echo "[entrypoint] Starting uvicorn…"
exec uvicorn uusio.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-1}" \
    --log-level "${LOG_LEVEL:-info}"
