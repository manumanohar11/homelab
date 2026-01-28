#!/usr/bin/env python3
"""
Network Testing Tool
Runs comprehensive network tests and displays results in terminal and HTML report.

Features:
- Ping latency and packet loss testing
- Speed test (download/upload)
- DNS resolution timing
- MTR route analysis
- TCP port connectivity
- HTTP/HTTPS latency
- Diagnostic analysis with recommendations
- Multiple output formats (terminal, HTML, JSON)
- YAML configuration support
- Structured JSON logging for Promtail/Loki
"""

# ============================================================================
# IMPORTS
# ============================================================================

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
    from rich.prompt import Prompt, Confirm
    from rich.live import Live
    from rich.layout import Layout
except ImportError:
    print("Error: 'rich' library is required. Install with: pip install rich")
    sys.exit(1)

# Optional YAML support for config files
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

# Default Configuration
DEFAULT_CONFIG = {
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
        "directory": "/tmp",
        "open_browser": True,
    },
    "logging": {
        "enabled": False,
        "file": "/tmp/nettest.log",
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
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: Optional[str] = None, quiet: bool = False) -> dict:
    """
    Load configuration from YAML file with fallback to defaults.

    Search order:
    1. Explicit --config path (if provided)
    2. ./nettest.yml or ./nettest.yaml (local directory)
    3. ~/.config/nettest/config.yml or config.yaml (user config)
    4. Built-in defaults

    Returns merged configuration dict.
    """
    config = DEFAULT_CONFIG.copy()

    if not YAML_AVAILABLE:
        if config_path:
            if not quiet:
                console.print("[yellow]Warning: pyyaml not installed. Using default config.[/yellow]")
                console.print("[dim]Install with: pip install pyyaml[/dim]")
        return config

    # Determine which config file to load
    config_file = None

    if config_path:
        # Explicit path provided
        if os.path.exists(config_path):
            config_file = config_path
        else:
            if not quiet:
                console.print(f"[yellow]Warning: Config file not found: {config_path}[/yellow]")
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
            if not quiet:
                console.print(f"[dim]Loaded config from: {config_file}[/dim]")
        except yaml.YAMLError as e:
            if not quiet:
                console.print(f"[yellow]Warning: Error parsing config file: {e}[/yellow]")
        except IOError as e:
            if not quiet:
                console.print(f"[yellow]Warning: Error reading config file: {e}[/yellow]")

    return config


class JsonLogger:
    """Structured JSON logger for Promtail/Loki integration."""

    def __init__(self, log_file: Optional[str] = None, enabled: bool = False):
        self.log_file = log_file
        self.enabled = enabled and log_file is not None
        self._file_handle = None

    def _write(self, entry: dict) -> None:
        """Write a log entry to the log file."""
        if not self.enabled:
            return

        entry["timestamp"] = datetime.now().isoformat()

        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + "\n")
        except IOError:
            pass  # Silently fail if we can't write to log

    def log_start(self, targets: list[str], profile: Optional[str] = None) -> None:
        """Log test session start."""
        self._write({
            "level": "info",
            "event": "session_start",
            "targets": targets,
            "profile": profile,
        })

    def log_ping_result(self, result) -> None:
        """Log a ping test result."""
        self._write({
            "level": "info" if result.success else "warning",
            "event": "ping_result",
            "target": result.target,
            "target_name": result.target_name,
            "success": result.success,
            "avg_ms": result.avg_ms,
            "min_ms": result.min_ms,
            "max_ms": result.max_ms,
            "jitter_ms": result.jitter_ms,
            "packet_loss": result.packet_loss,
            "error": result.error or None,
        })

    def log_speedtest_result(self, result) -> None:
        """Log a speed test result."""
        self._write({
            "level": "info" if result.success else "warning",
            "event": "speedtest_result",
            "success": result.success,
            "download_mbps": result.download_mbps,
            "upload_mbps": result.upload_mbps,
            "ping_ms": result.ping_ms,
            "server": result.server,
            "error": result.error or None,
        })

    def log_dns_result(self, result) -> None:
        """Log a DNS test result."""
        self._write({
            "level": "info" if result.success else "warning",
            "event": "dns_result",
            "target": result.target,
            "success": result.success,
            "resolution_time_ms": result.resolution_time_ms,
            "resolved_ip": result.resolved_ip,
            "error": result.error or None,
        })

    def log_mtr_result(self, result) -> None:
        """Log an MTR result."""
        self._write({
            "level": "info" if result.success else "warning",
            "event": "mtr_result",
            "target": result.target,
            "target_name": result.target_name,
            "success": result.success,
            "hop_count": len(result.hops),
            "error": result.error or None,
        })

    def log_diagnostic(self, diagnostic) -> None:
        """Log diagnostic analysis."""
        self._write({
            "level": "warning" if diagnostic.category != "none" else "info",
            "event": "diagnostic",
            "category": diagnostic.category,
            "confidence": diagnostic.confidence,
            "summary": diagnostic.summary,
            "details": diagnostic.details,
        })

    def log_end(self, success: bool = True) -> None:
        """Log test session end."""
        self._write({
            "level": "info",
            "event": "session_end",
            "success": success,
        })


# Global logger instance (will be configured in main())
json_logger = JsonLogger()


# Legacy compatibility - these will be set from config in main()
TARGET_SERVERS = DEFAULT_CONFIG["targets"]
PING_COUNT = DEFAULT_CONFIG["tests"]["ping_count"]
MTR_COUNT = DEFAULT_CONFIG["tests"]["mtr_count"]
THRESHOLDS = DEFAULT_CONFIG["thresholds"]


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class PingResult:
    target: str
    target_name: str
    min_ms: float = 0.0
    avg_ms: float = 0.0
    max_ms: float = 0.0
    jitter_ms: float = 0.0
    packet_loss: float = 0.0
    success: bool = False
    error: str = ""
    samples: list = field(default_factory=list)


@dataclass
class SpeedTestResult:
    download_mbps: float = 0.0
    upload_mbps: float = 0.0
    ping_ms: float = 0.0
    server: str = ""
    success: bool = False
    error: str = ""


@dataclass
class DnsResult:
    target: str
    resolution_time_ms: float = 0.0
    resolved_ip: str = ""
    success: bool = False
    error: str = ""


@dataclass
class MtrHop:
    hop_number: int
    host: str
    loss_pct: float
    sent: int
    avg_ms: float
    best_ms: float
    worst_ms: float


@dataclass
class MtrResult:
    target: str
    target_name: str
    hops: list = field(default_factory=list)
    success: bool = False
    error: str = ""


@dataclass
class DiagnosticResult:
    """Diagnostic analysis of where problems might be occurring."""
    category: str  # "local", "isp", "internet", "target", "none"
    confidence: str  # "high", "medium", "low"
    summary: str
    details: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)


@dataclass
class PortResult:
    """Result of a TCP port connectivity test."""
    host: str
    port: int
    open: bool = False
    response_time_ms: float = 0.0
    error: str = ""


@dataclass
class HttpResult:
    """Result of an HTTP/HTTPS latency test."""
    url: str
    status_code: int = 0
    response_time_ms: float = 0.0
    success: bool = False
    error: str = ""


console = Console()


# ============================================================================
# UTILITY FUNCTIONS & DEPENDENCY CHECKING
# ============================================================================

# Tool requirements with installation instructions
REQUIRED_TOOLS = {
    "ping": {
        "required": True,
        "description": "Basic connectivity test",
        "install": {
            "debian": "Usually pre-installed. If missing: sudo apt install iputils-ping",
            "fedora": "Usually pre-installed. If missing: sudo dnf install iputils",
        }
    },
    "dig": {
        "required": False,
        "description": "DNS resolution testing",
        "install": {
            "debian": "sudo apt install dnsutils",
            "fedora": "sudo dnf install bind-utils",
        }
    },
    "mtr": {
        "required": False,
        "description": "Route analysis and traceroute",
        "install": {
            "debian": "sudo apt install mtr-tiny",
            "fedora": "sudo dnf install mtr",
        }
    },
    "speedtest-cli": {
        "required": False,
        "description": "Internet speed testing",
        "install": {
            "debian": "sudo apt install speedtest-cli  # or: pip install speedtest-cli",
            "fedora": "pip install speedtest-cli",
        },
        "alternatives": ["speedtest"]
    },
}


