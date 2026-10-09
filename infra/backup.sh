#!/bin/sh
set -eu

backup_dir="${BACKUP_DIR:-/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
output="$backup_dir/lente-${timestamp}.dump"

pg_dump --format=custom --no-owner --no-privileges --file="$output" "$DATABASE_URL"
sha256sum "$output" > "${output}.sha256"
find "$backup_dir" -type f -name 'lente-*.dump*' -mtime "+${BACKUP_RETENTION_DAYS:-14}" -delete
printf '%s\n' "$output"

