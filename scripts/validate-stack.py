#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_MAIN = REPO_ROOT / "docker-compose.yml"
CONFIG_DOC = REPO_ROOT / "docs" / "configuration.md"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
SECURITY_COMPOSE_FILES = [
    path
    for path in sorted(REPO_ROOT.glob("docker-compose*.yml"))
    if path.name != "docker-compose.local.example.yml"
]

COMPOSE_FILES = [
    path
    for path in sorted(REPO_ROOT.glob("docker-compose*.yml"))
    if path.name not in {"docker-compose.common.yml", "docker-compose.local.example.yml"}
]

FORBIDDEN_DOC_TERMS = {
    "nettest": [REPO_ROOT / "README.md", REPO_ROOT / "docs"],
    "cAdvisor": [REPO_ROOT / "docs"],
    "IT-Tools": [REPO_ROOT / "docs"],
    "SQLite Backup Service": [REPO_ROOT / "docs" / "backup.md"],
}

TRACKED_ARTIFACT_PATTERNS = [
    r"^scripts/\.venv/",
    r"^scripts/build/",
    r"^scripts/dist/",
    r"^scripts/\.playwright-mcp/",
    r"^scripts/\.coverage$",
]

REQUIRED_SECRET_VARS = {
    "BITMAGNET_POSTGRES_PASSWORD",
    "DB_PASSWORD",
    "DOCMOST_APP_SECRET",
    "DOCMOST_DB_PASSWORD",
    "GRAFANA_ADMIN_PASSWORD",
    "JITSI_AUTH_PASSWORD",
    "JITSI_JICOFO_AUTH_PASSWORD",
    "JITSI_JICOFO_COMPONENT_SECRET",
    "JITSI_JVB_AUTH_PASSWORD",
    "JITSI_TURN_CREDENTIALS",
    "JOPLIN_DB_PASSWORD",
    "KARAKEEP_MEILI_MASTER_KEY",
    "KARAKEEP_NEXTAUTH_SECRET",
    "PAPERLESS_DB_PASSWORD",
    "PAPERLESS_SECRET_KEY",
}

REQUIRED_CONFIG_VARS = {
    "JITSI_CLOUDFLARE_API_TOKEN",
    "JITSI_MEDIA_PUBLIC_HOSTNAME",
    "JITSI_MEDIA_SUBDOMAIN",
    "JITSI_TURN_MAX_PORT",
    "JITSI_TURN_MIN_PORT",
}

STALE_ENV_VARS = {
    "JITSI_EDGE_PUBLIC_IP",
}

WEAK_SECRET_FALLBACKS = {
    "admin",
    "bitmagnet_secret",
    "change_me",
}

MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!\!)\[[^\]]+\]\(([^)]+)\)")
URI_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


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
    try:
        output = subprocess.check_output(
            command,
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.output or "").strip()
        raise RuntimeError(detail or f"command failed: {' '.join(command)}") from exc
    return [line.strip() for line in output.splitlines() if line.strip()]


def compose_profiles() -> set[str]:
    return set(shell_lines(["docker", "compose", "config", "--profiles"]))


def compose_services() -> dict[str, dict]:
    try:
        output = subprocess.check_output(
            ["docker", "compose", "config", "--format", "json"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.output or "").strip()
        raise RuntimeError(detail or "docker compose config --format json failed") from exc
    config = json.loads(output)
    return config["services"]


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


def declared_env_vars(path: Path) -> set[str]:
    variables: set[str] = set()
    for line in read_text(path).splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]+)=", line)
        if match:
            variables.add(match.group(1))
    return variables


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


def stale_var_scan_files() -> list[Path]:
    files: list[Path] = [
        ENV_EXAMPLE,
        REPO_ROOT / "README.md",
    ]
    files.extend(sorted(REPO_ROOT.glob("docker-compose*.yml")))
    files.extend(sorted((REPO_ROOT / "config-templates").rglob("*")))
    files.extend(sorted((REPO_ROOT / "docs").rglob("*.md")))

    unique_files: list[Path] = []
    seen: set[Path] = set()
    for path in files:
        if not path.is_file() or path in seen:
            continue
        seen.add(path)
        unique_files.append(path)

    return unique_files


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


def find_stale_variable_references() -> list[str]:
    errors: list[str] = []
    for path in stale_var_scan_files():
        try:
            text = read_text(path)
        except UnicodeDecodeError:
            continue
        for variable in sorted(STALE_ENV_VARS):
            if variable in text:
                errors.append(
                    f"stale variable '{variable}' found in {path.relative_to(REPO_ROOT)}"
                )
    return errors


