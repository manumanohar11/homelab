#!/usr/bin/env python3

from __future__ import annotations

import argparse
import secrets
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
STARTER_TEMPLATE = REPO_ROOT / ".env.example"
BUNDLE_TEMPLATE_DIR = REPO_ROOT / "env" / "bundles"

STARTER_SECRETS = (
    "DB_PASSWORD",
    "DUPLICATI_ENCRYPTION_KEY",
    "HOMARR_SECRET_ENCRYPTION_KEY",
)

BUNDLE_SECRETS = {
    "media": ("BITMAGNET_POSTGRES_PASSWORD",),
    "apps": (
        "JOPLIN_DB_PASSWORD",
        "PAPERLESS_SECRET_KEY",
        "PAPERLESS_DB_PASSWORD",
        "KARAKEEP_NEXTAUTH_SECRET",
        "KARAKEEP_MEILI_MASTER_KEY",
        "DOCMOST_APP_SECRET",
        "DOCMOST_DB_PASSWORD",
    ),
    "ops": ("GRAFANA_ADMIN_PASSWORD",),
    "access": (
        "JITSI_JICOFO_COMPONENT_SECRET",
        "JITSI_JICOFO_AUTH_PASSWORD",
        "JITSI_JVB_AUTH_PASSWORD",
        "JITSI_TURN_CREDENTIALS",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create .env from the starter template and optionally add bundle settings."
    )
    parser.add_argument(
        "--bundle",
        action="append",
        default=[],
        help="Optional bundle to add to .env (media, apps, ops, access). Repeat as needed.",
    )
    return parser.parse_args()


def load_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def assignment_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        return None
    key = line.split("=", 1)[0].strip()
    if not key:
        return None
    return key


def current_keys(lines: list[str]) -> set[str]:
    keys: set[str] = set()
    for line in lines:
        key = assignment_key(line)
        if key is not None:
            keys.add(key)
    return keys


def current_key_indexes(lines: list[str]) -> dict[str, int]:
    indexes: dict[str, int] = {}
    for index, line in enumerate(lines):
        key = assignment_key(line)
        if key is not None:
            indexes[key] = index
    return indexes


def append_missing_bundle_values(lines: list[str], bundle: str) -> list[str]:
    template_path = BUNDLE_TEMPLATE_DIR / f"{bundle}.env.example"
    if not template_path.exists():
        raise FileNotFoundError(f"missing bundle template: {template_path}")

    existing = current_keys(lines)
    additions: list[str] = []

    for line in load_lines(template_path):
        key = assignment_key(line)
        if key is None:
            continue
        if key in existing:
            continue
        additions.append(line)
        existing.add(key)

    if not additions:
        return []

    if lines and lines[-1] != "":
        lines.append("")
    lines.append(f"# Added from env/bundles/{bundle}.env.example")
    lines.extend(additions)
    return additions


def ensure_env_exists() -> bool:
    if ENV_PATH.exists():
        return False
    if not STARTER_TEMPLATE.exists():
        raise FileNotFoundError(f"missing starter template: {STARTER_TEMPLATE}")
    shutil.copyfile(STARTER_TEMPLATE, ENV_PATH)
    return True


def initialize_secrets(lines: list[str], secret_keys: tuple[str, ...]) -> list[str]:
    key_indexes = current_key_indexes(lines)
    generated: list[str] = []
    appended: list[str] = []

    for key in secret_keys:
        generated_value = secrets.token_hex(32)
        line = f"{key}={generated_value}"

        if key in key_indexes:
            current = lines[key_indexes[key]].split("=", 1)[1].strip()
            if not current:
                lines[key_indexes[key]] = line
                generated.append(key)
            continue

        appended.append(line)
        generated.append(key)

    if appended:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append("# Generated secrets")
        lines.extend(appended)

    return generated


def selected_bundles(raw_bundles: list[str]) -> list[str]:
    available = set(BUNDLE_SECRETS)
    bundles: list[str] = []

    for raw in raw_bundles:
        bundle = raw.strip()
        if not bundle:
            continue
        if bundle not in available:
            valid = ", ".join(sorted(available))
            raise SystemExit(f"unknown bundle '{bundle}' (expected one of: {valid})")
        if bundle not in bundles:
            bundles.append(bundle)

    return bundles


def main() -> int:
    args = parse_args()
    bundles = selected_bundles(args.bundle)

    created = ensure_env_exists()
    lines = load_lines(ENV_PATH)

    added_bundle_values: dict[str, list[str]] = {}
    for bundle in bundles:
        additions = append_missing_bundle_values(lines, bundle)
        if additions:
            added_bundle_values[bundle] = additions

    secret_keys = list(STARTER_SECRETS)
    for bundle in bundles:
        secret_keys.extend(BUNDLE_SECRETS[bundle])

    generated = initialize_secrets(lines, tuple(secret_keys))
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if created:
        print("created .env from .env.example")

    for bundle, additions in added_bundle_values.items():
        print(f"added {len(additions)} settings from env/bundles/{bundle}.env.example")

    if generated:
        print("initialized secrets in .env:")
        for key in generated:
            print(f"  - {key}")
    else:
        print(".env already has all requested starter and bundle secrets")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
