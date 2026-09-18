#!/bin/sh
# Periodic pg_dump with rotation. Runs inside the `backup` container.
set -u
INTERVAL="${BACKUP_INTERVAL_SECONDS:-900}"
KEEP="${BACKUP_KEEP:-96}"
mkdir -p /backups
while true; do
  ts="$(date +%Y-%m-%d_%H-%M-%S)"
  out="/backups/${PGDATABASE}_${ts}.sql.gz"
  if pg_dump --no-owner --no-privileges "$PGDATABASE" | gzip > "$out.tmp"; then
    mv "$out.tmp" "$out"
    echo "[backup] wrote $out"
  else
    rm -f "$out.tmp"
    echo "[backup] pg_dump failed" >&2
  fi
  # rotation: keep the newest $KEEP files
  ls -1t /backups/*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
  sleep "$INTERVAL"
done
