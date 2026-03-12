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

public_ip="$(resolve_ipv4 "${JITSI_MEDIA_PUBLIC_HOSTNAME}" || true)"
if [ -z "${public_ip}" ]; then
  echo "Could not resolve IPv4 address for ${JITSI_MEDIA_PUBLIC_HOSTNAME}" >&2
  exit 1
fi

export JVB_ADVERTISE_IPS="${public_ip}#${JITSI_JVB_UDP_PORT:-10000}"
echo "Advertising JVB media on ${JVB_ADVERTISE_IPS}" >&2

exec /init
