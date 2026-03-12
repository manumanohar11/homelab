#!/usr/bin/env python3

from __future__ import annotations

import secrets
import shutil
from pathlib import Path

REQUIRED_SECRETS = (
    "DB_PASSWORD",
    "GRAFANA_ADMIN_PASSWORD",
    # JITSI_CLOUDFLARE_API_TOKEN stays user-supplied because it must match your Cloudflare account.
    "JITSI_AUTH_PASSWORD",
    "JITSI_JICOFO_COMPONENT_SECRET",
    "JITSI_JICOFO_AUTH_PASSWORD",
    "JITSI_JVB_AUTH_PASSWORD",
    "JITSI_TURN_CREDENTIALS",
    "JOPLIN_DB_PASSWORD",
    "BITMAGNET_POSTGRES_PASSWORD",
    "PAPERLESS_SECRET_KEY",
    "PAPERLESS_DB_PASSWORD",
    "KARAKEEP_NEXTAUTH_SECRET",
    "KARAKEEP_MEILI_MASTER_KEY",
    "DOCMOST_APP_SECRET",
    "DOCMOST_DB_PASSWORD",
)


def load_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def main() -> int:
    project_dir = Path(__file__).resolve().parent.parent
    env_path = project_dir / ".env"
    example_path = project_dir / ".env.example"

    if not env_path.exists():
        if not example_path.exists():
            raise FileNotFoundError(f"missing template: {example_path}")
        shutil.copyfile(example_path, env_path)
        print("created .env from .env.example")

    lines = load_lines(env_path)
    key_to_index: dict[str, int] = {}

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0]
        if key in REQUIRED_SECRETS:
            key_to_index[key] = index

    generated: list[str] = []
    appended: list[str] = []

    for key in REQUIRED_SECRETS:
        generated_value = secrets.token_hex(32)
        line = f"{key}={generated_value}"

        if key in key_to_index:
            current = lines[key_to_index[key]].split("=", 1)[1].strip()
            if not current:
                lines[key_to_index[key]] = line
                generated.append(key)
            continue

        appended.append(line)
        generated.append(key)

    if appended:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append("# Generated required secrets")
        lines.extend(appended)

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if generated:
        print("initialized required secrets in .env:")
        for key in generated:
            print(f"  - {key}")
    else:
        print(".env already has all required secrets")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
