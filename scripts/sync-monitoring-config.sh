#!/bin/bash

set -euo pipefail

MODE="${1:---sync}"

if [[ "$MODE" != "--sync" && "$MODE" != "--check" ]]; then
    echo "Usage: $0 [--sync|--check]" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

load_env_file() {
    local file="$1"
    local line key value

    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        [[ "$line" != *=* ]] && continue

        key="${line%%=*}"
        value="${line#*=}"

        if [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
            export "$key=$value"
        fi
    done < "$file"
}

resolve_path_var() {
    local value="$1"
    value="${value//\$\{DOCKER_PROJECT_DIR\}/$DOCKER_PROJECT_DIR}"
    value="${value//\$DOCKER_PROJECT_DIR/$DOCKER_PROJECT_DIR}"
    printf '%s\n' "$value"
}

if [[ -f "$PROJECT_DIR/.env" ]]; then
    load_env_file "$PROJECT_DIR/.env"
fi

DOCKER_PROJECT_DIR="${DOCKER_PROJECT_DIR:-/opt/media-stack}"
DOCKER_BASE_DIR="$(resolve_path_var "${DOCKER_BASE_DIR:-$DOCKER_PROJECT_DIR/data}")"
DOCKER_GIT_CONFIG_DIR="$(resolve_path_var "${DOCKER_GIT_CONFIG_DIR:-$PROJECT_DIR/config-templates}")"

FILE_MAPPINGS=(
    "$DOCKER_GIT_CONFIG_DIR/loki/local-config.yaml|$DOCKER_BASE_DIR/loki/config/local-config.yaml"
    "$DOCKER_GIT_CONFIG_DIR/promtail/config.yml|$DOCKER_BASE_DIR/promtail/config/config.yml"
    "$DOCKER_GIT_CONFIG_DIR/prometheus/prometheus.yml|$DOCKER_BASE_DIR/prometheus/config/prometheus.yml"
    "$DOCKER_GIT_CONFIG_DIR/alertmanager/alertmanager.yml|$DOCKER_BASE_DIR/alertmanager/config/alertmanager.yml"
)

DIR_MAPPINGS=(
    "$DOCKER_GIT_CONFIG_DIR/grafana/provisioning|$DOCKER_BASE_DIR/grafana/provisioning"
    "$DOCKER_GIT_CONFIG_DIR/prometheus/rules|$DOCKER_BASE_DIR/prometheus/config/rules"
)

RUNTIME_DIRS=(
    "$DOCKER_BASE_DIR/loki/config"
    "$DOCKER_BASE_DIR/loki/data"
    "$DOCKER_BASE_DIR/loki/data/rules"
    "$DOCKER_BASE_DIR/loki/data/rules-temp"
    "$DOCKER_BASE_DIR/promtail/config"
    "$DOCKER_BASE_DIR/grafana/data"
    "$DOCKER_BASE_DIR/grafana/provisioning"
    "$DOCKER_BASE_DIR/prometheus/config"
    "$DOCKER_BASE_DIR/prometheus/data"
    "$DOCKER_BASE_DIR/alertmanager/config"
    "$DOCKER_BASE_DIR/alertmanager/data"
)

ensure_dir() {
    local dir="$1"
    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir"
        echo "created $dir"
    fi
}

sync_file() {
    local src="$1"
    local dest="$2"

    if [[ ! -f "$src" ]]; then
        echo "missing template: $src" >&2
        return 1
    fi

    ensure_dir "$(dirname "$dest")"

    if [[ "$MODE" == "--check" ]]; then
        if [[ ! -f "$dest" ]] || ! cmp -s "$src" "$dest"; then
            echo "drift file $dest"
            return 2
        fi
        return 0
    fi

    cp "$src" "$dest"
    echo "synced $dest"
}

sync_dir() {
    local src="$1"
    local dest="$2"

    if [[ ! -d "$src" ]]; then
        echo "missing template dir: $src" >&2
        return 1
    fi

    ensure_dir "$dest"

    if [[ "$MODE" == "--check" ]]; then
        if [[ ! -d "$dest" ]] || ! diff -qr "$src" "$dest" >/dev/null 2>&1; then
            echo "drift dir  $dest"
            return 2
        fi
        return 0
    fi

    rsync -a --delete "$src/" "$dest/"
    echo "synced $dest"
}

if [[ "$MODE" == "--sync" ]]; then
    echo "preparing runtime directories under $DOCKER_BASE_DIR"
    for dir in "${RUNTIME_DIRS[@]}"; do
        ensure_dir "$dir"
    done
fi

drift=0

for mapping in "${FILE_MAPPINGS[@]}"; do
    IFS="|" read -r src dest <<< "$mapping"
    if ! sync_file "$src" "$dest"; then
        status=$?
        if [[ $status -eq 2 ]]; then
            drift=1
        else
            exit $status
        fi
    fi
done

for mapping in "${DIR_MAPPINGS[@]}"; do
    IFS="|" read -r src dest <<< "$mapping"
    if ! sync_dir "$src" "$dest"; then
        status=$?
        if [[ $status -eq 2 ]]; then
            drift=1
        else
            exit $status
        fi
    fi
done

if [[ "$MODE" == "--check" ]]; then
    if [[ $drift -ne 0 ]]; then
        echo "monitoring runtime config is out of sync with config-templates/" >&2
        exit 1
    fi
    echo "monitoring runtime config matches config-templates/"
else
    echo "monitoring runtime config synced from config-templates/"
fi
