#!/usr/bin/env bash
# pg_dump 일배치 백업. systemd가 매일 03:00 실행.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/mnt/backup/pg}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set}"

mkdir -p "$BACKUP_DIR"
TS="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
FILE="$BACKUP_DIR/nestory-$TS.sql.gz"

pg_dump "$DATABASE_URL" --format=plain --no-owner --no-privileges \
  | gzip -9 > "$FILE"

chmod 600 "$FILE"

find "$BACKUP_DIR" -maxdepth 1 -name "nestory-*.sql.gz" -mtime "+$RETENTION_DAYS" -delete

echo "Backup written: $FILE"
