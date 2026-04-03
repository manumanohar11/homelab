#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_GUIDANCE = REPO_ROOT / "AGENTS.md"

STARTER_COMPOSE = REPO_ROOT / "docker-compose.yml"
BUNDLE_COMPOSES = {
    "media": REPO_ROOT / "docker-compose.media.yml",
    "apps": REPO_ROOT / "docker-compose.apps.yml",
    "ops": REPO_ROOT / "docker-compose.ops.yml",
    "access": REPO_ROOT / "docker-compose.access.yml",
}
COMMON_COMPOSE = REPO_ROOT / "docker-compose.common.yml"
LOCAL_OVERRIDE = REPO_ROOT / "docker-compose.local.example.yml"

STARTER_ENV = REPO_ROOT / ".env.example"
STARTER_ENV_MAX_KEYS = 35
BUNDLE_ENV_FILES = {
    "media": REPO_ROOT / "env" / "bundles" / "media.env.example",
    "apps": REPO_ROOT / "env" / "bundles" / "apps.env.example",
    "ops": REPO_ROOT / "env" / "bundles" / "ops.env.example",
    "access": REPO_ROOT / "env" / "bundles" / "access.env.example",
}

ADVANCED_DOCS = {
    REPO_ROOT / "docs" / "advanced" / "architecture.md",
    REPO_ROOT / "docs" / "advanced" / "monitoring.md",
    REPO_ROOT / "docs" / "advanced" / "logging.md",
    REPO_ROOT / "docs" / "advanced" / "docmost.md",
    REPO_ROOT / "docs" / "advanced" / "scripts.md",
}

LEGACY_COMPOSE_FILES = {
    REPO_ROOT / "docker-compose.arr.yml",
    REPO_ROOT / "docker-compose.automation.yml",
    REPO_ROOT / "docker-compose.backup.yml",
    REPO_ROOT / "docker-compose.communication.yml",
    REPO_ROOT / "docker-compose.core.yml",
    REPO_ROOT / "docker-compose.documents.yml",
    REPO_ROOT / "docker-compose.downloaders.yml",
    REPO_ROOT / "docker-compose.files.yml",
    REPO_ROOT / "docker-compose.logging.yml",
    REPO_ROOT / "docker-compose.management.yml",
    REPO_ROOT / "docker-compose.media-extras.yml",
    REPO_ROOT / "docker-compose.media-servers.yml",
    REPO_ROOT / "docker-compose.monitoring.yml",
    REPO_ROOT / "docker-compose.photos.yml",
    REPO_ROOT / "docker-compose.productivity.yml",
    REPO_ROOT / "docker-compose.requests.yml",
    REPO_ROOT / "docker-compose.utilities.yml",
}

LEGACY_DOCS = {
    REPO_ROOT / "docs" / "architecture.md",
    REPO_ROOT / "docs" / "monitoring.md",
    REPO_ROOT / "docs" / "logging.md",
    REPO_ROOT / "docs" / "docmost.md",
    REPO_ROOT / "docs" / "scripts.md",
    REPO_ROOT / "docs" / "docmost-space",
}

STARTER_SECRETS = {
    "DB_PASSWORD",
    "DUPLICATI_ENCRYPTION_KEY",
    "HOMARR_SECRET_ENCRYPTION_KEY",
    "LINKWARDEN_NEXTAUTH_SECRET",
    "LINKWARDEN_POSTGRES_PASSWORD",
    "LINKWARDEN_MEILI_MASTER_KEY",
}
BUNDLE_SECRETS = {
    "media": {"BITMAGNET_POSTGRES_PASSWORD"},
    "apps": {
        "SEARXNG_SECRET",
        "JOPLIN_DB_PASSWORD",
        "PAPERLESS_SECRET_KEY",
        "PAPERLESS_DB_PASSWORD",
        "KARAKEEP_NEXTAUTH_SECRET",
        "KARAKEEP_MEILI_MASTER_KEY",
        "DOCMOST_APP_SECRET",
        "DOCMOST_DB_PASSWORD",
        "ERPNEXT_DB_ROOT_PASSWORD",
        "ERPNEXT_ADMIN_PASSWORD",
    },
    "ops": {"GRAFANA_ADMIN_PASSWORD"},
    "access": set(),
}

