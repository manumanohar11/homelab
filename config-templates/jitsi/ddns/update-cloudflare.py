#!/usr/bin/env python3

from __future__ import annotations

import ipaddress
import json
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API_BASE = "https://api.cloudflare.com/client/v4"
COMMENT = "Managed by media-stack jitsi-ddns"
REQUEST_TIMEOUT_SECONDS = 20
STATUS_PATH = Path("/tmp/jitsi-ddns-status.json")
TRACE_URL = "https://one.one.one.one/cdn-cgi/trace"
UPDATE_INTERVAL_SECONDS = 300
USER_AGENT = "media-stack-jitsi-ddns/1.0"
STOP_EVENT = threading.Event()


def log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S%z")
    print(f"[{timestamp}] {message}", flush=True)


def load_status() -> dict[str, Any]:
    if not STATUS_PATH.exists():
        return {}

    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_status(**updates: Any) -> None:
    status = load_status()
    status.update(updates)
    STATUS_PATH.write_text(
        json.dumps(status, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def request_json(method: str, url: str, *, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Cloudflare API {method} {url} failed: {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cloudflare API {method} {url} failed: {exc.reason}") from exc

    data = json.loads(response_body)
    if not data.get("success"):
        errors = ", ".join(item.get("message", "unknown error") for item in data.get("errors", []))
        raise RuntimeError(f"Cloudflare API {method} {url} returned success=false: {errors or 'unknown error'}")
    return data


def detect_public_ipv4() -> str:
    request = urllib.request.Request(TRACE_URL, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"failed to detect public IPv4 address: {exc.reason}") from exc

    for line in body.splitlines():
        if not line.startswith("ip="):
            continue

        candidate = line.split("=", 1)[1].strip()
        ipaddress.IPv4Address(candidate)
        return candidate

    raise RuntimeError("failed to detect public IPv4 address from Cloudflare trace")


def get_zone_id(token: str, zone_name: str) -> str:
    query = urllib.parse.urlencode({"name": zone_name, "status": "active", "per_page": 1})
    data = request_json("GET", f"{API_BASE}/zones?{query}", token=token)
    result = data.get("result", [])
    if not result:
        raise RuntimeError(f"Cloudflare zone '{zone_name}' not found")
    return result[0]["id"]


def get_record(token: str, zone_id: str, fqdn: str) -> dict[str, Any] | None:
    query = urllib.parse.urlencode({"type": "A", "name": fqdn, "per_page": 100})
    data = request_json("GET", f"{API_BASE}/zones/{zone_id}/dns_records?{query}", token=token)
    result = data.get("result", [])
    if len(result) > 1:
        raise RuntimeError(f"multiple A records already exist for '{fqdn}'")
    return result[0] if result else None


def ensure_record(token: str, zone_id: str, fqdn: str, ipv4_address: str) -> str:
    payload = {
        "comment": COMMENT,
        "content": ipv4_address,
        "name": fqdn,
        "proxied": False,
        "ttl": 1,
        "type": "A",
    }
    record = get_record(token, zone_id, fqdn)

    if record is None:
        request_json("POST", f"{API_BASE}/zones/{zone_id}/dns_records", token=token, payload=payload)
        return "created"

    unchanged = (
        record.get("content") == ipv4_address
        and record.get("proxied") is False
        and int(record.get("ttl", 1)) == 1
        and record.get("comment", "") == COMMENT
    )
    if unchanged:
        return "unchanged"

    request_json(
        "PUT",
        f"{API_BASE}/zones/{zone_id}/dns_records/{record['id']}",
        token=token,
        payload=payload,
    )
    return "updated"


def env_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    raise RuntimeError(f"{name} is required")


def handle_signal(signum: int, _frame: Any) -> None:
    log(f"received signal {signum}, stopping")
    STOP_EVENT.set()


def update_once(*, token: str, zone_name: str, fqdn: str) -> None:
    ipv4_address = detect_public_ipv4()
    zone_id = get_zone_id(token, zone_name)
    action = ensure_record(token, zone_id, fqdn, ipv4_address)
    write_status(
        fqdn=fqdn,
        last_action=action,
        last_attempt=time.time(),
        last_error="",
        last_ipv4=ipv4_address,
        last_success=time.time(),
        zone=zone_name,
    )
    log(f"{action} Cloudflare A record {fqdn} -> {ipv4_address}")


def main() -> int:
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, handle_signal)

    try:
        zone_name = env_required("DOMAIN_NAME")
        fqdn = env_required("JITSI_MEDIA_PUBLIC_HOSTNAME")
        token = env_required("JITSI_CLOUDFLARE_API_TOKEN")
    except RuntimeError as exc:
        log(str(exc))
        return 1

    while not STOP_EVENT.is_set():
        try:
            update_once(token=token, zone_name=zone_name, fqdn=fqdn)
        except Exception as exc:  # noqa: BLE001
            write_status(last_attempt=time.time(), last_error=str(exc))
            log(f"DDNS update failed: {exc}")

        STOP_EVENT.wait(UPDATE_INTERVAL_SECONDS)

    return 0


if __name__ == "__main__":
    sys.exit(main())
