"""Argument parser for the network testing tool."""

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def create_parser(version: str) -> argparse.ArgumentParser:
    """Create the argument parser with logically grouped arguments.

    Args:
        version: Version string to display with --version

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="nettest",
        description="Network Testing Tool - Comprehensive network diagnostics including "
                    "speed tests, latency analysis, DNS timing, and video service connectivity.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nettest                          Run default test suite with ping and DNS tests
  nettest --profile quick          Fast ping-only test (3 packets, no speedtest)
  nettest --profile full           Full comprehensive test with all diagnostics
  nettest --simple                 Non-technical output for end users
  nettest --format html -o .       Generate HTML report in current directory
  nettest --format json            Machine-readable JSON output
  nettest --video-services         Test Teams, Zoom, WhatsApp, Meet, Webex connectivity
  nettest --bufferbloat            Detect queue-induced latency under load
  nettest --monitor --interval 30  Continuous monitoring with 30-second intervals
  nettest --api --api-port 9000    Start REST API server on port 9000
  nettest --history-db             Track results over time in SQLite database
  nettest -I eth0 --profile quick  Test using specific network interface
  nettest --wizard                 Interactive configuration setup wizard

Configuration:
  Config files are loaded from (in order of priority):
    1. Path specified with --config
    2. ./nettest.yml (current directory)
    3. ~/.config/nettest/config.yml (user config)

  See nettest.yml.example for all available options.

For more information, visit: https://github.com/example/nettest
        """
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"nettest {version}"
    )

    # Quick Start group
    quick_start = parser.add_argument_group(
        "Quick Start",
        "Common options for getting started quickly"
    )
    quick_start.add_argument(
        "--profile",
        type=str,
        metavar="NAME",
        help="Use a named test profile. Built-in profiles: 'quick' (ping only), "
             "'full' (all tests). Use --list-profiles to see all available profiles"
    )
    quick_start.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available test profiles with descriptions and exit"
    )
    quick_start.add_argument(
        "--config",
        type=str,
        metavar="FILE",
        help="Path to YAML config file. Default search: ./nettest.yml, "
             "~/.config/nettest/config.yml"
    )
    quick_start.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive menu mode with test selection"
    )
    quick_start.add_argument(
        "--wizard",
        action="store_true",
        help="Run configuration setup wizard to create/edit config file"
    )

    # Test Selection group
    test_selection = parser.add_argument_group(
        "Test Selection",
        "Control which tests to run and their parameters"
    )
    test_selection.add_argument(
        "--targets",
        type=str,
        metavar="LIST",
        help="Custom ping/DNS targets as comma-separated 'Name:Address' pairs. "
             "Example: 'Google:8.8.8.8,Cloudflare:1.1.1.1'"
    )
    test_selection.add_argument(
        "--ping-count",
        type=int,
        default=None,
        metavar="N",
        help="Number of ping packets per target (default: 10, quick profile: 3)"
    )
    test_selection.add_argument(
        "--expected-speed",
        type=float,
        default=None,
        metavar="MBPS",
        help="Expected download speed in Mbps for threshold comparison (default: 100)"
    )
    test_selection.add_argument(
        "--bufferbloat",
        action="store_true",
        help="Run bufferbloat detection test to measure latency under load"
    )
    test_selection.add_argument(
        "--video-services", "-vs",
        action="store_true",
        help="Test video conferencing connectivity: Microsoft Teams, Zoom, "
             "WhatsApp, Google Meet, Webex. Includes DNS, TCP ports, and STUN tests"
    )
    test_selection.add_argument(
        "--check-ports",
        type=str,
        metavar="PORTS",
        help="Test TCP port connectivity. Comma-separated port numbers. "
             "Example: '22,80,443,3389'"
    )
    test_selection.add_argument(
        "--check-http",
        type=str,
        metavar="URLS",
        help="Test HTTP/HTTPS response times. Comma-separated URLs. "
             "Example: 'https://google.com,https://github.com'"
    )
    test_selection.add_argument(
        "--monitor",
        action="store_true",
        help="Run in continuous monitoring mode with live dashboard. "
             "Use --interval to set refresh rate"
    )
    test_selection.add_argument(
        "--interval",
        type=int,
        default=30,
        metavar="SECS",
        help="Monitoring interval in seconds (default: 30). Used with --monitor"
    )

    # Output Options group
    output_options = parser.add_argument_group(
        "Output Options",
        "Control output format and destinations"
    )
    output_options.add_argument(
        "--format", "-f",
        type=str,
        choices=["text", "json", "html"],
        default="text",
        help="Output format: 'text' (terminal, default), 'json' (machine-readable), "
             "'html' (visual report, see also: --output, --no-browser)"
    )
    output_options.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        metavar="DIR",
        help="Directory for HTML report output (default: ~/Downloads). "
             "Use with --format html"
    )
    output_options.add_argument(
        "--export-csv",
        action="store_true",
        help="Export results to CSV files in addition to primary output format"
    )
    output_options.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't auto-open HTML report in browser. Use with --format html"
    )
    output_options.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress terminal output. Useful for scripts and automation"
    )
    output_options.add_argument(
        "--simple", "-s",
        action="store_true",
        help="Show simplified, non-technical output suitable for end users"
    )
    output_options.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full technical output with all details (default behavior)"
    )
    output_options.add_argument(
        "--log-file",
        type=str,
        metavar="FILE",
        help="Write JSON log entries to file for Promtail/Loki ingestion"
    )
    output_options.add_argument(
        "--prometheus-port",
        type=int,
        metavar="PORT",
        help="Enable Prometheus metrics endpoint on specified port (e.g., 9101)"
    )

    # History Options group
    history_options = parser.add_argument_group(
        "History Options",
        "Track and analyze results over time using SQLite database"
    )
    history_options.add_argument(
        "--history",
        type=str,
        metavar="FILE",
        help="Save results to JSON history file and show comparison with previous run"
    )
    history_options.add_argument(
        "--history-db",
        action="store_true",
        help="Enable SQLite history storage at ~/.local/share/nettest/history.db. "
             "Use --history-db-path for custom location"
    )
    history_options.add_argument(
        "--history-db-path",
        type=str,
        metavar="FILE",
        help="Custom path for SQLite history database. Implies --history-db"
    )
    history_options.add_argument(
        "--history-retention",
        type=int,
        default=90,
        metavar="DAYS",
        help="Days to retain history data before automatic cleanup (default: 90)"
    )
    history_options.add_argument(
        "--history-export",
        type=str,
        metavar="FILE",
        help="Export SQLite history to CSV file for external analysis"
    )
    history_options.add_argument(
        "--history-trends",
        type=int,
        metavar="DAYS",
        nargs="?",
        const=7,
        help="Show trend analysis for specified number of days (default: 7 if omitted)"
    )
    history_options.add_argument(
        "--history-stats",
        action="store_true",
        help="Show SQLite history database statistics and exit"
    )

    # Advanced Options group
    advanced = parser.add_argument_group(
        "Advanced Options",
        "Network configuration and advanced settings"
    )
    advanced.add_argument(
        "--interface", "-I",
        type=str,
        metavar="IFACE",
        help="Network interface to use for tests (e.g., eth0, wlan0, en0). "
             "Use --list-interfaces to see available options"
    )
    advanced.add_argument(
        "--list-interfaces",
        action="store_true",
        help="List available network interfaces with IP addresses and exit"
    )
    advanced.add_argument(
        "--ipv4", "-4",
        action="store_true",
        help="Force IPv4 only for all tests"
    )
    advanced.add_argument(
        "--ipv6", "-6",
        action="store_true",
        help="Force IPv6 only for all tests"
    )
    advanced.add_argument(
        "--parallel",
        action="store_true",
        help="Run ping and DNS tests in parallel for faster execution"
    )
    advanced.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip pre-flight dependency check (ping, dig, mtr, speedtest-cli)"
    )
    advanced.add_argument(
        "--api",
        action="store_true",
        help="Start REST API server instead of running tests. "
             "Use --api-port to specify port"
    )
    advanced.add_argument(
        "--api-port",
        type=int,
        default=8080,
        metavar="PORT",
        help="Port for REST API server (default: 8080). Use with --api"
    )

    return parser