def find_weak_secret_fallbacks() -> list[str]:
    errors: list[str] = []
    default_pattern = re.compile(r"\$\{[^}:]+:-([^}]+)\}")
    secret_field_pattern = re.compile(r"(PASSWORD|SECRET|PASS)")

    for path in SECURITY_COMPOSE_FILES:
        for lineno, line in enumerate(read_text(path).splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not secret_field_pattern.search(stripped):
                continue

            for match in default_pattern.finditer(stripped):
                fallback = match.group(1)
                if fallback in WEAK_SECRET_FALLBACKS:
                    errors.append(
                        f"weak secret fallback '{fallback}' found in {path.relative_to(REPO_ROOT)}:{lineno}"
                    )

    return errors


def markdown_files() -> list[Path]:
    files = [REPO_ROOT / "README.md", REPO_ROOT / "scripts" / "README.md"]
    docs_root = REPO_ROOT / "docs"
    if docs_root.exists():
        files.extend(sorted(docs_root.rglob("*.md")))
    return [path for path in files if path.exists()]


def markdown_anchor_slug(text: str) -> str:
    slug = text.rstrip().lower()
    slug = re.sub(r"[^\w\- ]", "", slug)
    slug = slug.replace(" ", "-")
    slug = re.sub(r"-{3,}", "--", slug)
    slug = slug.rstrip("-")
    return slug


def markdown_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    seen: dict[str, int] = {}

    for match in MARKDOWN_HEADING_PATTERN.finditer(read_text(path)):
        heading = match.group(2).strip()
        base = markdown_anchor_slug(heading)
        if not base:
            continue

        count = seen.get(base, 0)
        seen[base] = count + 1
        anchors.add(base if count == 0 else f"{base}-{count}")

    return anchors


def split_link_target(target: str) -> tuple[str, str]:
    value = target.strip()
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1].strip()
    path_part, anchor = (value.split("#", 1) + [""])[:2]
    return path_part, anchor


def is_external_target(target: str) -> bool:
    if not target:
        return False
    return bool(
        URI_SCHEME_PATTERN.match(target)
        or target.startswith("//")
        or target.startswith("mailto:")
        or target.startswith("tel:")
    )


def validate_markdown_links() -> list[str]:
    errors: list[str] = []
    anchor_cache: dict[Path, set[str]] = {}

    for path in markdown_files():
        text = read_text(path)
        for match in MARKDOWN_LINK_PATTERN.finditer(text):
            target = match.group(1).strip()
            if not target or is_external_target(target):
                continue

            path_part, anchor = split_link_target(target)
            if not path_part:
                resolved = path
            else:
                resolved = (path.parent / path_part).resolve()
                if not resolved.exists():
                    errors.append(
                        f"broken markdown link in {path.relative_to(REPO_ROOT)} -> {target}"
                    )
                    continue

            if anchor:
                if resolved.suffix.lower() != ".md":
                    errors.append(
                        f"markdown anchor target is not a markdown file in "
                        f"{path.relative_to(REPO_ROOT)} -> {target}"
                    )
                    continue

                anchors = anchor_cache.setdefault(resolved, markdown_anchors(resolved))
                if anchor not in anchors:
                    errors.append(
                        f"missing markdown anchor in {path.relative_to(REPO_ROOT)} -> {target}"
                    )

    return errors


def validate_docmost_bundle() -> list[str]:
    command = [sys.executable, str(REPO_ROOT / "scripts" / "build-docmost-space.py"), "--check"]
    try:
        subprocess.check_output(
            command,
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.output or "").strip()
        if not detail:
            return ["docmost bundle check failed"]
        cleaned: list[str] = []
        for line in detail.splitlines():
            stripped = line.strip()
            if not stripped or stripped == "docmost bundle check failed:":
                continue
            if stripped.startswith("- "):
                stripped = stripped[2:]
            cleaned.append(f"docmost bundle: {stripped}")
        return cleaned or ["docmost bundle check failed"]
    return []


def validate_service_defaults(services: dict[str, dict]) -> list[str]:
    errors: list[str] = []

    for name, service in sorted(services.items()):
        image = service.get("image") or ""
        is_linuxserver = isinstance(image, str) and image.startswith("lscr.io/linuxserver/")

        if service.get("restart") != "unless-stopped":
            errors.append(f"service '{name}' must set restart: unless-stopped")

        if is_linuxserver:
            if service.get("init") is not False:
                errors.append(f"service '{name}' must set init: false for LinuxServer.io images")
        elif service.get("init") is not True:
            errors.append(f"service '{name}' must set init: true")

        security_opts = service.get("security_opt") or []
        if "no-new-privileges:true" not in security_opts:
            errors.append(f"service '{name}' must include security_opt no-new-privileges:true")

        if service.get("healthcheck") is None:
            errors.append(f"service '{name}' must define a healthcheck")

        logging = service.get("logging") or {}
        if logging.get("driver") != "json-file":
            errors.append(f"service '{name}' must use json-file logging")

        logging_options = logging.get("options") or {}
        if logging_options.get("max-size") != "10m" or logging_options.get("max-file") != "3":
            errors.append(f"service '{name}' must set log rotation to max-size=10m and max-file=3")

        resources = ((service.get("deploy") or {}).get("resources") or {})
        if not resources.get("limits") or not resources.get("reservations"):
            errors.append(f"service '{name}' must define deploy.resources limits and reservations")

    return errors


def validate_required_env_vars() -> list[str]:
    declared = declared_env_vars(ENV_EXAMPLE)
    missing = sorted((REQUIRED_SECRET_VARS | REQUIRED_CONFIG_VARS) - declared)
    if not missing:
        return []
    return [".env.example missing required vars: " + ", ".join(missing)]


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

    services: dict[str, dict] = {}
    compose_loaded = True
    try:
        actual_profiles = compose_profiles()
        services = compose_services()
    except RuntimeError as exc:
        compose_loaded = False
        errors.append(f"docker compose config failed: {exc}")

    if compose_loaded:
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
    errors.extend(find_stale_variable_references())
    errors.extend(find_weak_secret_fallbacks())
    errors.extend(validate_markdown_links())
    errors.extend(validate_docmost_bundle())
    errors.extend(validate_required_env_vars())
    if compose_loaded:
        errors.extend(validate_service_defaults(services))

    if errors:
        print("validation failed:\n", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("stack validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
