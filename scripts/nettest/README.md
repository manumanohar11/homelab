# Network Testing Tool

Comprehensive network diagnostic tool with terminal output, HTML reports, Prometheus metrics, and Docker support.

## Features

- **Speed Test** - Download/upload speeds
- **Latency Tests** - Ping with jitter and packet loss
- **Route Analysis** - MTR network path tracing
- **DNS Resolution** - Lookup timing
- **TCP Port Testing** - Connectivity checks
- **HTTP/HTTPS Latency** - Application-layer timing
- **Prometheus Metrics** - Scrape-ready metrics endpoint
- **Alerting** - Webhook and email notifications
- **Interactive TUI** - Menu-driven interface
- **Continuous Monitoring** - Live dashboard
- **Historical Comparison** - Track performance over time

## Quick Start

```bash
# Run with defaults
python -m nettest

# Quick ping-only test
python -m nettest --profile quick

# Full comprehensive test
python -m nettest --profile full

# Interactive mode
python -m nettest --interactive

# Continuous monitoring with Prometheus
python -m nettest --monitor --prometheus-port 9101
```

## Docker

```bash
# Build image
docker build -t nettest .

# Run one-shot test
docker run --rm --cap-add NET_RAW nettest --profile quick

# Monitoring mode with metrics
docker run -d --cap-add NET_RAW -p 9101:9101 nettest --monitor --prometheus-port 9101
```

## Configuration

Create `nettest.yml` or use `--config path/to/config.yml`:

```yaml
targets:
  Google DNS: "8.8.8.8"
  Cloudflare DNS: "1.1.1.1"

tests:
  ping_count: 10
  expected_speed: 100

thresholds:
  latency:
    good: 50
    warning: 100

profiles:
  quick:
    description: "Fast ping-only test"
    ping_count: 3
    skip_speedtest: true
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--profile NAME` | Use test profile (quick, full, gaming) |
| `--format FORMAT` | Output format (text, json, html) |
| `--interface, -I` | Network interface to use |
| `--prometheus-port` | Enable Prometheus metrics |
| `--monitor` | Continuous monitoring mode |
| `--wizard` | Configuration wizard |
| `--history FILE` | Save/compare results |

## Package Structure

```
nettest/
├── __init__.py       # Version and exports
├── __main__.py       # Entry point
├── cli.py            # CLI and argument parsing
├── config.py         # Configuration loading
├── diagnostics.py    # Problem diagnosis
├── models.py         # Data classes
├── tests/            # Test implementations
│   ├── ping.py
│   ├── speedtest.py
│   ├── dns.py
│   ├── mtr.py
│   ├── tcp.py
│   └── http.py
├── output/           # Output formatters
│   ├── terminal.py
│   ├── html.py
│   ├── json_output.py
│   └── prometheus.py
├── tui/              # Terminal UI
│   ├── interactive.py
│   ├── monitor.py
│   └── wizard.py
├── alerts/           # Alerting system
│   ├── thresholds.py
│   └── notifications.py
└── utils/            # Utilities
    ├── commands.py
    ├── network.py
    ├── history.py
    └── logging.py
```

## Requirements

**Python:**
- rich>=13.0.0
- pyyaml>=6.0 (optional)
- prometheus-client>=0.19.0 (optional)
- requests>=2.31.0 (optional)
- netifaces>=0.11.0 (optional)

**System:**
- ping (required)
- dig (DNS tests)
- mtr (route analysis)
- speedtest-cli (speed tests)

## License

See main repository license.