EXPECTED_STARTER_SERVICES = {
    "database",
    "docker-socket-proxy",
    "dozzle",
    "duplicati",
    "freshrss",
    "homarr",
    "immich-machine-learning",
    "immich-server",
    "linkwarden",
    "linkwarden-db",
    "linkwarden-meilisearch",
    "plex",
    "portainer",
    "redis",
    "tautulli",
    "watchtower",
}

SCENARIOS = [
    {
        "name": "starter",
        "bundles": [],
        "profiles": [],
        "expected_exact": EXPECTED_STARTER_SERVICES,
    },
    {
        "name": "media",
        "bundles": ["media"],
        "profiles": ["arr", "jellyfin"],
        "expected_contains": {"gluetun", "radarr", "qbittorrent", "overseerr", "jellyfin"},
    },
    {
        "name": "apps",
        "bundles": ["apps"],
        "profiles": [],
        "expected_contains": {
            "paperless-ngx",
            "docmost",
            "joplin",
            "karakeep",
            "erpnext-frontend",
            "erpnext-backend",
            "erpnext-db",
        },
    },
    {
        "name": "ops",
        "bundles": ["ops"],
        "profiles": ["monitoring"],
        "expected_contains": {"prometheus", "grafana", "loki", "promtail", "glances"},
    },
    {
        "name": "access",
        "bundles": ["access"],
        "profiles": [],
        "expected_contains": {"newt"},
    },
]

FULL_STACK_PROFILES = [
    "arr",
    "downloaders",
    "requests",
    "jellyfin",
    "stash",
    "kavita",
    "navidrome",
    "tdarr",
    "maintainerr",
    "notifiarr",
    "files",
    "automation",
    "kasm",
    "monitoring",
    "dashboard",
    "speedtest",
    "scrutiny",
    "restic",
    "db-backup",
]

ONE_SHOT_RESTART_SERVICES = {
    "erpnext-configurator",
    "erpnext-init-site",
}

MARKDOWN_LINK_PATTERN = re.compile(r"(?<!\!)\[[^\]]+\]\(([^)]+)\)")
URI_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def shell(command: list[str], *, cwd: Path) -> str:
    try:
        return subprocess.check_output(
            command,
            cwd=cwd,
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.output or "").strip()
        raise RuntimeError(detail or f"command failed: {' '.join(command)}") from exc


def assignment_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        return None
    return line.split("=", 1)[0].strip()


def env_keys(path: Path) -> set[str]:
    return {
        key
        for key in (
            assignment_key(line)
            for line in read_text(path).splitlines()
        )
        if key is not None
    }


def merge_env_lines(paths: list[Path], secret_keys: set[str]) -> list[str]:
    lines: list[str] = []
    seen_keys: set[str] = set()

    for path in paths:
        for line in read_text(path).splitlines():
            key = assignment_key(line)
            if key is None:
                lines.append(line)
                continue
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if key in secret_keys and line.split("=", 1)[1].strip() == "":
                lines.append(f"{key}=validation-{key.lower()}")
            else:
                lines.append(line)

    return lines


def write_scenario_env(temp_repo: Path, bundles: list[str]) -> None:
    secret_keys = set(STARTER_SECRETS)
    for bundle in bundles:
        secret_keys.update(BUNDLE_SECRETS[bundle])

    paths = [STARTER_ENV] + [BUNDLE_ENV_FILES[bundle] for bundle in bundles]
    content = "\n".join(merge_env_lines(paths, secret_keys)).rstrip() + "\n"
    (temp_repo / ".env").write_text(content, encoding="utf-8")


def compose_command(temp_repo: Path, bundles: list[str], profiles: list[str], *tail: str) -> list[str]:
    command = ["docker", "compose", "-f", "docker-compose.yml"]
    for bundle in bundles:
        command.extend(["-f", f"docker-compose.{bundle}.yml"])
    for profile in profiles:
        command.extend(["--profile", profile])
    command.extend(tail)
    return command


def compose_services(temp_repo: Path, bundles: list[str], profiles: list[str]) -> set[str]:
    output = shell(compose_command(temp_repo, bundles, profiles, "config", "--services"), cwd=temp_repo)
    return {line.strip() for line in output.splitlines() if line.strip()}


def compose_json(temp_repo: Path, bundles: list[str], profiles: list[str]) -> dict:
    output = shell(
        compose_command(temp_repo, bundles, profiles, "config", "--format", "json"),
        cwd=temp_repo,
    )
    return json.loads(output)


