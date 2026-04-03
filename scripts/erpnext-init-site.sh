#!/usr/bin/env bash

set -euo pipefail

required_vars=(
  ERPNEXT_SITE_NAME
  ERPNEXT_DB_ROOT_PASSWORD
  ERPNEXT_ADMIN_PASSWORD
  ERPNEXT_BASE_URL
)

for name in "${required_vars[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "missing required environment variable: ${name}" >&2
    exit 1
  fi
done

sites_dir="/home/frappe/frappe-bench/sites"
site_config="${sites_dir}/${ERPNEXT_SITE_NAME}/site_config.json"

if [[ -f "${site_config}" ]]; then
  echo "ERPNext site ${ERPNEXT_SITE_NAME} already exists; skipping bootstrap."
  exit 0
fi

echo "Creating ERPNext site ${ERPNEXT_SITE_NAME}."
bench new-site \
  --mariadb-user-host-login-scope=% \
  --db-root-password "${ERPNEXT_DB_ROOT_PASSWORD}" \
  --admin-password "${ERPNEXT_ADMIN_PASSWORD}" \
  --install-app erpnext \
  "${ERPNEXT_SITE_NAME}"

bench use "${ERPNEXT_SITE_NAME}"
bench --site "${ERPNEXT_SITE_NAME}" set-config host_name "${ERPNEXT_BASE_URL}"

echo "ERPNext site ${ERPNEXT_SITE_NAME} created."
echo "Update the owner email to ${ERPNEXT_OWNER_EMAIL:-Administrator} after first login."
