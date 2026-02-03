"""
Pytest fixtures for nettest unit tests.

Provides reusable fixtures for mocking command execution, sample outputs,
and configuration management.
"""

import os
import tempfile
from typing import Tuple
from unittest.mock import MagicMock, patch

import pytest

# Try to import yaml for config fixtures
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None
    YAML_AVAILABLE = False


@pytest.fixture
def mock_run_command():
    """
    Fixture that mocks nettest.utils.commands.run_command.

    Returns a MagicMock that can be configured to return specific values.
    The mock is automatically applied to the run_command function.

    Usage:
        def test_ping(mock_run_command):
            mock_run_command.return_value = (0, "ping output", "")
            # ... test code that calls run_command

    Yields:
        MagicMock: The mock object for run_command
    """
    with patch("nettest.utils.commands.run_command") as mock:
        yield mock


@pytest.fixture
def sample_ping_output() -> str:
    """
    Fixture returning sample ping output in Linux format.

    Returns output simulating a successful ping to 8.8.8.8 with 10 packets,
    showing typical latency values and statistics.

    Returns:
        str: Sample Linux ping command output
    """
    return """PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=12.3 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=117 time=11.8 ms
64 bytes from 8.8.8.8: icmp_seq=3 ttl=117 time=13.1 ms
64 bytes from 8.8.8.8: icmp_seq=4 ttl=117 time=12.5 ms
64 bytes from 8.8.8.8: icmp_seq=5 ttl=117 time=11.9 ms
64 bytes from 8.8.8.8: icmp_seq=6 ttl=117 time=14.2 ms
64 bytes from 8.8.8.8: icmp_seq=7 ttl=117 time=12.0 ms
64 bytes from 8.8.8.8: icmp_seq=8 ttl=117 time=11.7 ms
64 bytes from 8.8.8.8: icmp_seq=9 ttl=117 time=13.4 ms
64 bytes from 8.8.8.8: icmp_seq=10 ttl=117 time=12.1 ms

--- 8.8.8.8 ping statistics ---
10 packets transmitted, 10 received, 0% packet loss, time 9012ms
rtt min/avg/max/mdev = 11.700/12.500/14.200/0.756 ms"""


@pytest.fixture
def sample_ping_output_with_loss() -> str:
    """
    Fixture returning sample ping output with packet loss.

    Returns output simulating a ping with 20% packet loss.

    Returns:
        str: Sample Linux ping command output with packet loss
    """
    return """PING 192.168.1.1 (192.168.1.1) 56(84) bytes of data.
64 bytes from 192.168.1.1: icmp_seq=1 ttl=64 time=1.23 ms
64 bytes from 192.168.1.1: icmp_seq=2 ttl=64 time=1.45 ms
64 bytes from 192.168.1.1: icmp_seq=4 ttl=64 time=2.10 ms
64 bytes from 192.168.1.1: icmp_seq=5 ttl=64 time=1.89 ms

--- 192.168.1.1 ping statistics ---
5 packets transmitted, 4 received, 20% packet loss, time 4005ms
rtt min/avg/max/mdev = 1.230/1.667/2.100/0.345 ms"""


@pytest.fixture
def sample_mtr_output() -> str:
    """
    Fixture returning sample MTR output in report format.

    Returns output simulating an MTR trace to 8.8.8.8 showing
    multiple hops with varying latencies and packet loss.

    Returns:
        str: Sample MTR report output
    """
    return """Start: 2024-01-15T10:30:00+0000
HOST: testhost                    Loss%   Snt   Last   Avg  Best  Wrst StDev
  1. 192.168.1.1                   0.0%    10    1.2    1.3   1.0   2.1   0.3
  2. 10.0.0.1                      0.0%    10    8.5    9.2   7.8  12.3   1.4
  3. 203.0.113.1                   0.0%    10   15.3   16.1  14.2  19.8   1.8
  4. 198.51.100.1                 10.0%    10   22.4   24.5  20.1  35.6   4.2
  5. 172.16.0.1                    0.0%    10   25.8   26.3  24.5  30.2   1.9
  6. 8.8.8.8                       0.0%    10   28.1   29.4  26.8  34.5   2.3"""


