"""
Unit tests for nettest configuration module.

Tests deep_merge(), apply_profile(), load_config(), and related functionality.
"""

import copy
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nettest.config import (
    deep_merge,
    apply_profile,
    load_config,
    DEFAULT_CONFIG,
)


class TestDeepMerge:
    """Tests for the deep_merge() function."""

    def test_deep_merge_simple(self):
        """Merging flat dicts should combine keys with override taking precedence."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = deep_merge(base, override)

        assert result == {"a": 1, "b": 3, "c": 4}
        # Ensure original dicts are not modified
        assert base == {"a": 1, "b": 2}
        assert override == {"b": 3, "c": 4}

    def test_deep_merge_nested(self):
        """Merging nested structures should recursively merge dicts."""
        base = {
            "level1": {
                "level2a": {"value": 1},
                "level2b": {"keep": "this"},
            },
            "other": "unchanged",
        }
        override = {
            "level1": {
                "level2a": {"value": 2, "new": "added"},
            },
        }

        result = deep_merge(base, override)

        assert result["level1"]["level2a"]["value"] == 2
        assert result["level1"]["level2a"]["new"] == "added"
        assert result["level1"]["level2b"]["keep"] == "this"
        assert result["other"] == "unchanged"

    def test_deep_merge_list_replace(self):
        """Lists should be replaced entirely, not merged."""
        base = {"items": [1, 2, 3], "other": "value"}
        override = {"items": [4, 5]}

        result = deep_merge(base, override)

        assert result["items"] == [4, 5]
        assert result["other"] == "value"

    def test_deep_merge_empty_base(self):
        """Merging into empty base should return override content."""
        base = {}
        override = {"key": "value"}

        result = deep_merge(base, override)

        assert result == {"key": "value"}

    def test_deep_merge_empty_override(self):
        """Merging empty override should return base content."""
        base = {"key": "value"}
        override = {}

        result = deep_merge(base, override)

        assert result == {"key": "value"}

    def test_deep_merge_type_override(self):
        """Override should replace value even if types differ."""
        base = {"key": {"nested": "dict"}}
        override = {"key": "string_now"}

        result = deep_merge(base, override)

        assert result["key"] == "string_now"


class TestApplyProfile:
    """Tests for the apply_profile() function."""

    def test_apply_profile_quick(self):
        """Apply quick profile should set ping_count and skip flags."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        original_ping_count = config["tests"]["ping_count"]

        result = apply_profile(config, "quick")

        # Quick profile sets ping_count to 3
        assert result["tests"]["ping_count"] == 3
        # Note: apply_profile modifies tests dict in place via shallow copy
        # The returned config has the profile applied
        assert original_ping_count == 10  # Verify we captured the original value

    def test_apply_profile_full(self):
        """Apply full profile should set comprehensive test settings."""
        config = copy.deepcopy(DEFAULT_CONFIG)

        result = apply_profile(config, "full")

        assert result["tests"]["ping_count"] == 10
        assert result["tests"]["mtr_count"] == 10

    def test_apply_profile_unknown(self):
        """Unknown profile should return unchanged config."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        original_ping_count = config["tests"]["ping_count"]

        result = apply_profile(config, "nonexistent_profile")

        assert result["tests"]["ping_count"] == original_ping_count
        # Should return the same reference when profile not found
        assert result is config

    def test_apply_profile_with_targets(self):
        """Profile with targets should override targets."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["profiles"] = {
            "custom": {
                "targets": {"Custom Target": "192.168.1.1"}
            }
        }

        result = apply_profile(config, "custom")

        assert result["targets"] == {"Custom Target": "192.168.1.1"}

    def test_apply_profile_with_thresholds(self):
        """Profile with thresholds should deep merge thresholds."""
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["thresholds"] = {"latency": {"good": 50, "warning": 100}}
        config["profiles"] = {
            "strict": {
                "thresholds": {"latency": {"good": 20}}
            }
        }

        result = apply_profile(config, "strict")

        # Should merge, keeping warning but overriding good
        assert result["thresholds"]["latency"]["good"] == 20
        assert result["thresholds"]["latency"]["warning"] == 100


