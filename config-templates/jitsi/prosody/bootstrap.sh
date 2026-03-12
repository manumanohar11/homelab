#!/bin/sh

set -eu

cert_dir="/config/certs"

generate_self_signed_cert() {
  domain="$1"
  crt_path="${cert_dir}/${domain}.crt"
  key_path="${cert_dir}/${domain}.key"

  if [ -s "${crt_path}" ] && [ -s "${key_path}" ]; then
    return 0
  fi

  tmp_dir="$(mktemp -d)"
  conf_path="${tmp_dir}/openssl.cnf"

  cat >"${conf_path}" <<EOF
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = ${domain}

[v3_req]
subjectAltName = DNS:${domain}
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
EOF

  openssl req \
    -x509 \
    -newkey rsa:2048 \
    -sha256 \
    -days 3650 \
    -nodes \
    -keyout "${key_path}" \
    -out "${crt_path}" \
    -config "${conf_path}" \
    >/dev/null 2>&1

  chmod 600 "${key_path}"
  rm -rf "${tmp_dir}"

  echo "Generated self-signed XMPP certificate for ${domain}" >&2
}

mkdir -p "${cert_dir}"

xmpp_domain="${XMPP_DOMAIN:-meet.jitsi}"
auth_domain="${XMPP_AUTH_DOMAIN:-auth.${xmpp_domain}}"

generate_self_signed_cert "${xmpp_domain}"
generate_self_signed_cert "${auth_domain}"

exec /init