@pytest.fixture
def sample_mtr_json_output() -> str:
    """
    Fixture returning sample MTR output in JSON format.

    Returns:
        str: Sample MTR JSON output
    """
    return """{
  "report": {
    "mtr": {
      "src": "testhost",
      "dst": "8.8.8.8",
      "tos": 0,
      "psize": "64",
      "bitpattern": "0x00",
      "tests": 10
    },
    "hubs": [
      {"count": 1, "host": "192.168.1.1", "Loss%": 0.0, "Snt": 10, "Last": 1.2, "Avg": 1.3, "Best": 1.0, "Wrst": 2.1, "StDev": 0.3},
      {"count": 2, "host": "10.0.0.1", "Loss%": 0.0, "Snt": 10, "Last": 8.5, "Avg": 9.2, "Best": 7.8, "Wrst": 12.3, "StDev": 1.4},
      {"count": 3, "host": "203.0.113.1", "Loss%": 0.0, "Snt": 10, "Last": 15.3, "Avg": 16.1, "Best": 14.2, "Wrst": 19.8, "StDev": 1.8},
      {"count": 4, "host": "198.51.100.1", "Loss%": 10.0, "Snt": 10, "Last": 22.4, "Avg": 24.5, "Best": 20.1, "Wrst": 35.6, "StDev": 4.2},
      {"count": 5, "host": "172.16.0.1", "Loss%": 0.0, "Snt": 10, "Last": 25.8, "Avg": 26.3, "Best": 24.5, "Wrst": 30.2, "StDev": 1.9},
      {"count": 6, "host": "8.8.8.8", "Loss%": 0.0, "Snt": 10, "Last": 28.1, "Avg": 29.4, "Best": 26.8, "Wrst": 34.5, "StDev": 2.3}
    ]
  }
}"""


@pytest.fixture
def sample_config() -> dict:
    """
    Fixture returning a sample configuration dictionary.

    Returns a configuration suitable for testing, with reasonable
    defaults for all major config sections.

    Returns:
        dict: Sample nettest configuration
    """
    return {
        "targets": {
            "Google DNS": "8.8.8.8",
            "Cloudflare DNS": "1.1.1.1",
            "Local Gateway": "192.168.1.1",
        },
        "tests": {
            "ping_count": 5,
            "mtr_count": 5,
            "expected_speed": 100,
        },
        "thresholds": {
            "latency": {"good": 50, "warning": 100},
            "jitter": {"good": 15, "warning": 30},
            "packet_loss": {"good": 0, "warning": 2},
            "download_pct": {"good": 80, "warning": 50},
        },
        "output": {
            "directory": "/tmp/nettest-output",
            "open_browser": False,
        },
        "logging": {
            "enabled": False,
            "file": "/tmp/nettest.log",
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


@pytest.fixture
def temp_config_file(sample_config):
    """
    Fixture that creates a temporary YAML config file.

    Creates a temporary file containing the sample config in YAML format.
    The file is automatically cleaned up after the test.

    Requires pyyaml to be installed; skips the test if unavailable.

    Args:
        sample_config: The sample_config fixture

    Yields:
        str: Path to the temporary config file
    """
    if not YAML_AVAILABLE:
        pytest.skip("pyyaml not installed")

    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.yml',
        delete=False
    ) as f:
        yaml.dump(sample_config, f, default_flow_style=False)
        config_path = f.name

    yield config_path

    # Cleanup
    if os.path.exists(config_path):
        os.unlink(config_path)


@pytest.fixture
def mock_run_command_success(mock_run_command, sample_ping_output):
    """
    Fixture that configures mock_run_command to return successful ping output.

    Convenience fixture combining mock_run_command with sample_ping_output.

    Args:
        mock_run_command: The mock_run_command fixture
        sample_ping_output: The sample_ping_output fixture

    Returns:
        MagicMock: Configured mock for successful ping
    """
    mock_run_command.return_value = (0, sample_ping_output, "")
    return mock_run_command


@pytest.fixture
def mock_run_command_failure(mock_run_command):
    """
    Fixture that configures mock_run_command to return a command failure.

    Simulates a DNS resolution failure error.

    Args:
        mock_run_command: The mock_run_command fixture

    Returns:
        MagicMock: Configured mock for failed command
    """
    mock_run_command.return_value = (
        1,
        "",
        "ping: unknown host example.invalid: Name or service not known"
    )
    return mock_run_command


@pytest.fixture
def mock_run_command_timeout(mock_run_command):
    """
    Fixture that configures mock_run_command to return a timeout error.

    Args:
        mock_run_command: The mock_run_command fixture

    Returns:
        MagicMock: Configured mock for timeout
    """
    mock_run_command.return_value = (-1, "", "Command timed out")
    return mock_run_command
