#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
BOARD_ID = "seed-home-board"
BOARD_NAME = "home"
ICON_BASE = "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons@master/svg"
FALLBACK_ICON = f"{ICON_BASE}/homarr.svg"
SEED_APP_PREFIX = "seed-app-"
SEED_ITEM_PREFIX = "seed-item-"
BUNDLE_CHOICES = ("media", "apps", "ops", "access")

PANGOLIN_LABEL = re.compile(r"^pangolin\.public-resources\.([^.]+)\.(.+)$")
ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(:-([^}]*))?\}")


@dataclass(frozen=True)
class LayoutSpec:
    id: str
    name: str
    column_count: int
    breakpoint: int


@dataclass(frozen=True)
class ServiceOverride:
    name: str | None = None
    description: str | None = None
    section: str | None = None
    icon_slug: str | None = None
    href: str | None = None
    ping_url: str | None = None
    local_path: str | None = None
    order: int = 500
    include: bool = True


@dataclass(frozen=True)
class ServiceCard:
    item_id: str
    app_id: str
    service: str
    name: str
    description: str
    section: str
    icon_slug: str
    href: str
    ping_url: str | None
    order: int


LAYOUT_SPECS: tuple[LayoutSpec, ...] = (
    LayoutSpec("seed-home-layout-small", "Small", 4, 0),
    LayoutSpec("seed-home-layout-medium", "Medium", 8, 800),
    LayoutSpec("seed-home-layout-large", "Large", 12, 1400),
)


SECTION_ORDER: dict[str, int] = {
    "Overview": 0,
    "Dashboards": 10,
    "Productivity": 20,
    "Documents": 30,
    "Knowledge": 40,
    "Files": 50,
    "Business": 55,
    "Automation": 60,
    "Media Servers": 70,
    "Media Management": 80,
    "Downloaders": 90,
    "Requests": 100,
    "Monitoring": 110,
    "Backups": 120,
}


SECTION_FAMILIES: dict[str, tuple[str, str]] = {
    "Dashboards": ("cluster-control", "#2dd4bf"),
    "Productivity": ("cluster-daily", "#fb923c"),
    "Documents": ("cluster-daily", "#fb923c"),
    "Knowledge": ("cluster-daily", "#fb923c"),
    "Files": ("cluster-daily", "#fb923c"),
    "Business": ("cluster-daily", "#fb923c"),
    "Automation": ("cluster-control", "#2dd4bf"),
    "Media Servers": ("cluster-media", "#60a5fa"),
    "Media Management": ("cluster-media", "#60a5fa"),
    "Downloaders": ("cluster-media", "#60a5fa"),
    "Requests": ("cluster-media", "#60a5fa"),
    "Monitoring": ("cluster-control", "#2dd4bf"),
    "Backups": ("cluster-control", "#2dd4bf"),
}


