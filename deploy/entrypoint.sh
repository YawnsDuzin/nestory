#!/usr/bin/env bash
# Entrypoint for the test/prod app container.
# Runs migrations and seed, then exec uvicorn.
set -euo pipefail

echo "[entrypoint] Waiting for Postgres..."
until pg_isready -h "${POSTGRES_HOST:-postgres}" -U "${POSTGRES_USER:-nestory}" >/dev/null 2>&1; do
  sleep 1
done

echo "[entrypoint] Running Alembic migrations..."
uv run alembic upgrade head

echo "[entrypoint] Seeding regions (idempotent)..."
uv run python -m scripts.seed_regions

echo "[entrypoint] Starting Uvicorn..."
exec uv run uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 2 \
  --proxy-headers \
  --forwarded-allow-ips=*
