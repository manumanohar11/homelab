"""
Configuration management for the network testing tool.

Handles loading configuration from YAML files with fallback to defaults,
including support for named test profiles.
"""

import os
from typing import Dict, Optional, Any

# Optional YAML support
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore
    YAML_AVAILABLE = False


# Default Configuration
DEFAULT_CONFIG: Dict[str, Any] = {
    "targets": {
        "Google DNS": "8.8.8.8",
        "Cloudflare DNS": "1.1.1.1",
        "Microsoft Teams": "teams.microsoft.com",
    },
    "tests": {
        "ping_count": 10,
        "mtr_count": 10,
        "expected_speed": 100,  # Mbps
    },
    "thresholds": {
        "latency": {"good": 50, "warning": 100},  # ms
        "jitter": {"good": 15, "warning": 30},  # ms
        "packet_loss": {"good": 0, "warning": 2},  # %
        "download_pct": {"good": 80, "warning": 50},  # % of expected
    },
    "output": {
        "directory": os.path.expanduser("~/Downloads"),
        "open_browser": True,
    },
    "logging": {
        "enabled": False,
        "file": os.path.expanduser("~/Downloads/nettest.log"),
    },
    "profiles": {
        "quick": {
            "description": "Fast ping-only test",
            "ping_count": 3,
            "skip_speedtest": True,
            "skip_dns": True,
            "skip_mtr": True,
        },
        "full": {
            "description": "Comprehensive diagnostic test",
            "ping_count": 10,
            "mtr_count": 10,
            "skip_speedtest": False,
            "skip_dns": False,
            "skip_mtr": False,
        },
    },
    "alerts": {
        "enabled": False,
        "channels": [],
    },
    "prometheus": {
        "enabled": False,
        "port": 9101,
    },
}

# Config search paths (in order of priority)
CONFIG_SEARCH_PATHS = [
    "./nettest.yml",
    "./nettest.yaml",
    os.path.expanduser("~/.config/nettest/config.yml"),
    os.path.expanduser("~/.config/nettest/config.yaml"),
]


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries, with override taking precedence.

    Args:
        base: Base dictionary (defaults)
        override: Override dictionary (user config)

    Returns:
        New dictionary with merged values
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(
    config_path: Optional[str] = None,
    quiet: bool = False,
    console: Optional[Any] = None
) -> dict:
    """
    Load configuration from YAML file with fallback to defaults.

    Search order:
    1. Explicit --config path (if provided)
    2. ./nettest.yml or ./nettest.yaml (local directory)
    3. ~/.config/nettest/config.yml or config.yaml (user config)
    4. Built-in defaults

    Args:
        config_path: Explicit path to config file
        quiet: Suppress warning messages
        console: Rich console for output (optional)

    Returns:
        Merged configuration dict
    """
    config = DEFAULT_CONFIG.copy()

    # Helper for printing warnings
    def warn(msg: str) -> None:
        if not quiet:
            if console:
                console.print(f"[yellow]{msg}[/yellow]")
            else:
                print(f"Warning: {msg}")

    def info(msg: str) -> None:
        if not quiet:
            if console:
                console.print(f"[dim]{msg}[/dim]")
            else:
                print(msg)

    if not YAML_AVAILABLE:
        if config_path:
            warn("Warning: pyyaml not installed. Using default config.")
            info("Install with: pip install pyyaml")
        return config

    # Determine which config file to load
    config_file = None

    if config_path:
        # Explicit path provided
        if os.path.exists(config_path):
            config_file = config_path
        else:
            warn(f"Warning: Config file not found: {config_path}")
    else:
        # Search default paths
        for path in CONFIG_SEARCH_PATHS:
            if os.path.exists(path):
                config_file = path
                break

    # Load and merge config
    if config_file:
        try:
            with open(config_file, 'r') as f:
                user_config = yaml.safe_load(f) or {}
            config = deep_merge(DEFAULT_CONFIG, user_config)
            info(f"Loaded config from: {config_file}")
        except yaml.YAMLError as e:
            warn(f"Warning: Error parsing config file: {e}")
        except IOError as e:
            warn(f"Warning: Error reading config file: {e}")

    return config


def get_profile(config: dict, profile_name: str) -> Optional[dict]:
    """
    Get a named test profile from configuration.

    Args:
        config: Full configuration dict
        profile_name: Name of profile to retrieve

    Returns:
        Profile settings dict, or None if not found
    """
    profiles = config.get("profiles", {})
    return profiles.get(profile_name)


def apply_profile(config: dict, profile_name: str) -> dict:
    """
    Apply a named profile's settings to the configuration.

    Args:
        config: Full configuration dict
        profile_name: Name of profile to apply

    Returns:
        Configuration with profile settings applied
    """
    profile = get_profile(config, profile_name)
    if not profile:
        return config

    result = config.copy()

    # Apply profile settings to tests section
    if "ping_count" in profile:
        result["tests"]["ping_count"] = profile["ping_count"]
    if "mtr_count" in profile:
        result["tests"]["mtr_count"] = profile["mtr_count"]
    if "expected_speed" in profile:
        result["tests"]["expected_speed"] = profile["expected_speed"]

    # Apply profile targets if specified
    if "targets" in profile:
        result["targets"] = profile["targets"]

    # Apply profile thresholds if specified
    if "thresholds" in profile:
        result["thresholds"] = deep_merge(result["thresholds"], profile["thresholds"])

    return result


def save_config(config: dict, path: str) -> None:
    """
    Save configuration to YAML file.

    Args:
        config: Configuration dict to save
        path: Path to save config file
    """
    if not YAML_AVAILABLE:
        raise RuntimeError("pyyaml is required to save config files")

    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    with open(path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def list_profiles(config: dict) -> list:
    """
    List available profile names.

    Args:
        config: Full configuration dict

    Returns:
        List of profile names
    """
    return list(config.get("profiles", {}).keys())