SERVICE_OVERRIDES: dict[str, ServiceOverride] = {
    "alertmanager": ServiceOverride(
        description="Alert routing",
        section="Monitoring",
        icon_slug="alertmanager",
    ),
    "dozzle": ServiceOverride(
        description="Live logs",
        section="Monitoring",
        icon_slug="dozzle",
    ),
    "duplicati": ServiceOverride(
        description="Backup console",
        section="Backups",
        icon_slug="duplicati",
        order=10,
    ),
    "glance-homepage": ServiceOverride(
        name="Glance",
        description="Alt dashboard",
        section="Dashboards",
        icon_slug="glance",
        order=20,
    ),
    "glances": ServiceOverride(
        description="System monitor",
        section="Monitoring",
        icon_slug="glances",
    ),
    "grafana": ServiceOverride(
        description="Dashboards",
        section="Dashboards",
        icon_slug="grafana",
        order=40,
    ),
    "homarr": ServiceOverride(
        description="Service portal",
        section="Dashboards",
        icon_slug="homarr",
        order=10,
    ),
    "immich-server": ServiceOverride(
        name="Immich",
        description="Photo library",
        section="Media Servers",
        icon_slug="immich",
        order=20,
    ),
    "jellyfin": ServiceOverride(
        description="Media streaming",
        section="Media Servers",
        icon_slug="jellyfin",
    ),
    "jellyseerr": ServiceOverride(
        description="Media requests",
        section="Requests",
        icon_slug="jellyseerr",
    ),
    "karakeep": ServiceOverride(
        description="Bookmarks and read later",
        section="Knowledge",
        icon_slug="karakeep",
        order=20,
    ),
    "linkwarden": ServiceOverride(
        description="Bookmarks and archives",
        section="Knowledge",
        icon_slug="linkwarden",
        order=10,
    ),
    "kavita": ServiceOverride(
        description="Reading library",
        section="Media Servers",
        icon_slug="kavita",
    ),
    "maintainerr": ServiceOverride(
        description="Library cleanup",
        section="Requests",
        icon_slug="maintainerr",
    ),
    "navidrome": ServiceOverride(
        description="Music streaming",
        section="Media Servers",
        icon_slug="navidrome",
    ),
    "notifiarr": ServiceOverride(
        description="Notifications",
        section="Requests",
        icon_slug="notifiarr",
    ),
    "overseerr": ServiceOverride(
        description="Media requests",
        section="Requests",
        icon_slug="overseerr",
    ),
    "plex": ServiceOverride(
        description="Media streaming",
        section="Media Servers",
        icon_slug="plex",
        local_path="/web",
        order=10,
    ),
    "portainer": ServiceOverride(
        description="Container control",
        section="Dashboards",
        icon_slug="portainer",
        order=30,
    ),
    "prometheus": ServiceOverride(
        description="Metrics store",
        section="Monitoring",
        icon_slug="prometheus",
    ),
    "scrutiny": ServiceOverride(
        description="Disk health",
        section="Monitoring",
        icon_slug="scrutiny",
    ),
    "speedtest-tracker": ServiceOverride(
        name="Speedtest Tracker",
        description="Internet trends",
        section="Monitoring",
        icon_slug="speedtest-tracker",
    ),
    "stash": ServiceOverride(
        description="Media organizer",
        section="Media Servers",
        icon_slug="stash",
    ),
    "tautulli": ServiceOverride(
        description="Plex analytics",
        section="Media Servers",
        icon_slug="tautulli",
    ),
    "tdarr": ServiceOverride(
        description="Transcode farm",
        section="Media Servers",
        icon_slug="tdarr",
    ),
    "uptime-kuma": ServiceOverride(
        description="Status checks",
        section="Monitoring",
        icon_slug="uptime-kuma",
    ),
}