def markdown_files() -> list[Path]:
    files = [REPO_ROOT / "README.md", REPO_ROOT / "scripts" / "README.md"]
    files.extend(sorted((REPO_ROOT / "docs").rglob("*.md")))
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
            resolved = path if not path_part else (path.parent / path_part).resolve()
            if not resolved.exists():
                errors.append(f"broken markdown link in {path.relative_to(REPO_ROOT)} -> {target}")
                continue

            if anchor:
                if resolved.suffix.lower() != ".md":
                    errors.append(
                        f"markdown anchor target is not a markdown file in {path.relative_to(REPO_ROOT)} -> {target}"
                    )
                    continue
                anchors = anchor_cache.setdefault(resolved, markdown_anchors(resolved))
                if anchor not in anchors:
                    errors.append(f"missing markdown anchor in {path.relative_to(REPO_ROOT)} -> {target}")

    return errors


def validate_repo_layout() -> list[str]:
    errors: list[str] = []

    for path in [STARTER_COMPOSE, COMMON_COMPOSE, LOCAL_OVERRIDE, *BUNDLE_COMPOSES.values()]:
        if not path.exists():
            errors.append(f"missing required compose file: {path.relative_to(REPO_ROOT)}")

    for path in LEGACY_COMPOSE_FILES:
        if path.exists():
            errors.append(f"legacy compose file still present: {path.relative_to(REPO_ROOT)}")

    for path in ADVANCED_DOCS:
        if not path.exists():
            errors.append(f"missing advanced doc: {path.relative_to(REPO_ROOT)}")

    for path in LEGACY_DOCS:
        if path.exists():
            errors.append(f"legacy doc path still present: {path.relative_to(REPO_ROOT)}")

    return errors


def validate_beginner_docs() -> list[str]:
    errors: list[str] = []
    beginner_docs = [REPO_ROOT / "README.md", REPO_ROOT / "docs" / "quickstart.md"]
    banned_terms = [
        "make init-env",
        "scripts/validate-stack.py",
        "scripts/build-docmost-space.py",
        "scripts/homarr_seed.py",
        "scripts/sync-monitoring-config.sh",
        "comment include",
        "docker-compose.core.yml",
        "docker-compose.arr.yml",
        "docker-compose.downloaders.yml",
        "docker-compose.media-servers.yml",
        "docker-compose.communication.yml",
    ]

    for path in beginner_docs:
        text = read_text(path)
        for term in banned_terms:
            if term in text:
                errors.append(f"beginner doc still references '{term}' in {path.relative_to(REPO_ROOT)}")

    return errors


def validate_agent_guidance() -> list[str]:
    errors: list[str] = []
    if not AGENT_GUIDANCE.exists():
        return ["missing AGENTS.md"]

    text = read_text(AGENT_GUIDANCE)
    banned_terms = [
        "docker-compose.core.yml",
        "docker-compose.arr.yml",
        "docker-compose.downloaders.yml",
        "docker-compose.media-servers.yml",
        "docker-compose.communication.yml",
        "comment include",
        "Commented = disabled",
        "Start full stack",
        "docker compose --profile vpn up -d",
    ]

    for term in banned_terms:
        if term in text:
            errors.append(f"AGENTS.md still references '{term}'")

    return errors