def check_dependencies(quiet: bool = False) -> dict[str, bool]:
    """
    Check if required tools are installed.

    Returns dict of tool_name -> is_available.
    Displays status table if not quiet.
    """
    results = {}

    for tool, info in REQUIRED_TOOLS.items():
        # Check main tool
        available = shutil.which(tool) is not None

        # Check alternatives if main tool not found
        if not available and "alternatives" in info:
            for alt in info["alternatives"]:
                if shutil.which(alt) is not None:
                    available = True
                    break

        results[tool] = available

    if not quiet:
        table = Table(title="Tool Availability", box=box.ROUNDED)
        table.add_column("Tool", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Purpose", style="dim")

        for tool, info in REQUIRED_TOOLS.items():
            available = results[tool]
            status = "[green]✓ Available[/green]" if available else "[red]✗ Missing[/red]"
            required_marker = " [yellow](required)[/yellow]" if info["required"] else ""
            table.add_row(tool, status, info["description"] + required_marker)

        console.print(table)
        console.print()

        # Show install instructions for missing tools
        missing = [t for t, available in results.items() if not available]
        if missing:
            console.print("[yellow]Missing tools - install instructions:[/yellow]")
            for tool in missing:
                info = REQUIRED_TOOLS[tool]
                console.print(f"\n[bold]{tool}[/bold]:")
                console.print(f"  Debian/Ubuntu: {info['install']['debian']}")
                console.print(f"  Fedora/RHEL:   {info['install']['fedora']}")
            console.print()

    return results


def evaluate_metric(value: float, metric: str, reverse: bool = False) -> tuple[str, str]:
    """
    Evaluate a metric value against thresholds.

    Args:
        value: The metric value to evaluate
        metric: The metric name (key in THRESHOLDS)
        reverse: If True, higher values are better (e.g., download speed percentage)

    Returns:
        tuple of (status, color) where:
        - status: "good", "warning", or "bad" (for CSS classes)
        - color: "green", "yellow", or "red" (for Rich terminal output)
    """
    thresholds = THRESHOLDS.get(metric, {"good": 50, "warning": 100})

    if reverse:
        # Higher is better (e.g., download speed percentage)
        if value >= thresholds["good"]:
            return ("good", "green")
        elif value >= thresholds["warning"]:
            return ("warning", "yellow")
        else:
            return ("bad", "red")
    else:
        # Lower is better (e.g., latency, jitter, packet loss)
        if value <= thresholds["good"]:
            return ("good", "green")
        elif value <= thresholds["warning"]:
            return ("warning", "yellow")
        else:
            return ("bad", "red")


def get_status_color(value: float, metric: str, reverse: bool = False) -> str:
    """Get color based on threshold. reverse=True means lower is worse (higher is better)."""
    _, color = evaluate_metric(value, metric, reverse)
    return color


def get_status_class(value: float, metric: str, reverse: bool = False) -> str:
    """Get CSS class based on threshold. reverse=True means lower is worse (higher is better)."""
    status, _ = evaluate_metric(value, metric, reverse)
    return status


# ============================================================================
# COMMAND RUNNERS (Test Execution)
# ============================================================================

def run_command(cmd: list, timeout: int = 60) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return -1, "", str(e)


def run_ping_test(target: str, target_name: str, count: int = PING_COUNT) -> PingResult:
    """Run ping test and parse results."""
    result = PingResult(target=target, target_name=target_name)

    cmd = ["ping", "-c", str(count), "-W", "2", target]
    exit_code, stdout, stderr = run_command(cmd, timeout=count * 3 + 10)

    if exit_code != 0 and not stdout:
        # Provide actionable error messages
        if "Name or service not known" in stderr or "Temporary failure in name resolution" in stderr:
            result.error = f"DNS resolution failed for '{target}'. Check your DNS settings or try an IP address."
        elif "Network is unreachable" in stderr:
            result.error = "Network unreachable. Check your network connection and default gateway."
        elif "Operation not permitted" in stderr:
            result.error = "Permission denied. Try running with sudo or check firewall settings."
        elif "Command timed out" in stderr:
            result.error = f"Ping timed out after {count * 3 + 10}s. Host may be down or blocking ICMP."
        elif "Command not found" in stderr:
            result.error = "ping not found. Install: sudo apt install iputils-ping"
        else:
            result.error = stderr or "Ping failed - check network connectivity"
        return result

    # Parse individual ping times for jitter calculation
    time_pattern = r"time[=<](\d+\.?\d*)\s*ms"
    times = [float(m) for m in re.findall(time_pattern, stdout)]
    result.samples = times

    # Parse summary statistics
    stats_pattern = r"(\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*)\s*ms"
    stats_match = re.search(stats_pattern, stdout)

    if stats_match:
        result.min_ms = float(stats_match.group(1))
        result.avg_ms = float(stats_match.group(2))
        result.max_ms = float(stats_match.group(3))
        result.jitter_ms = float(stats_match.group(4))  # mdev is essentially jitter
        result.success = True
    elif times:
        # Calculate manually if summary not found
        result.min_ms = min(times)
        result.avg_ms = sum(times) / len(times)
        result.max_ms = max(times)
        # Calculate jitter as average deviation
        if len(times) > 1:
            result.jitter_ms = sum(abs(times[i] - times[i-1]) for i in range(1, len(times))) / (len(times) - 1)
        result.success = True

    # Parse packet loss
    loss_pattern = r"(\d+)% packet loss"
    loss_match = re.search(loss_pattern, stdout)
    if loss_match:
        result.packet_loss = float(loss_match.group(1))

    return result


def run_speedtest() -> SpeedTestResult:
    """Run speedtest using speedtest-cli."""
    result = SpeedTestResult()

    # Try speedtest-cli first
    cmd = ["speedtest-cli", "--json"]
    exit_code, stdout, stderr = run_command(cmd, timeout=120)

    if exit_code == 0 and stdout:
        try:
            data = json.loads(stdout)
            result.download_mbps = data.get("download", 0) / 1_000_000  # Convert to Mbps
            result.upload_mbps = data.get("upload", 0) / 1_000_000
            result.ping_ms = data.get("ping", 0)
            result.server = data.get("server", {}).get("sponsor", "Unknown")
            result.success = True
            return result
        except json.JSONDecodeError:
            pass

    # Try alternative: speedtest (ookla official)
    cmd = ["speedtest", "--format=json"]
    exit_code, stdout, stderr = run_command(cmd, timeout=120)

    if exit_code == 0 and stdout:
        try:
            data = json.loads(stdout)
            result.download_mbps = data.get("download", {}).get("bandwidth", 0) * 8 / 1_000_000
            result.upload_mbps = data.get("upload", {}).get("bandwidth", 0) * 8 / 1_000_000
            result.ping_ms = data.get("ping", {}).get("latency", 0)
            result.server = data.get("server", {}).get("name", "Unknown")
            result.success = True
            return result
        except json.JSONDecodeError:
            pass

    # Provide actionable error message
    result.error = (
        "Speed test tools not found.\n"
        "  Install (Debian/Ubuntu): sudo apt install speedtest-cli\n"
        "  Install (Fedora/RHEL): pip install speedtest-cli\n"
        "  Or use Ookla official: https://www.speedtest.net/apps/cli"
    )
    return result


def run_dns_test(target: str) -> DnsResult:
    """Test DNS resolution time using dig."""
    result = DnsResult(target=target)

    # Skip IP addresses
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", target):
        result.success = True
        result.resolved_ip = target
        result.resolution_time_ms = 0
        return result

    cmd = ["dig", "+noall", "+answer", "+stats", target]
    exit_code, stdout, stderr = run_command(cmd, timeout=10)

    if exit_code != 0:
        # Provide actionable error messages
        if "Command not found" in stderr:
            result.error = (
                "dig not found.\n"
                "  Install (Debian/Ubuntu): sudo apt install dnsutils\n"
                "  Install (Fedora/RHEL): sudo dnf install bind-utils"
            )
        elif "connection timed out" in stderr.lower():
            result.error = f"DNS query timed out for '{target}'. Check your DNS server connectivity."
        elif "SERVFAIL" in stderr:
            result.error = f"DNS server failure for '{target}'. Your DNS server may be misconfigured."
        elif "NXDOMAIN" in stderr:
            result.error = f"Domain '{target}' does not exist (NXDOMAIN)."
        else:
            result.error = stderr or "DNS lookup failed - check your DNS settings"
        return result

    # Parse query time
    time_pattern = r";; Query time: (\d+) msec"
    time_match = re.search(time_pattern, stdout)
    if time_match:
        result.resolution_time_ms = float(time_match.group(1))

    # Parse resolved IP
    ip_pattern = r"\bIN\s+A\s+(\d+\.\d+\.\d+\.\d+)"
    ip_match = re.search(ip_pattern, stdout)
    if ip_match:
        result.resolved_ip = ip_match.group(1)

    result.success = True
    return result


def check_tcp_port(host: str, port: int, timeout: float = 5.0) -> PortResult:
    """
    Test TCP connectivity to a specific port.

    Args:
        host: Hostname or IP address
        port: Port number to test
        timeout: Connection timeout in seconds

    Returns:
        PortResult with connection status and response time
    """
    result = PortResult(host=host, port=port)

    try:
        start_time = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        # Attempt connection
        error_code = sock.connect_ex((host, port))
        end_time = time.perf_counter()

        result.response_time_ms = (end_time - start_time) * 1000

        if error_code == 0:
            result.open = True
        else:
            result.open = False
            result.error = f"Connection refused (error code: {error_code})"

        sock.close()

    except socket.timeout:
        result.error = f"Connection timed out after {timeout}s"
    except socket.gaierror as e:
        result.error = f"DNS resolution failed: {e}"
    except OSError as e:
        result.error = f"Connection error: {e}"

    return result


def check_tcp_ports(host: str, ports: list[int], timeout: float = 5.0) -> list[PortResult]:
    """
    Test TCP connectivity to multiple ports on a host.

    Args:
        host: Hostname or IP address
        ports: List of port numbers to test
        timeout: Connection timeout in seconds per port

    Returns:
        List of PortResult for each port
    """
    results = []
    for port in ports:
        result = check_tcp_port(host, port, timeout)
        results.append(result)
    return results


def measure_http_latency(url: str, timeout: float = 10.0) -> HttpResult:
    """
    Measure HTTP/HTTPS response time.

    Uses urllib to make a HEAD request and measure response time.
    This tests application-layer connectivity, not just ICMP.

    Args:
        url: Full URL (must include http:// or https://)
        timeout: Request timeout in seconds

    Returns:
        HttpResult with status code and response time
    """
    import urllib.request
    import urllib.error

    result = HttpResult(url=url)

    # Ensure URL has a scheme
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        result.url = url

    try:
        start_time = time.perf_counter()

        request = urllib.request.Request(url, method='HEAD')
        request.add_header('User-Agent', 'nettest/1.0')

        with urllib.request.urlopen(request, timeout=timeout) as response:
            end_time = time.perf_counter()
            result.status_code = response.status
            result.response_time_ms = (end_time - start_time) * 1000
            result.success = 200 <= response.status < 400

    except urllib.error.HTTPError as e:
        end_time = time.perf_counter()
        result.status_code = e.code
        result.response_time_ms = (end_time - start_time) * 1000
        result.error = f"HTTP {e.code}: {e.reason}"
        result.success = False

    except urllib.error.URLError as e:
        result.error = f"Connection failed: {e.reason}"
        result.success = False

    except Exception as e:
        result.error = f"Request failed: {str(e)}"
        result.success = False

    return result


# ============================================================================
# DIAGNOSTIC ANALYSIS
# ============================================================================

def diagnose_network(
    ping_results: list[PingResult],
    speedtest_result: SpeedTestResult,
    mtr_results: list[MtrResult],
    expected_speed: float
) -> DiagnosticResult:
    """Analyze test results to determine where problems are occurring."""

    issues = []
    local_issues = []
    isp_issues = []
    internet_issues = []
    target_issues = {}  # target_name -> issues

    # Check speedtest results
    if speedtest_result.success:
        dl_pct = (speedtest_result.download_mbps / expected_speed) * 100 if expected_speed > 0 else 100
        if dl_pct < 50:
            isp_issues.append(f"Download speed is only {dl_pct:.0f}% of expected ({speedtest_result.download_mbps:.1f}/{expected_speed} Mbps)")
        elif dl_pct < 80:
            isp_issues.append(f"Download speed is below expected ({dl_pct:.0f}% of {expected_speed} Mbps)")

        if speedtest_result.ping_ms > 100:
            isp_issues.append(f"High latency to speed test server ({speedtest_result.ping_ms:.0f}ms)")
    else:
        issues.append("Speed test failed - cannot assess bandwidth")

    # Analyze ping results by target
    successful_pings = [p for p in ping_results if p.success]
    failed_pings = [p for p in ping_results if not p.success]

    # Check if all pings failed (likely local/ISP issue)
    if len(failed_pings) == len(ping_results):
        local_issues.append("All ping tests failed - check your network connection")
    elif failed_pings:
        for p in failed_pings:
            target_issues.setdefault(p.target_name, []).append(f"Ping failed: {p.error}")

    # Analyze successful pings
    high_latency_all = True
    high_loss_all = True
    high_jitter_all = True

    for p in successful_pings:
        is_high_latency = p.avg_ms > THRESHOLDS["latency"]["warning"]
        is_high_loss = p.packet_loss > THRESHOLDS["packet_loss"]["warning"]
        is_high_jitter = p.jitter_ms > THRESHOLDS["jitter"]["warning"]

        if not is_high_latency:
            high_latency_all = False
        if not is_high_loss:
            high_loss_all = False
        if not is_high_jitter:
            high_jitter_all = False

        # Target-specific issues
        if is_high_latency or is_high_loss or is_high_jitter:
            target_issue_list = target_issues.setdefault(p.target_name, [])
            if is_high_latency:
                target_issue_list.append(f"High latency ({p.avg_ms:.0f}ms)")
            if is_high_loss:
                target_issue_list.append(f"Packet loss ({p.packet_loss:.1f}%)")
            if is_high_jitter:
                target_issue_list.append(f"High jitter ({p.jitter_ms:.1f}ms)")

    # If all successful pings have issues, it's likely ISP/local
    if successful_pings:
        if high_latency_all:
            isp_issues.append("High latency to all tested servers")
        if high_loss_all:
            isp_issues.append("Packet loss to all tested servers")
        if high_jitter_all:
            isp_issues.append("High jitter (unstable connection) to all servers")

    # Analyze MTR results to pinpoint where problems start
    for mtr in mtr_results:
        if not mtr.success or not mtr.hops:
            continue

        first_problem_hop = None
        for i, hop in enumerate(mtr.hops):
            if hop.loss_pct > THRESHOLDS["packet_loss"]["warning"] or hop.avg_ms > THRESHOLDS["latency"]["warning"]:
                first_problem_hop = (i, hop)
                break

        if first_problem_hop:
            hop_num, hop = first_problem_hop
            # First few hops (0-2) are typically local/router
            # Hops 3-6 are typically ISP
            # Later hops are internet backbone/target
            if hop_num <= 2:
                local_issues.append(f"Problems start at hop {hop.hop_number} ({hop.host}) - likely local network/router issue")
            elif hop_num <= 6:
                isp_issues.append(f"Problems start at hop {hop.hop_number} ({hop.host}) - likely ISP issue")
            else:
                internet_issues.append(f"Problems start at hop {hop.hop_number} ({hop.host}) - internet backbone issue")

    # Determine the primary problem category
    category = "none"
    confidence = "low"
    summary = ""
    details = []
    recommendations = []

    if local_issues:
        category = "local"
        confidence = "high" if len(local_issues) > 1 else "medium"
        summary = "Problem appears to be with your local network"
        details = local_issues
        recommendations = [
            "Restart your router/modem",
            "Check Ethernet cable connections",
            "Try connecting via Ethernet instead of WiFi",
            "Check for local network congestion (other devices using bandwidth)",
        ]
    elif isp_issues:
        category = "isp"
        confidence = "high" if len(isp_issues) > 1 else "medium"
        summary = "Problem appears to be with your ISP"
        details = isp_issues
        recommendations = [
            "Contact your ISP to report the issue",
            "Check ISP status page for outages",
            "Try rebooting your modem",
            "Test at different times of day (peak congestion)",
        ]
    elif internet_issues:
        category = "internet"
        confidence = "medium"
        summary = "Problem appears to be with internet backbone/routing"
        details = internet_issues
        recommendations = [
            "This is typically temporary - try again later",
            "Use a VPN to route around the problem",
            "The issue is outside your control",
        ]
    elif target_issues:
        # Check if issues are target-specific
        targets_with_issues = list(target_issues.keys())
        targets_ok = [p.target_name for p in successful_pings if p.target_name not in targets_with_issues]

        if targets_ok:
            category = "target"
            confidence = "high"
            summary = f"Problem appears to be specific to: {', '.join(targets_with_issues)}"
            for target, issue_list in target_issues.items():
                details.extend([f"{target}: {issue}" for issue in issue_list])
            recommendations = [
                "The target servers may be experiencing issues",
                "Check status pages for affected services",
                "Try alternative servers/services",
            ]
        else:
            category = "internet"
            confidence = "low"
            summary = "General connectivity issues detected"
            for target, issue_list in target_issues.items():
                details.extend([f"{target}: {issue}" for issue in issue_list])
            recommendations = [
                "Monitor the situation - it may be temporary",
                "Check if other devices have the same issue",
            ]
    else:
        category = "none"
        confidence = "high"
        summary = "No significant network issues detected"
        details = ["All tests passed within acceptable thresholds"]
        recommendations = ["Your network connection appears healthy"]

    return DiagnosticResult(
        category=category,
        confidence=confidence,
        summary=summary,
        details=details,
        recommendations=recommendations
    )


def run_mtr(target: str, target_name: str, count: int = MTR_COUNT) -> MtrResult:
    """Run mtr and parse results."""
    result = MtrResult(target=target, target_name=target_name)

    # Try JSON output first
    cmd = ["mtr", "--json", "-c", str(count), "--no-dns", target]
    exit_code, stdout, stderr = run_command(cmd, timeout=count * 2 + 30)

    if exit_code == 0 and stdout:
        try:
            data = json.loads(stdout)
            hubs = data.get("report", {}).get("hubs", [])
            for hop in hubs:
                mtr_hop = MtrHop(
                    hop_number=hop.get("count", 0),
                    host=hop.get("host", "???"),
                    loss_pct=hop.get("Loss%", 0),
                    sent=hop.get("Snt", 0),
                    avg_ms=hop.get("Avg", 0),
                    best_ms=hop.get("Best", 0),
                    worst_ms=hop.get("Wrst", 0),
                )
                result.hops.append(mtr_hop)
            result.success = True
            return result
        except json.JSONDecodeError:
            pass

    # Fall back to report mode
    cmd = ["mtr", "--report", "--report-wide", "-c", str(count), "--no-dns", target]
    exit_code, stdout, stderr = run_command(cmd, timeout=count * 2 + 30)

    if exit_code != 0:
        # Provide actionable error messages
        if "Command not found" in stderr:
            result.error = (
                "mtr not found.\n"
                "  Install (Debian/Ubuntu): sudo apt install mtr-tiny\n"
                "  Install (Fedora/RHEL): sudo dnf install mtr"
            )
        elif "Operation not permitted" in stderr or "permission" in stderr.lower():
            result.error = (
                "mtr requires elevated privileges.\n"
                "  Option 1: Run with sudo: sudo python3 nettest.py\n"
                "  Option 2: Set capabilities: sudo setcap cap_net_raw+ep /usr/sbin/mtr"
            )
        elif "Name or service not known" in stderr:
            result.error = f"Cannot resolve '{target}'. Check DNS settings or use IP address."
        else:
            result.error = stderr or "mtr failed - check network connectivity"
        return result

    # Parse report output
    # Format: HOST                             Loss%   Snt   Last   Avg  Best  Wrst StDev
    hop_pattern = r"^\s*(\d+)\.\s+(\S+)\s+(\d+\.?\d*)%\s+(\d+)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)"

    for line in stdout.split('\n'):
        match = re.match(hop_pattern, line)
        if match:
            mtr_hop = MtrHop(
                hop_number=int(match.group(1)),
                host=match.group(2),
                loss_pct=float(match.group(3)),
                sent=int(match.group(4)),
                avg_ms=float(match.group(6)),
                best_ms=float(match.group(7)),
                worst_ms=float(match.group(8)),
            )
            result.hops.append(mtr_hop)

    result.success = len(result.hops) > 0
    if not result.success:
        result.error = (
            "Could not parse mtr output. This may indicate:\n"
            "  - Target is unreachable (100% packet loss on all hops)\n"
            "  - Firewall blocking ICMP/UDP packets\n"
            "  - Incompatible mtr version (try updating mtr)"
        )

    return result


# ============================================================================
# OUTPUT FORMATTERS (Terminal, HTML, JSON)
# ============================================================================

def display_terminal(
    ping_results: list[PingResult],
    speedtest_result: SpeedTestResult,
    dns_results: list[DnsResult],
    mtr_results: list[MtrResult],
    expected_speed: float,
    diagnostic: DiagnosticResult
):
    """Display results in terminal using rich."""

    console.print()
    console.print(Panel.fit(
        "[bold blue]Network Test Results[/bold blue]",
        subtitle=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    console.print()

    # Display Diagnostic Summary First
    category_colors = {
        "none": "green",
        "local": "red",
        "isp": "red",
        "internet": "yellow",
        "target": "yellow",
    }
    category_icons = {
        "none": "[green]OK[/green]",
        "local": "[red]LOCAL[/red]",
        "isp": "[red]ISP[/red]",
        "internet": "[yellow]INTERNET[/yellow]",
        "target": "[yellow]TARGET[/yellow]",
    }
    color = category_colors.get(diagnostic.category, "white")

    diag_text = Text()
    diag_text.append(f"\n{diagnostic.summary}\n\n", style=f"bold {color}")

    if diagnostic.details:
        diag_text.append("Issues Found:\n", style="bold")
        for detail in diagnostic.details:
            diag_text.append(f"  - {detail}\n", style=color)
        diag_text.append("\n")

    if diagnostic.recommendations:
        diag_text.append("Recommendations:\n", style="bold")
        for rec in diagnostic.recommendations:
            diag_text.append(f"  - {rec}\n", style="dim")

    panel_title = f"Diagnosis: {category_icons.get(diagnostic.category, 'UNKNOWN')} ({diagnostic.confidence} confidence)"
    console.print(Panel(diag_text, title=panel_title, border_style=color))
    console.print()

    # Speed Test Results
    console.print("[bold]Speed Test[/bold]")
    if speedtest_result.success:
        speed_table = Table(box=box.ROUNDED)
        speed_table.add_column("Metric", style="cyan")
        speed_table.add_column("Value", justify="right")
        speed_table.add_column("Status", justify="center")

        dl_pct = (speedtest_result.download_mbps / expected_speed) * 100 if expected_speed > 0 else 100
        dl_color = get_status_color(dl_pct, "download_pct", reverse=True)

        speed_table.add_row(
            "Download",
            f"{speedtest_result.download_mbps:.1f} Mbps",
            Text(f"[{dl_color}]●[/{dl_color}] {dl_pct:.0f}% of expected")
        )
        speed_table.add_row(
            "Upload",
            f"{speedtest_result.upload_mbps:.1f} Mbps",
            ""
        )

        ping_color = get_status_color(speedtest_result.ping_ms, "latency")
        speed_table.add_row(
            "Ping",
            f"{speedtest_result.ping_ms:.1f} ms",
            Text(f"[{ping_color}]●[/{ping_color}]")
        )
        speed_table.add_row("Server", speedtest_result.server, "")

        console.print(speed_table)
    else:
        console.print(f"[red]  {speedtest_result.error}[/red]")
    console.print()

    # Latency Results
    console.print("[bold]Latency Tests[/bold]")
    latency_table = Table(box=box.ROUNDED)
    latency_table.add_column("Target", style="cyan")
    latency_table.add_column("Min", justify="right")
    latency_table.add_column("Avg", justify="right")
    latency_table.add_column("Max", justify="right")
    latency_table.add_column("Jitter", justify="right")
    latency_table.add_column("Loss", justify="right")

    for pr in ping_results:
        if pr.success:
            avg_color = get_status_color(pr.avg_ms, "latency")
            jitter_color = get_status_color(pr.jitter_ms, "jitter")
            loss_color = get_status_color(pr.packet_loss, "packet_loss")

            latency_table.add_row(
                pr.target_name,
                f"{pr.min_ms:.1f} ms",
                Text(f"[{avg_color}]{pr.avg_ms:.1f} ms[/{avg_color}]"),
                f"{pr.max_ms:.1f} ms",
                Text(f"[{jitter_color}]{pr.jitter_ms:.1f} ms[/{jitter_color}]"),
                Text(f"[{loss_color}]{pr.packet_loss:.1f}%[/{loss_color}]"),
            )
        else:
            latency_table.add_row(
                pr.target_name,
                "[red]Error[/red]",
                "[red]-[/red]",
                "[red]-[/red]",
                "[red]-[/red]",
                f"[red]{pr.error}[/red]",
            )

    console.print(latency_table)
    console.print()

    # DNS Results
    console.print("[bold]DNS Resolution[/bold]")
    dns_table = Table(box=box.ROUNDED)
    dns_table.add_column("Target", style="cyan")
    dns_table.add_column("Resolved IP")
    dns_table.add_column("Time", justify="right")

    for dr in dns_results:
        if dr.success:
            time_color = get_status_color(dr.resolution_time_ms, "latency")
            dns_table.add_row(
                dr.target,
                dr.resolved_ip or "-",
                Text(f"[{time_color}]{dr.resolution_time_ms:.0f} ms[/{time_color}]") if dr.resolution_time_ms > 0 else "N/A (IP)"
            )
        else:
            dns_table.add_row(dr.target, "[red]Failed[/red]", dr.error)

    console.print(dns_table)
    console.print()

    # MTR Results
    for mtr in mtr_results:
        console.print(f"[bold]Route to {mtr.target_name}[/bold]")
        if mtr.success and mtr.hops:
            mtr_table = Table(box=box.ROUNDED)
            mtr_table.add_column("Hop", justify="right", style="dim")
            mtr_table.add_column("Host")
            mtr_table.add_column("Loss", justify="right")
            mtr_table.add_column("Avg", justify="right")
            mtr_table.add_column("Best", justify="right")
            mtr_table.add_column("Worst", justify="right")

            for hop in mtr.hops:
                loss_color = get_status_color(hop.loss_pct, "packet_loss")
                avg_color = get_status_color(hop.avg_ms, "latency")

                mtr_table.add_row(
                    str(hop.hop_number),
                    hop.host,
                    Text(f"[{loss_color}]{hop.loss_pct:.1f}%[/{loss_color}]"),
                    Text(f"[{avg_color}]{hop.avg_ms:.1f} ms[/{avg_color}]"),
                    f"{hop.best_ms:.1f} ms",
                    f"{hop.worst_ms:.1f} ms",
                )

            console.print(mtr_table)
        else:
            console.print(f"[red]  {mtr.error}[/red]")
        console.print()


def generate_html(
    ping_results: list[PingResult],
    speedtest_result: SpeedTestResult,
    dns_results: list[DnsResult],
    mtr_results: list[MtrResult],
    expected_speed: float,
    output_dir: str,
    diagnostic: DiagnosticResult
) -> str:
    """Generate HTML report with charts."""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Prepare data for charts
    ping_labels = json.dumps([pr.target_name for pr in ping_results if pr.success])
    ping_avg = json.dumps([pr.avg_ms for pr in ping_results if pr.success])
    ping_min = json.dumps([pr.min_ms for pr in ping_results if pr.success])
    ping_max = json.dumps([pr.max_ms for pr in ping_results if pr.success])
    ping_jitter = json.dumps([pr.jitter_ms for pr in ping_results if pr.success])
    ping_loss = json.dumps([pr.packet_loss for pr in ping_results if pr.success])

    # MTR data for first target
    mtr_hops_labels = "[]"
    mtr_hops_latency = "[]"
    mtr_hops_loss = "[]"
    if mtr_results and mtr_results[0].success:
        mtr_hops_labels = json.dumps([f"Hop {h.hop_number}" for h in mtr_results[0].hops])
        mtr_hops_latency = json.dumps([h.avg_ms for h in mtr_results[0].hops])
        mtr_hops_loss = json.dumps([h.loss_pct for h in mtr_results[0].hops])

    # Calculate download percentage
    dl_pct = (speedtest_result.download_mbps / expected_speed) * 100 if expected_speed > 0 and speedtest_result.success else 0

    # Note: get_status_class() is now a module-level function (unified with get_status_color)

    # Build latency table rows
    latency_rows = ""
    for pr in ping_results:
        if pr.success:
            avg_class = get_status_class(pr.avg_ms, "latency")
            jitter_class = get_status_class(pr.jitter_ms, "jitter")
            loss_class = get_status_class(pr.packet_loss, "packet_loss")
            latency_rows += f"""
                <tr>
                    <td>{pr.target_name}</td>
                    <td>{pr.min_ms:.1f} ms</td>
                    <td class="{avg_class}">{pr.avg_ms:.1f} ms</td>
                    <td>{pr.max_ms:.1f} ms</td>
                    <td class="{jitter_class}">{pr.jitter_ms:.1f} ms</td>
                    <td class="{loss_class}">{pr.packet_loss:.1f}%</td>
                </tr>
            """
        else:
            latency_rows += f"""
                <tr>
                    <td>{pr.target_name}</td>
                    <td colspan="5" class="bad">Error: {pr.error}</td>
                </tr>
            """

    # Build DNS table rows
    dns_rows = ""
    for dr in dns_results:
        if dr.success:
            time_class = get_status_class(dr.resolution_time_ms, "latency") if dr.resolution_time_ms > 0 else ""
            time_str = f"{dr.resolution_time_ms:.0f} ms" if dr.resolution_time_ms > 0 else "N/A (IP)"
            dns_rows += f"""
                <tr>
                    <td>{dr.target}</td>
                    <td>{dr.resolved_ip or '-'}</td>
                    <td class="{time_class}">{time_str}</td>
                </tr>
            """
        else:
            dns_rows += f"""
                <tr>
                    <td>{dr.target}</td>
                    <td colspan="2" class="bad">{dr.error}</td>
                </tr>
            """

    # Build MTR sections
    mtr_sections = ""
    for mtr in mtr_results:
        if mtr.success and mtr.hops:
            hop_rows = ""
            for hop in mtr.hops:
                loss_class = get_status_class(hop.loss_pct, "packet_loss")
                avg_class = get_status_class(hop.avg_ms, "latency")
                hop_rows += f"""
                    <tr>
                        <td>{hop.hop_number}</td>
                        <td>{hop.host}</td>
                        <td class="{loss_class}">{hop.loss_pct:.1f}%</td>
                        <td class="{avg_class}">{hop.avg_ms:.1f} ms</td>
                        <td>{hop.best_ms:.1f} ms</td>
                        <td>{hop.worst_ms:.1f} ms</td>
                    </tr>
                """
            mtr_sections += f"""
                <div class="section">
                    <h2>Route to {mtr.target_name}</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Hop</th>
                                <th>Host</th>
                                <th>Loss</th>
                                <th>Avg</th>
                                <th>Best</th>
                                <th>Worst</th>
                            </tr>
                        </thead>
                        <tbody>
                            {hop_rows}
                        </tbody>
                    </table>
                </div>
            """
        else:
            mtr_sections += f"""
                <div class="section">
                    <h2>Route to {mtr.target_name}</h2>
                    <p class="bad">{mtr.error}</p>
                </div>
            """

    # Diagnostic section
    diag_colors = {
        "none": "#22c55e",  # green
        "local": "#ef4444",  # red
        "isp": "#ef4444",  # red
        "internet": "#eab308",  # yellow
        "target": "#eab308",  # yellow
    }
    diag_labels = {
        "none": "No Issues",
        "local": "Local Network Issue",
        "isp": "ISP Issue",
        "internet": "Internet Backbone Issue",
        "target": "Target-Specific Issue",
    }
    diag_color = diag_colors.get(diagnostic.category, "#94a3b8")
    diag_label = diag_labels.get(diagnostic.category, "Unknown")

    details_html = ""
    if diagnostic.details:
        details_html = "<ul>" + "".join(f"<li>{d}</li>" for d in diagnostic.details) + "</ul>"

    recommendations_html = ""
    if diagnostic.recommendations:
        recommendations_html = "<h4>Recommendations</h4><ul>" + "".join(f"<li>{r}</li>" for r in diagnostic.recommendations) + "</ul>"

    diagnostic_section = f"""
        <div class="section diagnostic" style="border-left: 4px solid {diag_color};">
            <div class="diag-header">
                <span class="diag-badge" style="background: {diag_color};">{diag_label}</span>
                <span class="diag-confidence">Confidence: {diagnostic.confidence}</span>
            </div>
            <h2 style="color: {diag_color};">{diagnostic.summary}</h2>
            {details_html}
            {recommendations_html}
        </div>
    """

    # Speed test section
    speed_section = ""
    if speedtest_result.success:
        dl_class = get_status_class(dl_pct, "download_pct", reverse=True)
        ping_class = get_status_class(speedtest_result.ping_ms, "latency")
        speed_section = f"""
            <div class="cards">
                <div class="card">
                    <div class="card-title">Download</div>
                    <div class="card-value {dl_class}">{speedtest_result.download_mbps:.1f} Mbps</div>
                    <div class="card-subtitle">{dl_pct:.0f}% of {expected_speed} Mbps expected</div>
                </div>
                <div class="card">
                    <div class="card-title">Upload</div>
                    <div class="card-value">{speedtest_result.upload_mbps:.1f} Mbps</div>
                </div>
                <div class="card">
                    <div class="card-title">Ping</div>
                    <div class="card-value {ping_class}">{speedtest_result.ping_ms:.1f} ms</div>
                </div>
                <div class="card">
                    <div class="card-title">Server</div>
                    <div class="card-value small">{speedtest_result.server}</div>
                </div>
            </div>
        """
    else:
        speed_section = f'<p class="bad">{speedtest_result.error}</p>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Network Test Report - {timestamp}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --good: #22c55e;
            --warning: #eab308;
            --bad: #ef4444;
            --bg: #0f172a;
            --bg-card: #1e293b;
            --text: #f1f5f9;
            --text-dim: #94a3b8;
            --border: #334155;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        h1 {{
            text-align: center;
            margin-bottom: 0.5rem;
            color: var(--text);
        }}

        .timestamp {{
            text-align: center;
            color: var(--text-dim);
            margin-bottom: 2rem;
        }}

        .section {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border);
        }}

        .section h2 {{
            margin-bottom: 1rem;
            color: var(--text);
            font-size: 1.25rem;
        }}

        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }}

        .card {{
            background: var(--bg);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
            border: 1px solid var(--border);
        }}

        .card-title {{
            color: var(--text-dim);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .card-value {{
            font-size: 2rem;
            font-weight: bold;
            margin: 0.5rem 0;
        }}

        .card-value.small {{
            font-size: 1rem;
        }}

        .card-subtitle {{
            color: var(--text-dim);
            font-size: 0.875rem;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}

        th {{
            color: var(--text-dim);
            font-weight: 500;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }}

        .good {{ color: var(--good); }}
        .warning {{ color: var(--warning); }}
        .bad {{ color: var(--bad); }}

        .chart-container {{
            position: relative;
            height: 300px;
            margin-top: 1rem;
        }}

        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 1.5rem;
        }}

        .diagnostic {{
            margin-bottom: 2rem;
        }}

        .diag-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }}

        .diag-badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--bg);
        }}

        .diag-confidence {{
            color: var(--text-dim);
            font-size: 0.875rem;
        }}

        .diagnostic h2 {{
            margin-bottom: 1rem;
        }}

        .diagnostic ul {{
            list-style: none;
            padding: 0;
            margin: 0.5rem 0;
        }}

        .diagnostic li {{
            padding: 0.25rem 0;
            padding-left: 1.5rem;
            position: relative;
        }}

        .diagnostic li::before {{
            content: "-";
            position: absolute;
            left: 0.5rem;
            color: var(--text-dim);
        }}

        .diagnostic h4 {{
            margin-top: 1rem;
            margin-bottom: 0.5rem;
            color: var(--text-dim);
            font-size: 0.875rem;
            text-transform: uppercase;
        }}

        @media (max-width: 600px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}

            body {{
                padding: 1rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Network Test Report</h1>
        <p class="timestamp">{timestamp}</p>

        {diagnostic_section}

        <div class="section">
            <h2>Speed Test</h2>
            {speed_section}
        </div>

        <div class="section">
            <h2>Latency Tests</h2>
            <table>
                <thead>
                    <tr>
                        <th>Target</th>
                        <th>Min</th>
                        <th>Avg</th>
                        <th>Max</th>
                        <th>Jitter</th>
                        <th>Loss</th>
                    </tr>
                </thead>
                <tbody>
                    {latency_rows}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>DNS Resolution</h2>
            <table>
                <thead>
                    <tr>
                        <th>Target</th>
                        <th>Resolved IP</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody>
                    {dns_rows}
                </tbody>
            </table>
        </div>

        {mtr_sections}

        <div class="charts-grid">
            <div class="section">
                <h2>Latency Comparison</h2>
                <div class="chart-container">
                    <canvas id="latencyChart"></canvas>
                </div>
            </div>

            <div class="section">
                <h2>Jitter & Packet Loss</h2>
                <div class="chart-container">
                    <canvas id="jitterChart"></canvas>
                </div>
            </div>

            <div class="section">
                <h2>Route Latency (First Target)</h2>
                <div class="chart-container">
                    <canvas id="mtrChart"></canvas>
                </div>
            </div>
        </div>
    </div>

    <script>
        const chartColors = {{
            good: '#22c55e',
            warning: '#eab308',
            bad: '#ef4444',
            blue: '#3b82f6',
            purple: '#8b5cf6',
            cyan: '#06b6d4',
        }};

        // Latency Chart
        new Chart(document.getElementById('latencyChart'), {{
            type: 'bar',
            data: {{
                labels: {ping_labels},
                datasets: [
                    {{
                        label: 'Min',
                        data: {ping_min},
                        backgroundColor: chartColors.good,
                    }},
                    {{
                        label: 'Avg',
                        data: {ping_avg},
                        backgroundColor: chartColors.blue,
                    }},
                    {{
                        label: 'Max',
                        data: {ping_max},
                        backgroundColor: chartColors.warning,
                    }},
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        labels: {{ color: '#f1f5f9' }}
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#94a3b8' }},
                        grid: {{ color: '#334155' }}
                    }},
                    y: {{
                        ticks: {{ color: '#94a3b8' }},
                        grid: {{ color: '#334155' }},
                        title: {{
                            display: true,
                            text: 'Latency (ms)',
                            color: '#94a3b8'
                        }}
                    }}
                }}
            }}
        }});

        // Jitter & Loss Chart
        new Chart(document.getElementById('jitterChart'), {{
            type: 'bar',
            data: {{
                labels: {ping_labels},
                datasets: [
                    {{
                        label: 'Jitter (ms)',
                        data: {ping_jitter},
                        backgroundColor: chartColors.purple,
                        yAxisID: 'y',
                    }},
                    {{
                        label: 'Packet Loss (%)',
                        data: {ping_loss},
                        backgroundColor: chartColors.bad,
                        yAxisID: 'y1',
                    }},
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        labels: {{ color: '#f1f5f9' }}
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#94a3b8' }},
                        grid: {{ color: '#334155' }}
                    }},
                    y: {{
                        type: 'linear',
                        position: 'left',
                        ticks: {{ color: '#94a3b8' }},
                        grid: {{ color: '#334155' }},
                        title: {{
                            display: true,
                            text: 'Jitter (ms)',
                            color: '#94a3b8'
                        }}
                    }},
                    y1: {{
                        type: 'linear',
                        position: 'right',
                        ticks: {{ color: '#94a3b8' }},
                        grid: {{ drawOnChartArea: false }},
                        title: {{
                            display: true,
                            text: 'Packet Loss (%)',
                            color: '#94a3b8'
                        }}
                    }}
                }}
            }}
        }});

        // MTR Chart
        new Chart(document.getElementById('mtrChart'), {{
            type: 'line',
            data: {{
                labels: {mtr_hops_labels},
                datasets: [
                    {{
                        label: 'Latency (ms)',
                        data: {mtr_hops_latency},
                        borderColor: chartColors.cyan,
                        backgroundColor: 'rgba(6, 182, 212, 0.1)',
                        fill: true,
                        tension: 0.3,
                        yAxisID: 'y',
                    }},
                    {{
                        label: 'Packet Loss (%)',
                        data: {mtr_hops_loss},
                        borderColor: chartColors.bad,
                        backgroundColor: 'transparent',
                        borderDash: [5, 5],
                        yAxisID: 'y1',
                    }},
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        labels: {{ color: '#f1f5f9' }}
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#94a3b8' }},
                        grid: {{ color: '#334155' }}
                    }},
                    y: {{
                        type: 'linear',
                        position: 'left',
                        ticks: {{ color: '#94a3b8' }},
                        grid: {{ color: '#334155' }},
                        title: {{
                            display: true,
                            text: 'Latency (ms)',
                            color: '#94a3b8'
                        }}
                    }},
                    y1: {{
                        type: 'linear',
                        position: 'right',
                        ticks: {{ color: '#94a3b8' }},
                        grid: {{ drawOnChartArea: false }},
                        title: {{
                            display: true,
                            text: 'Packet Loss (%)',
                            color: '#94a3b8'
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

    # Write HTML file
    filename = f"nettest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w') as f:
        f.write(html)

    return filepath


def run_tests_with_progress(
    targets: dict[str, str],
    ping_count: int = PING_COUNT,
    mtr_count: int = MTR_COUNT,
    quiet: bool = False,
    skip_speedtest: bool = False,
    skip_dns: bool = False,
    skip_mtr: bool = False,
    parallel: bool = False,
) -> tuple[list[PingResult], SpeedTestResult, list[DnsResult], list[MtrResult]]:
    """Run network tests with progress indicators.

    Args:
        targets: Dict of target_name -> target_address
        ping_count: Number of ping packets to send
        mtr_count: Number of mtr packets to send
        quiet: Suppress progress output
        skip_speedtest: Skip speed test
        skip_dns: Skip DNS tests
        skip_mtr: Skip MTR route analysis
        parallel: Run ping and DNS tests in parallel (faster but less orderly output)
    """
    ping_results = []
    dns_results = []
    mtr_results = []
    speedtest_result = SpeedTestResult()

    # Calculate total steps based on what tests we're running
    num_targets = len(targets)
    total_steps = num_targets  # ping tests always run
    if not skip_speedtest:
        total_steps += 1
    if not skip_dns:
        total_steps += num_targets
    if not skip_mtr:
        total_steps += num_targets

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=not quiet,
        disable=quiet,
    ) as progress:
        overall_task = progress.add_task("[cyan]Running network tests...", total=total_steps)

        if parallel:
            # Parallel execution for ping and DNS tests
            progress.update(overall_task, description="[cyan]Running ping tests in parallel...")

            # Run ping tests in parallel
            with ThreadPoolExecutor(max_workers=min(len(targets), 5)) as executor:
                ping_futures = {
                    executor.submit(run_ping_test, target, name, ping_count): name
                    for name, target in targets.items()
                }
                for future in as_completed(ping_futures):
                    result = future.result()
                    ping_results.append(result)
                    json_logger.log_ping_result(result)
                    progress.advance(overall_task)

            # Run speed test (sequential - uses bandwidth)
            if not skip_speedtest:
                progress.update(overall_task, description="[cyan]Running speed test...")
                speedtest_result = run_speedtest()
                json_logger.log_speedtest_result(speedtest_result)
                progress.advance(overall_task)

            # Run DNS tests in parallel
            if not skip_dns:
                progress.update(overall_task, description="[cyan]Running DNS tests in parallel...")
                with ThreadPoolExecutor(max_workers=min(len(targets), 5)) as executor:
                    dns_futures = {
                        executor.submit(run_dns_test, target): name
                        for name, target in targets.items()
                    }
                    for future in as_completed(dns_futures):
                        result = future.result()
                        dns_results.append(result)
                        json_logger.log_dns_result(result)
                        progress.advance(overall_task)

            # Run MTR tests (sequential - uses significant network resources)
            if not skip_mtr:
                for name, target in targets.items():
                    progress.update(overall_task, description=f"[cyan]Route analysis to {name}...")
                    result = run_mtr(target, name, count=mtr_count)
                    mtr_results.append(result)
                    json_logger.log_mtr_result(result)
                    progress.advance(overall_task)
        else:
            # Sequential execution (original behavior)
            # Run ping tests
            for name, target in targets.items():
                progress.update(overall_task, description=f"[cyan]Pinging {name}...")
                result = run_ping_test(target, name, count=ping_count)
                ping_results.append(result)
                json_logger.log_ping_result(result)
                progress.advance(overall_task)

            # Run speed test
            if not skip_speedtest:
                progress.update(overall_task, description="[cyan]Running speed test...")
                speedtest_result = run_speedtest()
                json_logger.log_speedtest_result(speedtest_result)
                progress.advance(overall_task)

            # Run DNS tests
            if not skip_dns:
                for name, target in targets.items():
                    progress.update(overall_task, description=f"[cyan]Testing DNS for {name}...")
                    result = run_dns_test(target)
                    dns_results.append(result)
                    json_logger.log_dns_result(result)
                    progress.advance(overall_task)

            # Run MTR tests
            if not skip_mtr:
                for name, target in targets.items():
                    progress.update(overall_task, description=f"[cyan]Route analysis to {name}...")
                    result = run_mtr(target, name, count=mtr_count)
                    mtr_results.append(result)
                    json_logger.log_mtr_result(result)
                    progress.advance(overall_task)

        progress.update(overall_task, description="[green]Tests complete!")

    return ping_results, speedtest_result, dns_results, mtr_results


def output_json(
    ping_results: list[PingResult],
    speedtest_result: SpeedTestResult,
    dns_results: list[DnsResult],
    mtr_results: list[MtrResult],
    diagnostic: DiagnosticResult,
    port_results: Optional[list[PortResult]] = None,
    http_results: Optional[list[HttpResult]] = None,
) -> None:
    """Output all results as JSON to stdout."""
    from dataclasses import asdict

    output = {
        "timestamp": datetime.now().isoformat(),
        "ping_results": [asdict(r) for r in ping_results],
        "speedtest": asdict(speedtest_result),
        "dns_results": [asdict(r) for r in dns_results],
        "mtr_results": [
            {
                "target": r.target,
                "target_name": r.target_name,
                "success": r.success,
                "error": r.error,
                "hops": [asdict(h) for h in r.hops],
            }
            for r in mtr_results
        ],
        "diagnostic": asdict(diagnostic),
    }

    # Add optional results if present
    if port_results:
        output["port_results"] = [asdict(r) for r in port_results]
    if http_results:
        output["http_results"] = [asdict(r) for r in http_results]

    print(json.dumps(output, indent=2))


def run_monitor_mode(
    targets: Dict[str, str],
    interval: int,
    ping_count: int = 3,
    config: dict = None
) -> None:
    """
    Run continuous monitoring mode with live-updating dashboard.

    Uses Rich Live to display real-time ping statistics that refresh
    on each interval.

    Args:
        targets: Dict of target_name -> hostname/IP to monitor
        interval: Seconds between test rounds
        ping_count: Number of ping packets per target
        config: Configuration dict for thresholds
    """
    from datetime import datetime

    # Track historical data for each target (last 10 readings)
    history: Dict[str, list] = {name: [] for name in targets.keys()}
    max_history = 10

    def generate_dashboard(results: List[PingResult], round_num: int) -> Table:
        """Generate the monitoring dashboard table."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Main table
        table = Table(
            title=f"[bold blue]Network Monitor[/bold blue] - Round {round_num}",
            caption=f"Last update: {now} | Interval: {interval}s | Ctrl+C to stop",
            box=box.ROUNDED,
            header_style="bold cyan",
            show_lines=True
        )

        table.add_column("Target", style="white", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Latency", justify="right")
        table.add_column("Jitter", justify="right")
        table.add_column("Loss", justify="right")
        table.add_column("Trend", justify="center")
        table.add_column("Min/Max", justify="right")

        for result in results:
            # Update history
            if result.success:
                history[result.target_name].append(result.avg_ms)
                if len(history[result.target_name]) > max_history:
                    history[result.target_name].pop(0)

            # Determine status emoji and colors
            if not result.success:
                status = "[red]● DOWN[/red]"
                latency_str = f"[red]{result.error or 'Unreachable'}[/red]"
                jitter_str = "-"
                loss_str = "[red]100%[/red]"
                trend_str = "⬇"
                minmax_str = "-"
            else:
                # Evaluate metrics
                lat_status, lat_color = evaluate_metric(result.avg_ms, "latency")
                jit_status, jit_color = evaluate_metric(result.jitter_ms, "jitter")
                loss_status, loss_color = evaluate_metric(result.packet_loss, "packet_loss")

                # Overall status
                if lat_status == "bad" or loss_status == "bad":
                    status = "[red]● WARN[/red]"
                elif lat_status == "warning" or loss_status == "warning":
                    status = "[yellow]● FAIR[/yellow]"
                else:
                    status = "[green]● GOOD[/green]"

                latency_str = f"[{lat_color}]{result.avg_ms:.1f}ms[/{lat_color}]"
                jitter_str = f"[{jit_color}]{result.jitter_ms:.1f}ms[/{jit_color}]"
                loss_str = f"[{loss_color}]{result.packet_loss:.1f}%[/{loss_color}]"
                minmax_str = f"{result.min_ms:.0f}/{result.max_ms:.0f}ms"

                # Calculate trend from history
                hist = history[result.target_name]
                if len(hist) >= 2:
                    recent_avg = sum(hist[-3:]) / len(hist[-3:])
                    older_avg = sum(hist[:-3]) / max(len(hist[:-3]), 1) if len(hist) > 3 else recent_avg
                    if recent_avg > older_avg * 1.2:
                        trend_str = "[red]↗[/red]"  # Getting worse
                    elif recent_avg < older_avg * 0.8:
                        trend_str = "[green]↘[/green]"  # Getting better
                    else:
                        trend_str = "→"  # Stable
                else:
                    trend_str = "-"

            table.add_row(
                result.target_name,
                status,
                latency_str,
                jitter_str,
                loss_str,
                trend_str,
                minmax_str
            )

        return table

    console.print()
    console.print(Panel.fit(
        "[bold blue]Network Monitor[/bold blue]\n"
        f"[dim]Monitoring {len(targets)} targets every {interval}s[/dim]\n"
        "[dim]Press Ctrl+C to stop[/dim]",
        border_style="blue"
    ))
    console.print()

    round_num = 0
    try:
        with Live(console=console, refresh_per_second=1, transient=False) as live:
            while True:
                round_num += 1

                # Run ping tests
                results = []
                for name, target in targets.items():
                    result = run_ping_test(target, target_name=name, count=ping_count)
                    results.append(result)

                # Update the live display
                dashboard = generate_dashboard(results, round_num)
                live.update(dashboard)

                # Log results if logger is configured
                if json_logger:
                    for result in results:
                        json_logger.log_ping_result(result)

                # Wait for next interval
                time.sleep(interval)

    except KeyboardInterrupt:
        console.print()
        console.print(f"[dim]Monitoring stopped after {round_num} rounds.[/dim]")


def run_interactive_mode(config: dict) -> Optional[dict]:
    """
    Run interactive menu mode.

    Returns a dict with test settings, or None if user quits.
    """
    console.print()
    console.print(Panel.fit(
        "[bold blue]Network Testing Tool[/bold blue]\n"
        "[dim]Interactive Mode[/dim]",
        border_style="blue"
    ))
    console.print()

    menu = """
[bold]Select test mode:[/bold]

  [cyan]1[/cyan]  Quick check      [dim]- Ping only, 3 packets (fast)[/dim]
  [cyan]2[/cyan]  Full diagnostic  [dim]- All tests, comprehensive analysis[/dim]
  [cyan]3[/cyan]  Speed test only  [dim]- Internet speed measurement[/dim]
  [cyan]4[/cyan]  Route analysis   [dim]- MTR traceroute to targets[/dim]
  [cyan]5[/cyan]  Custom test      [dim]- Configure your own test[/dim]
  [cyan]q[/cyan]  Quit

"""
    console.print(menu)

    choice = Prompt.ask(
        "Enter choice",
        choices=["1", "2", "3", "4", "5", "q"],
        default="2"
    )

    if choice == "q":
        console.print("[dim]Goodbye![/dim]")
        return None

    # Build test settings based on choice
    settings = {
        "skip_speedtest": False,
        "skip_dns": False,
        "skip_mtr": False,
        "ping_count": config["tests"]["ping_count"],
        "mtr_count": config["tests"]["mtr_count"],
        "targets": config["targets"],
    }

    if choice == "1":
        # Quick check - ping only
        settings["skip_speedtest"] = True
        settings["skip_dns"] = True
        settings["skip_mtr"] = True
        settings["ping_count"] = 3
        console.print("[dim]Running quick check (ping only)...[/dim]")

    elif choice == "2":
        # Full diagnostic
        settings["ping_count"] = 10
        settings["mtr_count"] = 10
        console.print("[dim]Running full diagnostic...[/dim]")

    elif choice == "3":
        # Speed test only
        settings["skip_dns"] = True
        settings["skip_mtr"] = True
        settings["ping_count"] = 3
        console.print("[dim]Running speed test...[/dim]")

    elif choice == "4":
        # Route analysis (MTR focus)
        settings["skip_speedtest"] = True
        settings["skip_dns"] = True
        settings["mtr_count"] = 10
        settings["ping_count"] = 3
        console.print("[dim]Running route analysis...[/dim]")

    elif choice == "5":
        # Custom test - ask for settings
        console.print("\n[bold]Custom Test Configuration[/bold]\n")

        # Ask for ping count
        ping_count_str = Prompt.ask(
            "Number of ping packets",
            default="5"
        )
        settings["ping_count"] = int(ping_count_str) if ping_count_str.isdigit() else 5

        # Ask which tests to run
        settings["skip_speedtest"] = not Confirm.ask("Run speed test?", default=True)
        settings["skip_dns"] = not Confirm.ask("Run DNS tests?", default=True)
        settings["skip_mtr"] = not Confirm.ask("Run route analysis (MTR)?", default=True)

        if not settings["skip_mtr"]:
            mtr_count_str = Prompt.ask(
                "Number of MTR packets",
                default="5"
            )
            settings["mtr_count"] = int(mtr_count_str) if mtr_count_str.isdigit() else 5

        # Ask for custom targets
        if Confirm.ask("Use custom targets?", default=False):
            targets_str = Prompt.ask(
                "Enter targets (comma-separated, format: Name:IP or just IP)",
                default="8.8.8.8,1.1.1.1"
            )
            custom_targets = {}
            for item in targets_str.split(","):
                item = item.strip()
                if ":" in item:
                    name, target = item.split(":", 1)
                    custom_targets[name.strip()] = target.strip()
                else:
                    custom_targets[item] = item
            settings["targets"] = custom_targets

        console.print("[dim]Running custom test...[/dim]")

    console.print()
    return settings


# ============================================================================
# CLI & MAIN ENTRY POINT
# ============================================================================

def main():
    global THRESHOLDS  # Allow config to update thresholds

    parser = argparse.ArgumentParser(
        description="Network Testing Tool - Run comprehensive network tests"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to YAML config file (default: searches ./nettest.yml, ~/.config/nettest/config.yml)"
    )
    parser.add_argument(
        "--expected-speed",
        type=float,
        default=None,
        help="Expected download speed in Mbps (overrides config)"
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't auto-open HTML report in browser"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Directory for HTML report (overrides config)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress terminal output (only show results)"
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip pre-flight dependency check"
    )
    parser.add_argument(
        "--targets",
        type=str,
        help="Custom targets (comma-separated), e.g., 'Google:8.8.8.8,CF:1.1.1.1'"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json", "html"],
        default="text",
        help="Output format: text (terminal+HTML), json (machine-readable), html (report only)"
    )
    parser.add_argument(
        "--ping-count",
        type=int,
        default=None,
        help="Number of ping packets to send (overrides config)"
    )
    parser.add_argument(
        "--profile",
        type=str,
        choices=["quick", "full"],
        help="Test profile: quick (ping only, 3 packets), full (all tests, 10 packets)"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        help="Path to JSON log file for Promtail/Loki (enables structured logging)"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive menu mode"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run ping and DNS tests in parallel (faster execution)"
    )
    parser.add_argument(
        "--check-ports",
        type=str,
        help="Test TCP ports (comma-separated), e.g., '80,443,22' or 'host:80,host:443'"
    )
    parser.add_argument(
        "--check-http",
        type=str,
        help="Test HTTP/HTTPS latency (comma-separated URLs), e.g., 'google.com,github.com'"
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Run in continuous monitoring mode (Ctrl+C to stop)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Monitoring interval in seconds (default: 30)"
    )

    args = parser.parse_args()

    # Determine if we should suppress terminal output
    # Quiet mode or JSON format should suppress most output
    suppress_output = args.quiet or args.format == "json"

    # Load configuration (file + CLI overrides)
    config = load_config(config_path=args.config, quiet=suppress_output or args.interactive)

    # Update global thresholds from config
    THRESHOLDS = config["thresholds"]

    # Handle interactive mode
    if args.interactive:
        interactive_settings = run_interactive_mode(config)
        if interactive_settings is None:
            # User quit
            sys.exit(0)

        # Apply interactive settings
        skip_speedtest = interactive_settings["skip_speedtest"]
        skip_dns = interactive_settings["skip_dns"]
        skip_mtr = interactive_settings["skip_mtr"]
        config["tests"]["ping_count"] = interactive_settings["ping_count"]
        config["tests"]["mtr_count"] = interactive_settings["mtr_count"]
        config["targets"] = interactive_settings["targets"]
    else:
        # Non-interactive mode - show header
        if not suppress_output:
            console.print()
            console.print(Panel.fit(
                "[bold blue]Network Testing Tool[/bold blue]\n"
                "[dim]Comprehensive network diagnostics[/dim]",
                border_style="blue"
            ))
            console.print()

        # Apply profile settings first (can be overridden by explicit flags)
        skip_speedtest = False
        skip_mtr = False
        skip_dns = False

        if args.profile == "quick":
            # Quick mode: ping only with fewer packets
            config["tests"]["ping_count"] = 3
            skip_speedtest = True
            skip_mtr = True
            skip_dns = True
            if not suppress_output:
                console.print("[dim]Using quick profile: ping only, 3 packets[/dim]")
        elif args.profile == "full":
            # Full mode: all tests with more packets
            config["tests"]["ping_count"] = 10
            config["tests"]["mtr_count"] = 10
            if not suppress_output:
                console.print("[dim]Using full profile: all tests, 10 packets[/dim]")

    # Apply CLI overrides to config
    if args.expected_speed is not None:
        config["tests"]["expected_speed"] = args.expected_speed
    if args.output is not None:
        config["output"]["directory"] = args.output
    if args.no_browser:
        config["output"]["open_browser"] = False
    if args.ping_count is not None:
        config["tests"]["ping_count"] = args.ping_count

    # Parse custom targets if provided
    if args.targets:
        custom_targets = {}
        for item in args.targets.split(","):
            item = item.strip()
            if ":" in item:
                name, target = item.split(":", 1)
                custom_targets[name.strip()] = target.strip()
            else:
                # Use target as both name and address
                custom_targets[item] = item
        config["targets"] = custom_targets
        if not suppress_output:
            console.print(f"[dim]Using custom targets: {', '.join(custom_targets.keys())}[/dim]")

    # Extract config values for convenience
    targets = config["targets"]
    ping_count = config["tests"]["ping_count"]
    mtr_count = config["tests"]["mtr_count"]
    expected_speed = config["tests"]["expected_speed"]
    output_dir = config["output"]["directory"]
    open_browser = config["output"]["open_browser"]
    output_format = args.format

    # Configure JSON logger
    global json_logger
    log_file = args.log_file or (config["logging"]["file"] if config["logging"]["enabled"] else None)
    if log_file:
        json_logger = JsonLogger(log_file=log_file, enabled=True)
        json_logger.log_start(targets=list(targets.keys()), profile=args.profile)
        if not suppress_output:
            console.print(f"[dim]Logging to: {log_file}[/dim]")

    # Handle monitor mode (continuous monitoring)
    if args.monitor:
        run_monitor_mode(
            targets=targets,
            interval=args.interval,
            ping_count=min(ping_count, 3),  # Use fewer packets for faster monitoring
            config=config
        )
        # Monitor mode runs indefinitely until Ctrl+C
        if json_logger:
            json_logger.log_end(success=True)
        sys.exit(0)

    # Pre-flight dependency check
    if not args.skip_check:
        tool_status = check_dependencies(quiet=args.quiet)

        # Check if required tools are missing
        missing_required = [
            tool for tool, available in tool_status.items()
            if not available and REQUIRED_TOOLS[tool]["required"]
        ]
        if missing_required:
            console.print(f"[red]Error: Required tools missing: {', '.join(missing_required)}[/red]")
            console.print("[dim]Install the missing tools and try again, or use --skip-check to proceed anyway.[/dim]")
            sys.exit(1)

    # Run all tests with progress indicators
    ping_results, speedtest_result, dns_results, mtr_results = run_tests_with_progress(
        targets,
        ping_count=ping_count,
        mtr_count=mtr_count,
        quiet=args.quiet or output_format == "json",
        skip_speedtest=skip_speedtest,
        skip_dns=skip_dns,
        skip_mtr=skip_mtr,
        parallel=args.parallel,
    )

    # Run optional TCP port tests
    port_results = []
    if args.check_ports:
        if not suppress_output:
            console.print("[dim]Running TCP port tests...[/dim]")
        for item in args.check_ports.split(","):
            item = item.strip()
            if ":" in item:
                # Format: host:port
                host, port_str = item.rsplit(":", 1)
                port = int(port_str)
            else:
                # Just port number - test against first target
                host = list(targets.values())[0] if targets else "8.8.8.8"
                port = int(item)
            result = check_tcp_port(host, port)
            port_results.append(result)

    # Run optional HTTP latency tests
    http_results = []
    if args.check_http:
        if not suppress_output:
            console.print("[dim]Running HTTP latency tests...[/dim]")
        for url in args.check_http.split(","):
            url = url.strip()
            result = measure_http_latency(url)
            http_results.append(result)

    # Run diagnostics
    diagnostic = diagnose_network(
        ping_results,
        speedtest_result,
        mtr_results,
        expected_speed
    )

    # Log diagnostic result
    json_logger.log_diagnostic(diagnostic)

    # Handle output based on format
    if output_format == "json":
        # JSON output - machine-readable format to stdout
        output_json(ping_results, speedtest_result, dns_results, mtr_results, diagnostic,
                    port_results=port_results, http_results=http_results)
    else:
        # Text or HTML format - show terminal output
        if not args.quiet:
            display_terminal(
                ping_results,
                speedtest_result,
                dns_results,
                mtr_results,
                expected_speed,
                diagnostic
            )

            # Display port test results if any
            if port_results:
                console.print("[bold]TCP Port Tests[/bold]")
                port_table = Table(box=box.ROUNDED)
                port_table.add_column("Host", style="cyan")
                port_table.add_column("Port", justify="right")
                port_table.add_column("Status", justify="center")
                port_table.add_column("Response Time", justify="right")

                for pr in port_results:
                    status = "[green]Open[/green]" if pr.open else f"[red]Closed[/red]"
                    time_str = f"{pr.response_time_ms:.1f} ms" if pr.open else pr.error
                    port_table.add_row(pr.host, str(pr.port), status, time_str)

                console.print(port_table)
                console.print()

            # Display HTTP latency results if any
            if http_results:
                console.print("[bold]HTTP Latency Tests[/bold]")
                http_table = Table(box=box.ROUNDED)
                http_table.add_column("URL", style="cyan")
                http_table.add_column("Status", justify="center")
                http_table.add_column("Response Time", justify="right")

                for hr in http_results:
                    if hr.success:
                        status = f"[green]{hr.status_code}[/green]"
                        time_str = f"{hr.response_time_ms:.1f} ms"
                    else:
                        status = f"[red]{hr.status_code or 'Failed'}[/red]"
                        time_str = hr.error
                    http_table.add_row(hr.url, status, time_str)

                console.print(http_table)
                console.print()

        # Generate HTML report for text and html formats
        if not args.quiet:
            console.print("[dim]Generating HTML report...[/dim]")
        html_path = generate_html(
            ping_results,
            speedtest_result,
            dns_results,
            mtr_results,
            expected_speed,
            output_dir,
            diagnostic
        )
        if not args.quiet:
            console.print(f"[green]HTML report saved to: {html_path}[/green]")

        # Open in browser (respects config and --no-browser flag)
        if open_browser and output_format != "html":
            # html format = report only, no auto-open
            if not args.quiet:
                console.print("[dim]Opening report in browser...[/dim]")
            webbrowser.open(f"file://{html_path}")

        # For html-only format, just print the path
        if output_format == "html":
            print(html_path)

    # Log session end
    json_logger.log_end(success=True)


if __name__ == "__main__":
    main()