def load_env(env_path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not env_path.exists():
        return env

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip("'\"")

    for _ in range(5):
        changed = False
        for key, value in list(env.items()):
            expanded = ENV_VAR_PATTERN.sub(
                lambda match: env.get(match.group(1), match.group(3) or ""),
                value,
            )
            if expanded != value:
                env[key] = expanded
                changed = True
        if not changed:
            break

    return env


def resolve_db_path(env: dict[str, str]) -> Path:
    base_dir = env.get("DOCKER_BASE_DIR")
    if base_dir:
        return Path(base_dir) / "homarr" / "appdata" / "db" / "db.sqlite"
    return REPO_ROOT / "data" / "homarr" / "appdata" / "db" / "db.sqlite"


def unique_values(values: list[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()

    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)

    return tuple(ordered)


def compose_config_command(
    bundles: tuple[str, ...],
    profiles: tuple[str, ...],
) -> list[str]:
    command = ["docker", "compose", "-f", "docker-compose.yml"]

    for bundle in bundles:
        command.extend(["-f", f"docker-compose.{bundle}.yml"])
    for profile in profiles:
        command.extend(["--profile", profile])

    command.extend(["config", "--format", "json"])
    return command


def load_compose_services(
    bundles: tuple[str, ...] = (),
    profiles: tuple[str, ...] = (),
) -> dict[str, dict[str, Any]]:
    command = compose_config_command(bundles, profiles)

    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("docker compose is not installed or not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"docker compose config failed: {detail}") from exc

    config = json.loads(result.stdout)
    return config.get("services", {})


def docker_json_command(command: list[str], error_message: str) -> Any:
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("docker is not installed or not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"{error_message}: {detail}") from exc

    return json.loads(result.stdout)


def docker_text_command(command: list[str], error_message: str) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("docker is not installed or not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"{error_message}: {detail}") from exc

    return result.stdout


def load_running_service_details(project_name: str) -> dict[str, dict[str, Any]]:
    output = docker_text_command(
        [
            "docker",
            "ps",
            "--filter",
            f"label=com.docker.compose.project={project_name}",
            "--format",
            "{{.ID}}",
        ],
        "docker ps failed",
    )
    container_ids = [line.strip() for line in output.splitlines() if line.strip()]

    if not container_ids:
        return {}

    inspect = docker_json_command(
        ["docker", "inspect", *container_ids],
        "docker inspect failed",
    )

    details: dict[str, dict[str, Any]] = {}
    for container in inspect:
        labels = container.get("Config", {}).get("Labels", {}) or {}
        service_name = labels.get("com.docker.compose.service")
        if not service_name:
            continue
        details[service_name] = container

    return details


def choose_published_binding(
    port_map: dict[str, Any] | None,
) -> tuple[str, str] | None:
    if not port_map:
        return None

    for container_port, bindings in port_map.items():
        if not bindings:
            continue
        for binding in bindings:
            host_ip = (binding or {}).get("HostIp", "")
            host_port = (binding or {}).get("HostPort")
            if not host_port:
                continue
            if host_ip in {"127.0.0.1", "::1"}:
                continue
            return (container_port, host_port)

    return None


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def icon_url(icon_slug: str) -> str:
    if not icon_slug:
        return FALLBACK_ICON
    if icon_slug.startswith("http://") or icon_slug.startswith("https://"):
        return icon_slug
    return f"{ICON_BASE}/{icon_slug}.svg"


def superjson(payload: dict[str, Any] | None = None) -> str:
    return json.dumps({"json": payload or {}}, separators=(",", ":"))


def gradient_svg_data_uri() -> str:
    svg = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice">
  <defs>
    <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="55%" stop-color="#111827"/>
      <stop offset="100%" stop-color="#1f2937"/>
    </linearGradient>
    <radialGradient id="sun" cx="20%" cy="15%" r="70%">
      <stop offset="0%" stop-color="#fb923c" stop-opacity="0.38"/>
      <stop offset="40%" stop-color="#fb923c" stop-opacity="0.14"/>
      <stop offset="100%" stop-color="#fb923c" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="blue" cx="85%" cy="18%" r="55%">
      <stop offset="0%" stop-color="#22d3ee" stop-opacity="0.20"/>
      <stop offset="100%" stop-color="#22d3ee" stop-opacity="0"/>
    </radialGradient>
    <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse">
      <path d="M 48 0 L 0 0 0 48" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="1600" height="900" fill="url(#g)"/>
  <rect width="1600" height="900" fill="url(#sun)"/>
  <rect width="1600" height="900" fill="url(#blue)"/>
  <circle cx="1360" cy="760" r="260" fill="rgba(15,23,42,0.38)"/>
  <rect width="1600" height="900" fill="url(#grid)"/>
</svg>
""".strip()
    return f"data:image/svg+xml,{quote(svg)}"


def board_css() -> str:
    return """
:root {
  --deck-ink: #e5eef7;
  --deck-muted: rgba(226, 232, 240, 0.72);
}

body::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 14% 12%, rgba(251, 146, 60, 0.15), transparent 28%),
    radial-gradient(circle at 84% 16%, rgba(96, 165, 250, 0.14), transparent 24%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.03), transparent 42%);
}

.mantine-Card-root,
.mantine-Paper-root {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.80), rgba(15, 23, 42, 0.58)) !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  backdrop-filter: blur(20px) saturate(140%);
  box-shadow:
    0 18px 48px rgba(2, 6, 23, 0.38),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
  transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
}

.mantine-Card-root:hover,
.mantine-Paper-root:hover {
  transform: translateY(-4px);
  box-shadow:
    0 24px 70px rgba(2, 6, 23, 0.52),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.hero-card {
  background:
    linear-gradient(135deg, rgba(251, 146, 60, 0.34), rgba(15, 23, 42, 0.90) 50%, rgba(34, 211, 238, 0.18)) !important;
  border-color: rgba(251, 191, 36, 0.50) !important;
}

.cluster-daily {
  background: linear-gradient(180deg, rgba(251, 146, 60, 0.16), rgba(15, 23, 42, 0.78)) !important;
}

.cluster-media {
  background: linear-gradient(180deg, rgba(96, 165, 250, 0.16), rgba(15, 23, 42, 0.78)) !important;
}

.cluster-control {
  background: linear-gradient(180deg, rgba(45, 212, 191, 0.16), rgba(15, 23, 42, 0.78)) !important;
}

.hero-card,
.cluster-daily,
.cluster-media,
.cluster-control {
  position: relative;
  overflow: hidden;
}

.hero-card::after,
.cluster-daily::after,
.cluster-media::after,
.cluster-control::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.04), transparent 44%);
  pointer-events: none;
}