def validate_example_env_files() -> list[str]:
    errors: list[str] = []
    required_keys = {
        STARTER_ENV: {
            "PUID",
            "PGID",
            "TZ",
            "DOMAIN_NAME",
            "LOCAL_LAN_IP",
            "DOCKER_PROJECT_DIR",
            "DOCKER_BASE_DIR",
            "DOCKER_SSD_CONFIG_DIR",
            "DOCKER_GIT_CONFIG_DIR",
            "DOCKER_MEDIA_DIR",
            "BACKUP_DESTINATION",
            "DB_PASSWORD",
            "DUPLICATI_ENCRYPTION_KEY",
            "HOMARR_SECRET_ENCRYPTION_KEY",
            "LINKWARDEN_NEXTAUTH_SECRET",
            "LINKWARDEN_POSTGRES_PASSWORD",
            "LINKWARDEN_MEILI_MASTER_KEY",
        },
        BUNDLE_ENV_FILES["media"]: {"VPN_SERVICE_PROVIDER", "OPENVPN_USER", "OPENVPN_PASSWORD", "SERVER_REGIONS", "BITMAGNET_POSTGRES_PASSWORD"},
        BUNDLE_ENV_FILES["apps"]: {
            "JOPLIN_DB_PASSWORD",
            "PAPERLESS_SECRET_KEY",
            "PAPERLESS_DB_PASSWORD",
            "KARAKEEP_NEXTAUTH_SECRET",
            "KARAKEEP_MEILI_MASTER_KEY",
            "DOCMOST_APP_SECRET",
            "DOCMOST_DB_PASSWORD",
            "ERPNEXT_DB_ROOT_PASSWORD",
            "ERPNEXT_ADMIN_PASSWORD",
        },
        BUNDLE_ENV_FILES["ops"]: {"GRAFANA_ADMIN_PASSWORD"},
        BUNDLE_ENV_FILES["access"]: {"PANGOLIN_ENDPOINT", "NEWT_ID", "NEWT_SECRET"},
    }

    for path, required in required_keys.items():
        if not path.exists():
            errors.append(f"missing env example file: {path.relative_to(REPO_ROOT)}")
            continue

        keys = env_keys(path)
        missing = sorted(required - keys)
        if missing:
            errors.append(f"{path.relative_to(REPO_ROOT)} missing keys: {', '.join(missing)}")

    starter_keys = env_keys(STARTER_ENV)
    if len(starter_keys) > STARTER_ENV_MAX_KEYS:
        errors.append(
            f".env.example has {len(starter_keys)} keys; keep the starter template at or below {STARTER_ENV_MAX_KEYS}"
        )

    bundle_keys: set[str] = set()
    for path in BUNDLE_ENV_FILES.values():
        bundle_keys.update(env_keys(path))

    leaked_keys = sorted(starter_keys & bundle_keys)
    if leaked_keys:
        errors.append(
            ".env.example should stay starter-only; remove bundle keys: "
            + ", ".join(leaked_keys)
        )

    return errors


def validate_init_script() -> list[str]:
    errors: list[str] = []
    starter_template_keys = env_keys(STARTER_ENV)
    bundle_template_keys: dict[str, set[str]] = {
        bundle: env_keys(path)
        for bundle, path in BUNDLE_ENV_FILES.items()
    }
    all_bundle_keys = set().union(*bundle_template_keys.values())

    with tempfile.TemporaryDirectory(prefix="init-validate-") as tmpdir:
        temp_repo = Path(tmpdir) / "repo"
        shutil.copytree(
            REPO_ROOT,
            temp_repo,
            ignore=shutil.ignore_patterns(".git", ".env", "data", "build", "__pycache__", "*.pyc"),
        )

        try:
            shell([sys.executable, str(temp_repo / "scripts" / "init-env.py")], cwd=temp_repo)
        except RuntimeError as exc:
            return [f"starter init failed: {exc}"]

        starter_env_path = temp_repo / ".env"
        if not starter_env_path.exists():
            return ["starter init did not create .env"]

        starter_env_keys = env_keys(starter_env_path)
        missing_starter = sorted(starter_template_keys - starter_env_keys)
        if missing_starter:
            errors.append(f"starter init .env missing keys: {', '.join(missing_starter)}")

        leaked_bundle_keys = sorted(starter_env_keys & all_bundle_keys)
        if leaked_bundle_keys:
            errors.append(
                "starter init .env should not include bundle keys: "
                + ", ".join(leaked_bundle_keys)
            )

        selected_bundles = ("media", "apps", "access")
        temp_repo.joinpath(".env").unlink()

        bundle_command = [sys.executable, str(temp_repo / "scripts" / "init-env.py")]
        for bundle in selected_bundles:
            bundle_command.extend(["--bundle", bundle])

        try:
            shell(bundle_command, cwd=temp_repo)
        except RuntimeError as exc:
            errors.append(f"bundle init failed: {exc}")
            return errors

        bundle_env_keys = env_keys(temp_repo / ".env")
        expected_bundle_keys = starter_template_keys.copy()
        for bundle in selected_bundles:
            expected_bundle_keys.update(bundle_template_keys[bundle])

        missing_selected = sorted(expected_bundle_keys - bundle_env_keys)
        if missing_selected:
            errors.append(
                "bundle init .env missing selected starter or bundle keys: "
                + ", ".join(missing_selected)
            )

        unselected_bundle_keys = set()
        for bundle, keys in bundle_template_keys.items():
            if bundle not in selected_bundles:
                unselected_bundle_keys.update(keys)

        leaked_unselected = sorted(bundle_env_keys & unselected_bundle_keys)
        if leaked_unselected:
            errors.append(
                "bundle init .env should not include unselected bundle keys: "
                + ", ".join(leaked_unselected)
            )

    return errors


