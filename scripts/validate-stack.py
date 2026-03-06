#!/usr/bin/env python3

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_MAIN = REPO_ROOT / "docker-compose.yml"
CONFIG_DOC = REPO_ROOT / "docs" / "configuration.md"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

COMPOSE_FILES = [
    path
    for path in sorted(REPO_ROOT.glob("docker-compose*.yml"))
    if path.name not in {"docker-compose.common.yml", "docker-compose.local.example.yml"}
]

FORBIDDEN_DOC_TERMS = {
    "nettest": [REPO_ROOT / "README.md", REPO_ROOT / "docs"],
    "cAdvisor": [REPO_ROOT / "docs"],
    "IT-Tools": [REPO_ROOT / "docs"],
    "Stirling PDF": [REPO_ROOT / "docs"],
    "SQLite Backup Service": [REPO_ROOT / "docs" / "backup.md"],
}

TRACKED_ARTIFACT_PATTERNS = [
    r"^scripts/\.venv/",
    r"^scripts/build/",
    r"^scripts/dist/",
    r"^scripts/\.playwright-mcp/",
    r"^scripts/\.coverage$",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_services(path: Path) -> list[str]:
    services: list[str] = []
    in_services = False

    for line in read_text(path).splitlines():
        if line.startswith("services:"):
            in_services = True
            continue

        if in_services and re.match(r"^[A-Za-z0-9_-]+:", line):
            break

        match = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", line)
        if in_services and match:
            services.append(match.group(1))

    return services


def shell_lines(command: list[str]) -> list[str]:
    output = subprocess.check_output(command, cwd=REPO_ROOT, text=True)
    return [line.strip() for line in output.splitlines() if line.strip()]


def compose_profiles() -> set[str]:
    return set(shell_lines(["docker", "compose", "config", "--profiles"]))


def documented_profiles_from_comments(path: Path) -> set[str]:
    profiles: set[str] = set()
    for line in read_text(path).splitlines():
        match = re.match(r"^#\s+([a-z0-9-]+)\s+-", line)
        if match:
            profiles.add(match.group(1))
    return profiles


def documented_profiles_from_markdown(path: Path) -> set[str]:
    profiles: set[str] = set()
    for line in read_text(path).splitlines():
        match = re.match(r"^\| `([a-z0-9-]+)` \|", line)
        if match:
            profiles.add(match.group(1))
    return profiles


def tracked_artifacts() -> list[str]:
    tracked = shell_lines(["git", "ls-files"])
    offenders: list[str] = []
    for item in tracked:
        if not (REPO_ROOT / item).exists():
            continue
        for pattern in TRACKED_ARTIFACT_PATTERNS:
            if re.match(pattern, item):
                offenders.append(item)
                break
    return offenders


def find_forbidden_terms() -> list[str]:
    errors: list[str] = []
    for term, roots in FORBIDDEN_DOC_TERMS.items():
        pattern = re.compile(re.escape(term))
        for root in roots:
            paths = [root] if root.is_file() else sorted(root.rglob("*.md"))
            for path in paths:
                text = read_text(path)
                if pattern.search(text):
                    errors.append(f"stale term '{term}' found in {path.relative_to(REPO_ROOT)}")
    return errors


def main() -> int:
    errors: list[str] = []

    services_by_file = {path: extract_services(path) for path in COMPOSE_FILES}
    owners: dict[str, list[str]] = {}
    for path, services in services_by_file.items():
        for service in services:
            owners.setdefault(service, []).append(path.name)

    for service, files in sorted(owners.items()):
        if len(files) > 1:
            errors.append(
                f"duplicate compose service '{service}' declared in {', '.join(files)}"
            )

    actual_profiles = compose_profiles()
    main_profiles = documented_profiles_from_comments(COMPOSE_MAIN)
    config_doc_profiles = documented_profiles_from_markdown(CONFIG_DOC)
    env_profiles = documented_profiles_from_comments(ENV_EXAMPLE)

    for source_name, documented in [
        ("docker-compose.yml comments", main_profiles),
        ("docs/configuration.md", config_doc_profiles),
        (".env.example", env_profiles),
    ]:
        missing = sorted(actual_profiles - documented)
        extra = sorted(documented - actual_profiles)
        if missing:
            errors.append(f"{source_name} missing profiles: {', '.join(missing)}")
        if extra:
            errors.append(f"{source_name} has stale profiles: {', '.join(extra)}")

    offenders = tracked_artifacts()
    if offenders:
        errors.append("tracked local artifacts:\n  - " + "\n  - ".join(offenders[:20]))

    errors.extend(find_forbidden_terms())

    if errors:
        print("validation failed:\n", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("stack validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
