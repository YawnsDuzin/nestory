#!/usr/bin/env bash
# Entrypoint for the test/prod app container.
# Runs migrations and seed, then exec uvicorn.
# Uses the pre-installed venv directly to avoid `uv run` re-syncing dev deps.
set -euo pipefail

VENV=/app/.venv

echo "[entrypoint] Waiting for Postgres..."
until pg_isready -h "${POSTGRES_HOST:-postgres}" -U "${POSTGRES_USER:-nestory}" >/dev/null 2>&1; do
  sleep 1
done

echo "[entrypoint] Running Alembic migrations..."
"$VENV/bin/alembic" upgrade head

echo "[entrypoint] Seeding regions (idempotent)..."
"$VENV/bin/python" -m scripts.seed_regions

echo "[entrypoint] Starting Uvicorn..."
exec "$VENV/bin/uvicorn" app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 2 \
  --proxy-headers \
  --forwarded-allow-ips=*
