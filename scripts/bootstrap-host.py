#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create missing host bind-mount directories for the resolved starter or "
            "bundle-aware compose config."
        )
    )
    parser.add_argument(
        "--bundle",
        action="append",
        default=[],
        help="Include an optional compose bundle. Repeat for multiple bundles.",
    )
    parser.add_argument(
        "--profile",
        action="append",
        default=[],
        help="Enable an optional compose profile. Repeat for multiple profiles.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the directories that would be created without changing the host.",
    )
    return parser.parse_args()


def unique_values(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        value = raw.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def compose_config(bundles: tuple[str, ...], profiles: tuple[str, ...]) -> dict:
    command = ["docker", "compose", "-f", "docker-compose.yml"]
    for bundle in bundles:
        command.extend(["-f", f"docker-compose.{bundle}.yml"])
    for profile in profiles:
        command.extend(["--profile", profile])
    command.extend(["config", "--format", "json"])

    try:
        output = subprocess.check_output(command, cwd=REPO_ROOT, text=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc

    return json.loads(output)


def is_socket_mount(path: Path) -> bool:
    return path == Path("/var/run/docker.sock") or path.suffix == ".sock"


def looks_like_file(path: Path, target: str) -> bool:
    target_path = Path(target)
    if path.suffix or target_path.suffix:
        return True
    return path.name.startswith(".") and target_path.name.startswith(".")


def bind_sources(config: dict) -> tuple[dict[Path, list[str]], dict[Path, list[str]]]:
    directory_sources: dict[Path, list[str]] = {}
    file_sources: dict[Path, list[str]] = {}

    services = config.get("services", {})
    for service_name, service in services.items():
        for volume in service.get("volumes", []):
            if not isinstance(volume, dict) or volume.get("type") != "bind":
                continue

            source_raw = volume.get("source")
            target = volume.get("target", "")
            if not source_raw:
                continue

            source = Path(source_raw)
            if not source.is_absolute():
                source = (REPO_ROOT / source).resolve()

            if is_socket_mount(source):
                continue

            ref = f"{service_name}:{target}"
            if looks_like_file(source, target):
                file_sources.setdefault(source, []).append(ref)
            else:
                directory_sources.setdefault(source, []).append(ref)

    return directory_sources, file_sources


def create_directories(paths: list[Path], dry_run: bool) -> list[Path]:
    created: list[Path] = []
    for path in paths:
        if path.exists():
            continue
        if dry_run:
            created.append(path)
            continue
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    return created


def print_path_group(title: str, mapping: dict[Path, list[str]]) -> None:
    print(title)
    for path in sorted(mapping):
        refs = ", ".join(sorted(mapping[path]))
        print(f"  - {path} [{refs}]")


def main() -> int:
    args = parse_args()
    bundles = unique_values(args.bundle)
    profiles = unique_values(args.profile)

    config = compose_config(bundles, profiles)
    directory_sources, file_sources = bind_sources(config)

    created = create_directories(sorted(directory_sources), args.dry_run)

    action = "would create" if args.dry_run else "created"
    if created:
        print_path_group(f"{action} {len(created)} bind-mount directories:", {path: directory_sources[path] for path in created})
    else:
        print("all bind-mount directories already exist")

    missing_files = {
        path: refs
        for path, refs in sorted(file_sources.items())
        if not path.exists()
    }
    if missing_files:
        print_path_group("missing file bind sources (not auto-created):", missing_files)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