.hero-card h1,
.hero-card h2,
.hero-card h3,
.hero-card p {
  color: #fff !important;
}

main h1,
main h2,
main h3,
[data-board-section-title] {
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--deck-muted) !important;
}

main a,
main p,
main span,
main div {
  color: var(--deck-ink);
}

main img,
main svg {
  filter: drop-shadow(0 12px 20px rgba(15, 23, 42, 0.22));
}

@media (max-width: 48em) {
  main h1,
  main h2,
  main h3,
  [data-board-section-title] {
    letter-spacing: 0.08em;
  }

  .mantine-Card-root:hover,
  .mantine-Paper-root:hover {
    transform: none;
  }
}
""".strip()


def humanize_service_name(service: str) -> str:
    parts = service.replace("_", "-").split("-")
    return " ".join(part.upper() if part.isupper() else part.capitalize() for part in parts)


def extract_pangolin_resource(labels: dict[str, str]) -> dict[str, str]:
    resources: dict[str, dict[str, str]] = defaultdict(dict)
    for key, value in labels.items():
        match = PANGOLIN_LABEL.match(key)
        if not match:
            continue
        resource_name, suffix = match.groups()
        resources[resource_name][suffix] = value
    if not resources:
        return {}

    resource_keys = sorted(resources)
    return resources[resource_keys[0]]


def build_pangolin_href(resource: dict[str, str]) -> str | None:
    full_domain = resource.get("full-domain")
    if not full_domain:
        return None
    return f"https://{full_domain}"


def build_pangolin_ping_url(resource: dict[str, str]) -> str | None:
    host = resource.get("targets[0].healthcheck.hostname")
    port = resource.get("targets[0].healthcheck.port")
    path = resource.get("targets[0].healthcheck.path", "/")
    scheme = resource.get("targets[0].healthcheck.method") or resource.get("targets[0].method") or "http"

    if not host or not port:
        return None
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{scheme}://{host}:{port}{path}"


def section_sort_key(section: str) -> tuple[int, str]:
    return (SECTION_ORDER.get(section, 999), section.lower())


def section_id(section: str) -> str:
    return f"seed-section-{slugify(section)}"


def service_ids(service: str) -> tuple[str, str]:
    service_slug = slugify(service)
    return (f"{SEED_ITEM_PREFIX}{service_slug}", f"{SEED_APP_PREFIX}{service_slug}")


def choose_section(labels: dict[str, str], override: ServiceOverride) -> str | None:
    if override.section:
        return override.section
    return labels.get("homepage.group")


def choose_name(service: str, labels: dict[str, str], resource: dict[str, str], override: ServiceOverride) -> str:
    return (
        override.name
        or labels.get("homepage.name")
        or resource.get("name")
        or humanize_service_name(service)
    )


def choose_description(labels: dict[str, str], override: ServiceOverride) -> str | None:
    return override.description or labels.get("homepage.description")


def choose_href(labels: dict[str, str], resource: dict[str, str], override: ServiceOverride) -> str | None:
    if override.href:
        return override.href
    if labels.get("homepage.href"):
        return labels["homepage.href"]
    return build_pangolin_href(resource)


def choose_ping_url(resource: dict[str, str], override: ServiceOverride) -> str | None:
    if override.ping_url:
        return override.ping_url
    return build_pangolin_ping_url(resource)


def choose_icon_slug(service: str, labels: dict[str, str], override: ServiceOverride) -> str:
    return override.icon_slug or labels.get("homepage.icon") or service


def build_service_cards(
    bundles: tuple[str, ...] = (),
    profiles: tuple[str, ...] = (),
) -> list[ServiceCard]:
    services = load_compose_services(bundles, profiles)
    cards: list[ServiceCard] = []

    for service_name, service in services.items():
        override = SERVICE_OVERRIDES.get(service_name, ServiceOverride())
        if not override.include:
            continue

        labels = service.get("labels", {}) or {}
        resource = extract_pangolin_resource(labels)
        section = choose_section(labels, override)
        href = choose_href(labels, resource, override)
        description = choose_description(labels, override)

        if not section or not href or not description:
            continue

        item_id, app_id = service_ids(service_name)
        cards.append(
            ServiceCard(
                item_id=item_id,
                app_id=app_id,
                service=service_name,
                name=choose_name(service_name, labels, resource, override),
                description=description,
                section=section,
                icon_slug=choose_icon_slug(service_name, labels, override),
                href=href,
                ping_url=choose_ping_url(resource, override),
                order=override.order,
            )
        )

    cards.sort(key=lambda card: (section_sort_key(card.section), card.order, card.name.lower()))
    return cards


def choose_local_scheme(
    resource: dict[str, str],
    published_container_port: str | None,
    published_host_port: str | None,
) -> str:
    method = resource.get("targets[0].method", "").lower()
    if method in {"http", "https"}:
        return method

    secure_ports = {"443", "8443", "9443"}
    if published_container_port:
        container_port = published_container_port.split("/", 1)[0]
        if container_port in secure_ports:
            return "https"
    if published_host_port in secure_ports:
        return "https"
    return "http"


def build_local_href(
    local_host: str,
    service_name: str,
    override: ServiceOverride,
    resource: dict[str, str],
    container: dict[str, Any],
) -> str | None:
    binding = choose_published_binding(
        container.get("NetworkSettings", {}).get("Ports", {}) or {}
    )
    published_container_port: str | None = None
    published_host_port: str | None = None

    if binding is not None:
        published_container_port, published_host_port = binding
    elif container.get("HostConfig", {}).get("NetworkMode") == "host":
        published_host_port = resource.get("targets[0].port")
        published_container_port = published_host_port

    if not published_host_port:
        return None

    scheme = choose_local_scheme(resource, published_container_port, published_host_port)
    path = override.local_path or ""
    return f"{scheme}://{local_host}:{published_host_port}{path}"


def build_running_service_cards(
    local_host: str,
    project_name: str,
) -> list[ServiceCard]:
    containers = load_running_service_details(project_name)
    cards: list[ServiceCard] = []

    for service_name, container in containers.items():
        override = SERVICE_OVERRIDES.get(service_name, ServiceOverride())
        if not override.include:
            continue

        labels = container.get("Config", {}).get("Labels", {}) or {}
        resource = extract_pangolin_resource(labels)
        section = choose_section(labels, override)
        description = choose_description(labels, override)
        href = build_local_href(local_host, service_name, override, resource, container)

        if not section or not href or not description:
            continue

        item_id, app_id = service_ids(service_name)
        cards.append(
            ServiceCard(
                item_id=item_id,
                app_id=app_id,
                service=service_name,
                name=choose_name(service_name, labels, resource, override),
                description=description,
                section=section,
                icon_slug=choose_icon_slug(service_name, labels, override),
                href=href,
                ping_url=choose_ping_url(resource, override),
                order=override.order,
            )
        )

    cards.sort(key=lambda card: (section_sort_key(card.section), card.order, card.name.lower()))
    return cards


def section_rows(cards: list[ServiceCard]) -> list[dict[str, Any]]:
    sections = OrderedDict()
    sections["Overview"] = "Overview"
    for card in cards:
        sections.setdefault(card.section, card.section)

    rows: list[dict[str, Any]] = []
    for y_offset, section_name in enumerate(
        sorted(sections.values(), key=section_sort_key)
    ):
        rows.append(
            {
                "id": section_id(section_name),
                "board_id": BOARD_ID,
                "kind": "category",
                "x_offset": 0,
                "y_offset": y_offset,
                "name": section_name,
                "options": superjson(),
            }
        )
    return rows


def section_style(section_name: str) -> tuple[str, str]:
    return SECTION_FAMILIES.get(section_name, ("cluster-control", "#2dd4bf"))


def item_rows(cards: list[ServiceCard]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "id": "seed-item-clock",
            "board_id": BOARD_ID,
            "kind": "clock",
            "options": superjson(
                {
                    "showDate": True,
                    "showSeconds": False,
                    "is24HourFormat": True,
                    "customTitleToggle": True,
                    "customTitle": "Command Deck",
                }
            ),
            "advanced_options": superjson(
                {
                    "title": None,
                    "customCssClasses": ["hero-card"],
                    "borderColor": "#f59e0b",
                }
            ),
        }
    ]

    for card in cards:
        css_class, border_color = section_style(card.section)
        rows.append(
            {
                "id": card.item_id,
                "board_id": BOARD_ID,
                "kind": "app",
                "options": superjson(
                    {
                        "appId": card.app_id,
                        "openInNewTab": True,
                        "showTitle": True,
                        "pingEnabled": bool(card.ping_url),
                        "layout": "column",
                        "descriptionDisplayMode": "normal",
                    }
                ),
                "advanced_options": superjson(
                    {
                        "title": None,
                        "customCssClasses": [css_class],
                        "borderColor": border_color,
                    }
                ),
            }
        )
    return rows


def app_rows(cards: list[ServiceCard]) -> list[dict[str, Any]]:
    return [
        {
            "id": card.app_id,
            "name": card.name,
            "description": card.description,
            "icon_url": icon_url(card.icon_slug),
            "href": card.href,
            "ping_url": card.ping_url,
        }
        for card in cards
    ]


def cards_by_section(cards: list[ServiceCard]) -> OrderedDict[str, list[ServiceCard]]:
    grouped: OrderedDict[str, list[ServiceCard]] = OrderedDict()
    for section_name in sorted({card.section for card in cards}, key=section_sort_key):
        grouped[section_name] = [
            card for card in cards if card.section == section_name
        ]
    return grouped


def card_dimensions(column_count: int, card_count: int) -> tuple[int, int]:
    if column_count <= 4:
        return (column_count, 1)
    if column_count <= 8:
        return (8, 1) if card_count == 1 else (4, 1)
    if card_count == 1:
        return (6, 1)
    if card_count == 2:
        return (6, 1)
    if card_count == 3:
        return (4, 1)
    return (3, 1)


def item_layout_rows(cards: list[ServiceCard]) -> list[dict[str, Any]]:
    layouts: list[dict[str, Any]] = []
    grouped = cards_by_section(cards)

    for layout_spec in LAYOUT_SPECS:
        hero_height = 2 if layout_spec.column_count <= 8 else 3
        layouts.append(
            {
                "item_id": "seed-item-clock",
                "section_id": section_id("Overview"),
                "layout_id": layout_spec.id,
                "x_offset": 0,
                "y_offset": 0,
                "width": layout_spec.column_count,
                "height": hero_height,
            }
        )

        for section_name, section_cards in grouped.items():
            card_width, card_height = card_dimensions(layout_spec.column_count, len(section_cards))
            cards_per_row = max(1, layout_spec.column_count // card_width)
            for index, card in enumerate(section_cards):
                layouts.append(
                    {
                        "item_id": card.item_id,
                        "section_id": section_id(section_name),
                        "layout_id": layout_spec.id,
                        "x_offset": (index % cards_per_row) * card_width,
                        "y_offset": index // cards_per_row,
                        "width": card_width,
                        "height": card_height,
                    }
                )

    return layouts


def layout_rows() -> list[dict[str, Any]]:
    return [
        {
            "id": layout_spec.id,
            "name": layout_spec.name,
            "board_id": BOARD_ID,
            "column_count": layout_spec.column_count,
            "breakpoint": layout_spec.breakpoint,
        }
        for layout_spec in LAYOUT_SPECS
    ]


def update_server_setting(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT value FROM serverSetting WHERE setting_key = 'board'"
    ).fetchone()
    payload = {"json": {}}
    if row is not None:
        payload = json.loads(row[0])

    settings = payload.setdefault("json", {})
    settings["homeBoardId"] = BOARD_ID
    settings["mobileHomeBoardId"] = BOARD_ID
    settings.setdefault("enableStatusByDefault", True)
    settings.setdefault("forceDisableStatus", False)
    conn.execute(
        """
        INSERT INTO serverSetting (setting_key, value)
        VALUES ('board', ?)
        ON CONFLICT(setting_key) DO UPDATE SET value = excluded.value
        """,
        (json.dumps(payload, separators=(",", ":")),),
    )

    appearance_row = conn.execute(
        "SELECT value FROM serverSetting WHERE setting_key = 'appearance'"
    ).fetchone()
    appearance_payload = {"json": {}}
    if appearance_row is not None:
        appearance_payload = json.loads(appearance_row[0])
    appearance_settings = appearance_payload.setdefault("json", {})
    appearance_settings["defaultColorScheme"] = "dark"
    conn.execute(
        """
        INSERT INTO serverSetting (setting_key, value)
        VALUES ('appearance', ?)
        ON CONFLICT(setting_key) DO UPDATE SET value = excluded.value
        """,
        (json.dumps(appearance_payload, separators=(",", ":")),),
    )


def reset_section_collapse_states(
    conn: sqlite3.Connection,
    section_ids: list[str],
) -> None:
    if not section_ids:
        return

    placeholders = ",".join("?" for _ in section_ids)
    conn.execute(
        f"DELETE FROM section_collapse_state WHERE section_id IN ({placeholders})",
        section_ids,
    )

    user_ids = [row[0] for row in conn.execute("SELECT id FROM user").fetchall()]
    rows = [
        {"user_id": user_id, "section_id": section_id, "collapsed": 0}
        for user_id in user_ids
        for section_id in section_ids
    ]
    if rows:
        conn.executemany(
            """
            INSERT INTO section_collapse_state (user_id, section_id, collapsed)
            VALUES (:user_id, :section_id, :collapsed)
            """,
            rows,
        )


def seed_board_from_cards(
    db_path: Path,
    cards: list[ServiceCard],
) -> list[str]:
    if not db_path.exists():
        raise FileNotFoundError(f"Homarr database not found at {db_path}")

    if not cards:
        raise RuntimeError("No routable services were discovered for the Homarr board.")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    owner = conn.execute(
        "SELECT id, name FROM user ORDER BY rowid LIMIT 1"
    ).fetchone()
    if owner is None:
        raise RuntimeError("Homarr has no user yet. Complete the first user setup before seeding.")

    section_data = section_rows(cards)
    item_data = item_rows(cards)
    app_data = app_rows(cards)
    layout_data = item_layout_rows(cards)
    board_layouts = layout_rows()
    section_ids = [row["id"] for row in section_data]

    with conn:
        conn.execute(
            """
            INSERT INTO board (
              id, name, is_public, creator_id, page_title, meta_title,
              background_image_url, background_image_attachment, background_image_repeat,
              background_image_size, primary_color, secondary_color, opacity, custom_css,
              disable_status, item_radius, icon_color
            ) VALUES (?, ?, 1, ?, ?, ?, ?, 'fixed', 'no-repeat', 'cover', ?, ?, ?, ?, 0, 'xl', ?)
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              is_public = excluded.is_public,
              creator_id = excluded.creator_id,
              page_title = excluded.page_title,
              meta_title = excluded.meta_title,
              background_image_url = excluded.background_image_url,
              background_image_attachment = excluded.background_image_attachment,
              background_image_repeat = excluded.background_image_repeat,
              background_image_size = excluded.background_image_size,
              primary_color = excluded.primary_color,
              secondary_color = excluded.secondary_color,
              opacity = excluded.opacity,
              custom_css = excluded.custom_css,
              disable_status = excluded.disable_status,
              item_radius = excluded.item_radius,
              icon_color = excluded.icon_color
            """,
            (
                BOARD_ID,
                BOARD_NAME,
                owner["id"],
                "Command Deck",
                "Manohar Solleti | Command Deck",
                gradient_svg_data_uri(),
                "#fb923c",
                "#22d3ee",
                84,
                board_css(),
                "#f8fafc",
            ),
        )

        conn.execute(
            "DELETE FROM item_layout WHERE item_id IN (SELECT id FROM item WHERE board_id = ?)",
            (BOARD_ID,),
        )
        conn.execute(
            "DELETE FROM section_layout WHERE section_id IN (SELECT id FROM section WHERE board_id = ?)",
            (BOARD_ID,),
        )
        conn.execute("DELETE FROM layout WHERE board_id = ?", (BOARD_ID,))
        conn.execute("DELETE FROM item WHERE board_id = ?", (BOARD_ID,))
        conn.execute("DELETE FROM section WHERE board_id = ?", (BOARD_ID,))
        conn.execute(
            "DELETE FROM app WHERE id LIKE ?",
            (f"{SEED_APP_PREFIX}%",),
        )

        conn.executemany(
            """
            INSERT INTO layout (id, name, board_id, column_count, breakpoint)
            VALUES (:id, :name, :board_id, :column_count, :breakpoint)
            """,
            board_layouts,
        )
        conn.executemany(
            """
            INSERT INTO section (id, board_id, kind, x_offset, y_offset, name, options)
            VALUES (:id, :board_id, :kind, :x_offset, :y_offset, :name, :options)
            """,
            section_data,
        )
        reset_section_collapse_states(conn, section_ids)
        conn.executemany(
            """
            INSERT INTO app (id, name, description, icon_url, href, ping_url)
            VALUES (:id, :name, :description, :icon_url, :href, :ping_url)
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              description = excluded.description,
              icon_url = excluded.icon_url,
              href = excluded.href,
              ping_url = excluded.ping_url
            """,
            app_data,
        )
        conn.executemany(
            """
            INSERT INTO item (id, board_id, kind, options, advanced_options)
            VALUES (:id, :board_id, :kind, :options, :advanced_options)
            """,
            item_data,
        )
        conn.executemany(
            """
            INSERT INTO item_layout (
              item_id, section_id, layout_id, x_offset, y_offset, width, height
            )
            VALUES (:item_id, :section_id, :layout_id, :x_offset, :y_offset, :width, :height)
            """,
            layout_data,
        )
        conn.execute(
            """
            UPDATE user
            SET home_board_id = ?, mobile_home_board_id = ?
            WHERE id = ?
            """,
            (BOARD_ID, BOARD_ID, owner["id"]),
        )
        update_server_setting(conn)

    conn.close()
    return [card.name for card in cards]


def seed_board(
    db_path: Path,
    bundles: tuple[str, ...] = (),
    profiles: tuple[str, ...] = (),
) -> list[str]:
    return seed_board_from_cards(db_path, build_service_cards(bundles, profiles))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the Homarr board from the resolved starter or bundle-aware compose config.",
    )
    parser.add_argument(
        "--bundle",
        action="append",
        choices=BUNDLE_CHOICES,
        default=[],
        help="Include an optional compose bundle. Repeat for multiple bundles.",
    )
    parser.add_argument(
        "--profile",
        action="append",
        default=[],
        help="Enable a compose profile while resolving services. Repeat as needed.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Override the detected Homarr SQLite path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the apps that would be seeded without writing to the Homarr database.",
    )
    parser.add_argument(
        "--running-only",
        action="store_true",
        help="Seed only apps for currently running media-stack containers using local LAN URLs.",
    )
    parser.add_argument(
        "--local-host",
        help="LAN hostname or IP to use for app URLs in --running-only mode. Defaults to LOCAL_LAN_IP from .env.",
    )
    parser.add_argument(
        "--project-name",
        default="media-stack",
        help="Compose project name to inspect in --running-only mode. Defaults to media-stack.",
    )
    return parser.parse_args()


def print_included_apps(app_names: list[str], prefix: str) -> None:
    print(prefix)
    print("Included apps:")
    for app_name in app_names:
        print(f"- {app_name}")


def main() -> int:
    args = parse_args()
    bundles = unique_values(args.bundle)
    profiles = unique_values(args.profile)
    env = load_env(ENV_PATH)

    if args.running_only:
        local_host = args.local_host or env.get("LOCAL_LAN_IP")
        if not local_host:
            raise RuntimeError("LOCAL_LAN_IP is missing from .env. Set it or pass --local-host.")
        cards = build_running_service_cards(local_host, args.project_name)
    else:
        cards = build_service_cards(bundles, profiles)

    if not cards:
        raise RuntimeError("No routable services were discovered for the Homarr board.")

    app_names = [card.name for card in cards]
    if args.dry_run:
        print_included_apps(app_names, "Dry run only. No changes were written.")
        return 0

    db_path = args.db_path or resolve_db_path(env)
    if args.running_only:
        included_apps = seed_board_from_cards(db_path, cards)
    else:
        included_apps = seed_board(db_path, bundles, profiles)
    print_included_apps(included_apps, f"Seeded Homarr board at {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
