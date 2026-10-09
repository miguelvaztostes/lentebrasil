#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  printf 'Uso: %s /backups/lente-AAAAMMDDTHHMMSSZ.dump\n' "$0" >&2
  exit 2
fi

dump_file="$1"
test -f "$dump_file"
test -f "${dump_file}.sha256"
(cd "$(dirname "$dump_file")" && sha256sum -c "$(basename "${dump_file}.sha256")")
pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$DATABASE_URL" "$dump_file"

