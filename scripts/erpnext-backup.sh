#!/usr/bin/env bash

set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

if [[ ! -f .env ]]; then
  echo ".env not found in ${repo_dir}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

retention_days="${ERPNEXT_BACKUP_RETENTION_DAYS:-14}"
sites_dir="${DOCKER_BASE_DIR}/erpnext/sites"

docker compose -f docker-compose.yml -f docker-compose.apps.yml exec -T erpnext-backend bench --site all backup

if [[ -d "${sites_dir}" ]]; then
  find "${sites_dir}" \
    -type f \
    \( -path "*/private/backups/*" -o -path "*/backups/*" \) \
    -mtime "+${retention_days}" \
    -print \
    -delete
fi
