#!/bin/sh

set -eu

resolve_ipv4() {
  host="$1"

  if command -v getent >/dev/null 2>&1; then
    ip="$(getent ahostsv4 "$host" 2>/dev/null | awk 'NR == 1 { print $1; exit }' || true)"
    if [ -n "$ip" ]; then
      printf '%s\n' "$ip"
      return 0
    fi
  fi

  if command -v nslookup >/dev/null 2>&1; then
    ip="$(nslookup "$host" 2>/dev/null | awk '/^Address: / { print $2; exit }' || true)"
    if [ -n "$ip" ]; then
      printf '%s\n' "$ip"
      return 0
    fi
  fi

  if command -v host >/dev/null 2>&1; then
    ip="$(host -t A "$host" 2>/dev/null | awk '/ has address / { print $4; exit }' || true)"
    if [ -n "$ip" ]; then
      printf '%s\n' "$ip"
      return 0
    fi
  fi

  if command -v dig >/dev/null 2>&1; then
    ip="$(dig +short A "$host" 2>/dev/null | awk 'NF { print; exit }' || true)"
    if [ -n "$ip" ]; then
      printf '%s\n' "$ip"
      return 0
    fi
  fi

  return 1
}

if [ -z "${JITSI_MEDIA_PUBLIC_HOSTNAME:-}" ]; then
  echo "JITSI_MEDIA_PUBLIC_HOSTNAME is required" >&2
  exit 1
fi

if [ "${JITSI_TURN_MIN_PORT:-20000}" -gt "${JITSI_TURN_MAX_PORT:-20100}" ]; then
  echo "JITSI_TURN_MIN_PORT must be less than or equal to JITSI_TURN_MAX_PORT" >&2
  exit 1
fi

public_ip="$(resolve_ipv4 "${JITSI_MEDIA_PUBLIC_HOSTNAME}" || true)"
if [ -z "${public_ip}" ]; then
  echo "Could not resolve IPv4 address for ${JITSI_MEDIA_PUBLIC_HOSTNAME}" >&2
  exit 1
fi

sed \
  -e "s|__JITSI_MEDIA_PUBLIC_HOSTNAME__|${JITSI_MEDIA_PUBLIC_HOSTNAME}|g" \
  -e "s|__JITSI_MEDIA_PUBLIC_IP__|${public_ip}|g" \
  -e "s|__JITSI_TURN_CREDENTIALS__|${JITSI_TURN_CREDENTIALS}|g" \
  -e "s|__JITSI_TURN_PORT__|${JITSI_TURN_PORT:-3478}|g" \
  -e "s|__JITSI_TURN_MIN_PORT__|${JITSI_TURN_MIN_PORT:-20000}|g" \
  -e "s|__JITSI_TURN_MAX_PORT__|${JITSI_TURN_MAX_PORT:-20100}|g" \
  /config/turnserver.conf.template > /var/lib/coturn/turnserver.conf

echo "Starting coturn with external-ip ${public_ip}" >&2
exec turnserver -c /var/lib/coturn/turnserver.conf
