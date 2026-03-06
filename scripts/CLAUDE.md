# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**nettest** is a comprehensive network testing and diagnostics tool written in Python. It performs speed tests, latency analysis, route tracing, DNS resolution timing, TCP/HTTP connectivity checks, bufferbloat detection, VoIP quality scoring, and video conferencing service testing.

## Common Commands

```bash
# Run the tool (from repo root)
python -m nettest

# Run with specific profile
python -m nettest --profile quick    # Fast ping-only test
python -m nettest --profile full     # All tests enabled

# Run specific tests
python -m nettest --video-services   # Test Teams, Zoom, WhatsApp, Meet, Webex
python -m nettest --bufferbloat      # Bufferbloat detection
python -m nettest --check-ports 22,80,443  # TCP port checks
python -m nettest --check-http https://example.com

# Output formats
python -m nettest --format html --output report.html
python -m nettest --format json
python -m nettest --prometheus-port 9101

# Interactive modes
python -m nettest --interactive      # Menu-driven test selection
python -m nettest --monitor          # Live dashboard with continuous testing
python -m nettest --wizard           # Configuration setup wizard

# Build Windows package
./build-windows-package.sh
```

## Architecture

```
nettest/
├── cli.py              # Main entry point and argument parsing
├── config.py           # Configuration management, profiles, VIDEO_SERVICES dict
├── models.py           # Dataclasses for all result types (PingResult, SpeedTestResult, etc.)
├── diagnostics.py      # Network problem diagnosis logic
│
├── tests/              # Test implementations (run concurrently via ThreadPoolExecutor)
│   ├── runner.py       # Test orchestration with Rich progress tracking
│   ├── ping.py         # ICMP latency/jitter/packet loss
│   ├── speedtest.py    # Download/upload via speedtest-cli
│   ├── dns.py          # Resolution timing via dig
│   ├── mtr.py          # Route analysis
│   ├── tcp.py          # Port connectivity via socket
│   ├── http.py         # HTTP/HTTPS latency via requests
│   ├── bufferbloat.py  # Queue-induced latency detection
│   ├── stability.py    # Connection scoring (0-100) and MOS calculation
│   └── video_services.py  # DNS + TCP + STUN tests for video platforms
│
├── output/             # Output formatters (pluggable)
│   ├── terminal.py     # Rich TUI with color-coded tables
│   ├── html.py         # Comprehensive HTML reports with charts
│   ├── json_output.py  # Machine-readable JSON
│   ├── prometheus.py   # Metrics endpoint for scraping
│   └── evidence.py     # ISP complaint documentation
│
├── tui/                # Interactive modes
│   ├── interactive.py  # Menu-driven test selection
│   ├── monitor.py      # Live dashboard (continuous monitoring)
│   └── wizard.py       # Configuration setup wizard
│
└── alerts/             # Alerting system
    ├── thresholds.py   # Threshold definitions and checking
    └── notifications.py # Webhook and email notifications
```

## Key Design Patterns

- **Configuration hierarchy**: Built-in defaults → YAML file → CLI arguments → Profile overrides
- **Graceful degradation**: Optional dependencies (pyyaml, requests, netifaces) with fallbacks
- **Concurrent execution**: Tests run in parallel via `ThreadPoolExecutor` in `tests/runner.py`
- **Immutable dataclasses**: All result types in `models.py` are dataclasses with JSON serialization

## Configuration

Configuration is loaded from `./nettest.yml` or `~/.config/nettest/config.yml`. See `nettest.yml.example` for all options.

Key configuration sections:
- `targets`: IP addresses and hostnames to test
- `thresholds`: Latency, jitter, packet loss, speed thresholds
- `profiles`: Named test configurations (quick, full, gaming, etc.)
- `output`: Directory and browser settings

## Dependencies

**Required system tools**: `ping`

**Optional system tools**: `dig` (DNS), `mtr` (route analysis), `speedtest-cli` (speed tests)

**Python dependencies** (in `nettest/requirements.txt`):
- `rich` ≥13.0.0 (required) - Terminal formatting
- `pyyaml` ≥6.0 (optional) - YAML config
- `prometheus-client` ≥0.19.0 (optional) - Metrics
- `requests` ≥2.31.0 (optional) - HTTP tests/webhooks
- `netifaces` ≥0.11.0 (optional) - Interface enumeration

## Commit Convention

Use conventional commits: `type(scope): description`
- Types: `feat`, `fix`, `docs`, `test`, `refactor`
- Example: `feat(video-services): add STUN binding support`

## Adding New Tests

1. Create module in `nettest/tests/` following existing patterns
2. Add result dataclass to `models.py`
3. Integrate into `tests/runner.py` for concurrent execution
4. Add CLI arguments in `cli.py:create_parser()`
5. Add output handling to each formatter in `output/`