def validate_docmost_bundle() -> list[str]:
    with tempfile.TemporaryDirectory(prefix="docmost-") as tmpdir:
        output_dir = Path(tmpdir) / "docmost-space"
        for check in (False, True):
            command = [sys.executable, str(REPO_ROOT / "scripts" / "build-docmost-space.py"), "--output-dir", str(output_dir)]
            if check:
                command.insert(2, "--check")
            try:
                subprocess.check_output(
                    command,
                    cwd=REPO_ROOT,
                    text=True,
                    stderr=subprocess.STDOUT,
                )
            except subprocess.CalledProcessError as exc:
                detail = (exc.output or "").strip()
                return [f"docmost bundle failed: {detail or 'unknown error'}"]
    return []


def validate_service_defaults(services: dict[str, dict]) -> list[str]:
    errors: list[str] = []

    for name, service in sorted(services.items()):
        image = service.get("image") or ""
        is_linuxserver = isinstance(image, str) and image.startswith("lscr.io/linuxserver/")

        expected_restart = "on-failure" if name in ONE_SHOT_RESTART_SERVICES else "unless-stopped"
        if service.get("restart") != expected_restart:
            errors.append(f"service '{name}' must set restart: {expected_restart}")

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


def validate_compose_scenarios() -> list[str]:
    errors: list[str] = []

    with tempfile.TemporaryDirectory(prefix="stack-validate-") as tmpdir:
        temp_repo = Path(tmpdir) / "repo"
        shutil.copytree(
            REPO_ROOT,
            temp_repo,
            ignore=shutil.ignore_patterns(".git", ".env", "data", "build", "__pycache__", "*.pyc"),
        )

        for scenario in SCENARIOS:
            write_scenario_env(temp_repo, scenario["bundles"])
            try:
                services = compose_services(temp_repo, scenario["bundles"], scenario["profiles"])
            except RuntimeError as exc:
                errors.append(f"{scenario['name']} compose config failed: {exc}")
                continue

            expected_exact = scenario.get("expected_exact")
            if expected_exact is not None and services != expected_exact:
                errors.append(
                    f"{scenario['name']} services mismatch: expected {sorted(expected_exact)}, got {sorted(services)}"
                )

            expected_contains = scenario.get("expected_contains", set())
            missing = sorted(expected_contains - services)
            if missing:
                errors.append(
                    f"{scenario['name']} missing expected services: {', '.join(missing)}"
                )

            if scenario["name"] in {"starter", "media"}:
                command = [sys.executable, str(temp_repo / "scripts" / "homarr_seed.py"), "--dry-run"]
                for bundle in scenario["bundles"]:
                    command.extend(["--bundle", bundle])
                for profile in scenario["profiles"]:
                    command.extend(["--profile", profile])
                try:
                    output = shell(command, cwd=temp_repo)
                except RuntimeError as exc:
                    errors.append(f"{scenario['name']} homarr dry-run failed: {exc}")
                    continue
                if "Included apps:" not in output:
                    errors.append(f"{scenario['name']} homarr dry-run did not list apps")

        write_scenario_env(temp_repo, list(BUNDLE_COMPOSES))
        try:
            full_config = compose_json(temp_repo, list(BUNDLE_COMPOSES), FULL_STACK_PROFILES)
        except RuntimeError as exc:
            errors.append(f"full-stack compose config failed: {exc}")
            return errors

        errors.extend(validate_service_defaults(full_config["services"]))

    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(validate_repo_layout())
    errors.extend(validate_example_env_files())
    errors.extend(validate_init_script())
    errors.extend(validate_beginner_docs())
    errors.extend(validate_agent_guidance())
    errors.extend(validate_markdown_links())
    errors.extend(validate_docmost_bundle())
    errors.extend(validate_compose_scenarios())

    if errors:
        print("validation failed:\n", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("stack validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
