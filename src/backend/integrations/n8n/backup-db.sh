#!/bin/sh
set -eu
umask 077

pending=$(mktemp /backups/.n8n_XXXXXXXX)
trap 'rm -f "$pending"' EXIT
archive="/backups/n8n_$(date -u +%Y%m%dT%H%M%SZ)_${pending##*_}.dump"

pg_dump -U postgres -d n8n --format=custom --file="$pending"
pg_restore --list "$pending" >/dev/null
mv "$pending" "$archive"
printf '%s\n' "$archive"
