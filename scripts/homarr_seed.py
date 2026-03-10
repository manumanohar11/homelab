#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
BOARD_ID = "seed-home-board"
LAYOUT_ID = "seed-home-layout-base"
BOARD_NAME = "home"
ICON_BASE = "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons@master/svg"
FALLBACK_ICON = f"{ICON_BASE}/homarr.svg"


@dataclass(frozen=True)
class AppSpec:
    item_id: str
    app_id: str
    service: str
    name: str
    description: str
    section: str
    env_var: str
    default_subdomain: str
    icon_slug: str
    ping_url: str | None = None


SECTIONS: OrderedDict[str, str] = OrderedDict(
    [
        ("daily", "Every Day"),
        ("media", "Media Room"),
        ("control", "Lab Control"),
    ]
)


APP_SPECS: tuple[AppSpec, ...] = (
    AppSpec(
        item_id="seed-item-plex",
        app_id="seed-app-plex",
        service="plex",
        name="Plex",
        description="Watch",
        section="daily",
        env_var="PLEX_SUBDOMAIN",
        default_subdomain="plex",
        icon_slug="plex",
        ping_url="http://plex:32400/identity",
    ),
    AppSpec(
        item_id="seed-item-immich",
        app_id="seed-app-immich",
        service="immich-server",
        name="Immich",
        description="Photos",
        section="daily",
        env_var="IMMICH_SUBDOMAIN",
        default_subdomain="photos",
        icon_slug="immich",
        ping_url="http://immich-server:2283/api/server/ping",
    ),
    AppSpec(
        item_id="seed-item-freshrss",
        app_id="seed-app-freshrss",
        service="freshrss",
        name="FreshRSS",
        description="Feeds",
        section="daily",
        env_var="FRESHRSS_SUBDOMAIN",
        default_subdomain="freshrss",
        icon_slug="freshrss",
        ping_url="http://freshrss/",
    ),
    AppSpec(
        item_id="seed-item-searxng",
        app_id="seed-app-searxng",
        service="searxng",
        name="SearXNG",
        description="Search",
        section="daily",
        env_var="SEARXNG_SUBDOMAIN",
        default_subdomain="search",
        icon_slug="searxng",
        ping_url="http://searxng:8080/",
    ),
    AppSpec(
        item_id="seed-item-joplin",
        app_id="seed-app-joplin",
        service="joplin",
        name="Joplin",
        description="Notes",
        section="daily",
        env_var="JOPLIN_SUBDOMAIN",
        default_subdomain="joplin",
        icon_slug="joplin",
        ping_url="http://joplin:22300/api/ping",
    ),
    AppSpec(
        item_id="seed-item-syncthing",
        app_id="seed-app-syncthing",
        service="syncthing",
        name="Syncthing",
        description="Sync",
        section="daily",
        env_var="SYNCTHING_SUBDOMAIN",
        default_subdomain="syncthing",
        icon_slug="syncthing",
        ping_url="http://syncthing:8384/",
    ),
    AppSpec(
        item_id="seed-item-jellyfin",
        app_id="seed-app-jellyfin",
        service="jellyfin",
        name="Jellyfin",
        description="Alt Media",
        section="media",
        env_var="JELLYFIN_SUBDOMAIN",
        default_subdomain="jellyfin",
        icon_slug="jellyfin",
    ),
    AppSpec(
        item_id="seed-item-kavita",
        app_id="seed-app-kavita",
        service="kavita",
        name="Kavita",
        description="Reading",
        section="media",
        env_var="KAVITA_SUBDOMAIN",
        default_subdomain="kavita",
        icon_slug="kavita",
        ping_url="http://kavita:5000/api/health",
    ),
    AppSpec(
        item_id="seed-item-tautulli",
        app_id="seed-app-tautulli",
        service="tautulli",
        name="Tautulli",
        description="Plex Stats",
        section="media",
        env_var="TAUTULLI_SUBDOMAIN",
        default_subdomain="tautulli",
        icon_slug="tautulli",
    ),
    AppSpec(
        item_id="seed-item-portainer",
        app_id="seed-app-portainer",
        service="portainer",
        name="Portainer",
        description="Containers",
        section="control",
        env_var="PORTAINER_SUBDOMAIN",
        default_subdomain="portainer",
        icon_slug="portainer",
    ),
    AppSpec(
        item_id="seed-item-prometheus",
        app_id="seed-app-prometheus",
        service="prometheus",
        name="Prometheus",
        description="Metrics",
        section="control",
        env_var="PROMETHEUS_SUBDOMAIN",
        default_subdomain="prometheus",
        icon_slug="prometheus",
        ping_url="http://prometheus:9090/-/healthy",
    ),
    AppSpec(
        item_id="seed-item-grafana",
        app_id="seed-app-grafana",
        service="grafana",
        name="Grafana",
        description="Dashboards",
        section="control",
        env_var="GRAFANA_SUBDOMAIN",
        default_subdomain="grafana",
        icon_slug="grafana",
        ping_url="http://grafana:3000/api/health",
    ),
    AppSpec(
        item_id="seed-item-alertmanager",
        app_id="seed-app-alertmanager",
        service="alertmanager",
        name="Alertmanager",
        description="Alerts",
        section="control",
        env_var="ALERTMANAGER_SUBDOMAIN",
        default_subdomain="alertmanager",
        icon_slug="alertmanager",
        ping_url="http://alertmanager:9093/-/healthy",
    ),
    AppSpec(
        item_id="seed-item-uptime-kuma",
        app_id="seed-app-uptime-kuma",
        service="uptime-kuma",
        name="Uptime Kuma",
        description="Status",
        section="control",
        env_var="UPTIME_KUMA_SUBDOMAIN",
        default_subdomain="uptime",
        icon_slug="uptime-kuma",
        ping_url="http://uptime-kuma:3001/",
    ),
    AppSpec(
        item_id="seed-item-dozzle",
        app_id="seed-app-dozzle",
        service="dozzle",
        name="Dozzle",
        description="Logs",
        section="control",
        env_var="DOZZLE_SUBDOMAIN",
        default_subdomain="dozzle",
        icon_slug="dozzle",
        ping_url="http://dozzle:8080/",
    ),
    AppSpec(
        item_id="seed-item-duplicati",
        app_id="seed-app-duplicati",
        service="duplicati",
        name="Duplicati",
        description="Backups",
        section="control",
        env_var="DUPLICATI_SUBDOMAIN",
        default_subdomain="duplicati",
        icon_slug="duplicati",
        ping_url="http://duplicati:8200/",
    ),
)


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
    pattern = re.compile(r"\$\{([^}:]+)(:-([^}]*))?\}")
    for _ in range(5):
        changed = False
        for key, value in list(env.items()):
            expanded = pattern.sub(
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


def detect_running_services() -> set[str]:
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--services", "--status", "running"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def icon_url(icon_slug: str) -> str:
    return f"{ICON_BASE}/{icon_slug}.svg"


def build_public_url(env: dict[str, str], app: AppSpec) -> str:
    domain = env.get("DOMAIN_NAME", "localhost")
    subdomain = env.get(app.env_var, app.default_subdomain)
    return f"https://{subdomain}.{domain}"


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
""".strip()


def section_rows(apps: list[AppSpec]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for y_offset, (section_key, section_name) in enumerate(SECTIONS.items()):
        if any(app.section == section_key for app in apps) or section_key == "daily":
            rows.append(
                {
                    "id": f"seed-section-{section_key}",
                    "board_id": BOARD_ID,
                    "kind": "category",
                    "x_offset": 0,
                    "y_offset": y_offset,
                    "name": section_name,
                    "options": superjson(),
                }
            )
    return rows


def item_rows(apps: list[AppSpec]) -> list[dict[str, Any]]:
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
    section_classes = {
        "daily": ("cluster-daily", "#fb923c"),
        "media": ("cluster-media", "#60a5fa"),
        "control": ("cluster-control", "#2dd4bf"),
    }
    for app in apps:
        custom_class, border_color = section_classes[app.section]
        rows.append(
            {
                "id": app.item_id,
                "board_id": BOARD_ID,
                "kind": "app",
                "options": superjson(
                    {
                        "appId": app.app_id,
                        "openInNewTab": True,
                        "showTitle": True,
                        "pingEnabled": bool(app.ping_url),
                        "layout": "column",
                        "descriptionDisplayMode": "normal",
                    }
                ),
                "advanced_options": superjson(
                    {
                        "title": None,
                        "customCssClasses": [custom_class],
                        "borderColor": border_color,
                    }
                ),
            }
        )
    return rows


def app_rows(apps: list[AppSpec], env: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for app in apps:
        rows.append(
            {
                "id": app.app_id,
                "name": app.name,
                "description": app.description,
                "icon_url": icon_url(app.icon_slug),
                "href": build_public_url(env, app),
                "ping_url": app.ping_url,
            }
        )
    return rows


def item_layout_rows(apps: list[AppSpec]) -> list[dict[str, Any]]:
    explicit_layouts: dict[str, tuple[int, int, int, int]] = {
        "seed-item-clock": (0, 0, 5, 3),
        "seed-item-plex": (5, 0, 3, 3),
        "seed-item-immich": (8, 0, 4, 3),
        "seed-item-freshrss": (0, 3, 3, 1),
        "seed-item-searxng": (3, 3, 3, 1),
        "seed-item-joplin": (6, 3, 3, 1),
        "seed-item-syncthing": (9, 3, 3, 1),
        "seed-item-jellyfin": (0, 0, 4, 2),
        "seed-item-kavita": (4, 0, 4, 2),
        "seed-item-tautulli": (8, 0, 4, 2),
        "seed-item-portainer": (0, 0, 3, 2),
        "seed-item-grafana": (3, 0, 3, 2),
        "seed-item-uptime-kuma": (6, 0, 3, 2),
        "seed-item-dozzle": (9, 0, 3, 2),
        "seed-item-duplicati": (0, 2, 4, 1),
        "seed-item-prometheus": (4, 2, 4, 1),
        "seed-item-alertmanager": (8, 2, 4, 1),
    }
    layouts: list[dict[str, Any]] = []
    for item_id, section_key in [("seed-item-clock", "daily")]:
        x_offset, y_offset, width, height = explicit_layouts[item_id]
        layouts.append(
            {
                "item_id": item_id,
                "section_id": f"seed-section-{section_key}",
                "layout_id": LAYOUT_ID,
                "x_offset": x_offset,
                "y_offset": y_offset,
                "width": width,
                "height": height,
            }
        )

    for app in apps:
        x_offset, y_offset, width, height = explicit_layouts.get(app.item_id, (0, 0, 3, 1))
        layouts.append(
            {
                "item_id": app.item_id,
                "section_id": f"seed-section-{app.section}",
                "layout_id": LAYOUT_ID,
                "x_offset": x_offset,
                "y_offset": y_offset,
                "width": width,
                "height": height,
            }
        )
    return layouts


def select_apps(env: dict[str, str]) -> list[AppSpec]:
    running_services = detect_running_services()
    apps = [app for app in APP_SPECS if not running_services or app.service in running_services]
    if not apps:
        apps = list(APP_SPECS[:10])
    return apps


def update_server_setting(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT value FROM serverSetting WHERE setting_key = 'board'"
    ).fetchone()
    if row is None:
        payload = {"json": {}}
    else:
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


def seed_board(db_path: Path, env: dict[str, str]) -> list[str]:
    if not db_path.exists():
        raise FileNotFoundError(f"Homarr database not found at {db_path}")

    apps = select_apps(env)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    owner = conn.execute(
        "SELECT id, name FROM user ORDER BY rowid LIMIT 1"
    ).fetchone()
    if owner is None:
        raise RuntimeError("Homarr has no user yet. Complete the first user setup before seeding.")

    section_data = section_rows(apps)
    item_data = item_rows(apps)
    app_data = app_rows(apps, env)
    layout_data = item_layout_rows(apps)
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
            """
            INSERT INTO layout (id, name, board_id, column_count, breakpoint)
            VALUES (?, 'Base', ?, 12, 0)
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              board_id = excluded.board_id,
              column_count = excluded.column_count,
              breakpoint = excluded.breakpoint
            """,
            (LAYOUT_ID, BOARD_ID),
        )
        conn.execute(
            "DELETE FROM item_layout WHERE item_id IN (SELECT id FROM item WHERE board_id = ?)",
            (BOARD_ID,),
        )
        conn.execute("DELETE FROM item WHERE board_id = ?", (BOARD_ID,))
        conn.execute(
            "DELETE FROM section_layout WHERE section_id IN (SELECT id FROM section WHERE board_id = ?)",
            (BOARD_ID,),
        )
        conn.execute("DELETE FROM section WHERE board_id = ?", (BOARD_ID,))

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
    return [app.name for app in apps]


def main() -> int:
    env = load_env(ENV_PATH)
    db_path = resolve_db_path(env)
    included_apps = seed_board(db_path, env)
    print(f"Seeded Homarr board at {db_path}")
    print("Included apps:")
    for app_name in included_apps:
        print(f"- {app_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