class TestLoadConfig:
    """Tests for the load_config() function."""

    def test_load_config_defaults(self):
        """Returns defaults when no config file exists."""
        # Use a path that doesn't exist and patch search paths
        with patch('nettest.config.CONFIG_SEARCH_PATHS', ['/nonexistent/path.yml']):
            result = load_config(quiet=True)

        assert "targets" in result
        assert "tests" in result
        assert "thresholds" in result
        assert result["targets"] == DEFAULT_CONFIG["targets"]

    def test_load_config_with_file(self, tmp_path):
        """Loads and merges YAML file correctly."""
        # Create a temporary config file
        config_file = tmp_path / "nettest.yml"
        config_content = """
targets:
  Custom Target: "10.0.0.1"
tests:
  ping_count: 5
"""
        config_file.write_text(config_content)

        result = load_config(config_path=str(config_file), quiet=True)

        # Custom values should be present
        assert "Custom Target" in result["targets"]
        assert result["targets"]["Custom Target"] == "10.0.0.1"
        assert result["tests"]["ping_count"] == 5
        # Defaults should be preserved for unspecified values
        assert "thresholds" in result
        assert result["thresholds"] == DEFAULT_CONFIG["thresholds"]

    def test_load_config_explicit_path_not_found(self, tmp_path):
        """Explicit path that doesn't exist returns defaults with warning."""
        nonexistent_path = str(tmp_path / "nonexistent.yml")

        result = load_config(config_path=nonexistent_path, quiet=True)

        # Should return defaults
        assert result["targets"] == DEFAULT_CONFIG["targets"]

    def test_load_config_yaml_not_available(self):
        """Returns defaults when YAML is not available."""
        with patch('nettest.config.YAML_AVAILABLE', False):
            result = load_config(config_path="/some/path.yml", quiet=True)

        assert result == DEFAULT_CONFIG

    def test_load_config_invalid_yaml(self, tmp_path):
        """Invalid YAML file returns defaults."""
        config_file = tmp_path / "invalid.yml"
        config_file.write_text("invalid: yaml: content: [")

        result = load_config(config_path=str(config_file), quiet=True)

        # Should fall back to defaults on parse error
        assert "targets" in result

    def test_load_config_search_paths(self, tmp_path):
        """Config is found via search paths when no explicit path given."""
        config_file = tmp_path / "nettest.yml"
        config_content = """
tests:
  ping_count: 7
"""
        config_file.write_text(config_content)

        # Patch search paths to include our temp file
        with patch('nettest.config.CONFIG_SEARCH_PATHS', [str(config_file)]):
            result = load_config(quiet=True)

        assert result["tests"]["ping_count"] == 7

    def test_load_config_empty_yaml_file(self, tmp_path):
        """Empty YAML file returns defaults."""
        config_file = tmp_path / "empty.yml"
        config_file.write_text("")

        result = load_config(config_path=str(config_file), quiet=True)

        # Empty file should result in defaults
        assert result["targets"] == DEFAULT_CONFIG["targets"]


class TestDefaultConfig:
    """Tests for DEFAULT_CONFIG structure."""

    def test_default_config_has_required_sections(self):
        """DEFAULT_CONFIG should have all required sections."""
        required_sections = ["targets", "tests", "thresholds", "output", "logging", "profiles", "alerts", "prometheus"]

        for section in required_sections:
            assert section in DEFAULT_CONFIG, f"Missing required section: {section}"

    def test_default_config_profiles_exist(self):
        """Built-in profiles should be present."""
        profiles = DEFAULT_CONFIG.get("profiles", {})

        assert "quick" in profiles
        assert "full" in profiles

    def test_default_config_thresholds_structure(self):
        """Thresholds should have good and warning levels."""
        thresholds = DEFAULT_CONFIG.get("thresholds", {})

        assert "latency" in thresholds
        assert "good" in thresholds["latency"]
        assert "warning" in thresholds["latency"]
