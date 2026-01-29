# Utility Scripts

[← Back to README](../README.md)

Collection of utility scripts for managing and monitoring your homelab.

---

## Table of Contents

- [Network Testing Tool](#network-testing-tool)

---

## Network Testing Tool

**Location:** `scripts/nettest/` (Python package)

A comprehensive network diagnostic tool that tests connectivity, identifies where problems originate, and generates detailed reports.

### Features

- **Speed Test** - Download/upload speeds using speedtest-cli
- **Latency Tests** - Ping to multiple servers with jitter and packet loss
- **Route Analysis** - Uses `mtr` to trace network path and identify problematic hops
- **DNS Resolution** - Tests DNS lookup times
- **TCP Port Testing** - Check if specific ports are open
- **HTTP/HTTPS Latency** - Measure application-layer response times
- **Problem Diagnosis** - Automatically identifies if issues are with your local network, ISP, internet backbone, or specific targets
- **Multiple Output Formats** - Terminal, HTML reports, and JSON for scripting
- **YAML Configuration** - Customize targets, thresholds, and defaults
- **Structured Logging** - JSON logs for Promtail/Loki integration
- **Interactive Mode** - Menu-driven interface for easy use
- **Parallel Execution** - Faster testing with concurrent operations
- **Continuous Monitoring** - Live dashboard for ongoing network health tracking
- **IPv4/IPv6 Support** - Force specific IP protocol for testing
- **Historical Comparison** - Track performance over time and compare with previous runs

### Quick Start

```bash
# Navigate to scripts directory first
cd ~/docker/scripts

# Run with default settings
python3 -m nettest

# Quick check (ping only, fast)
python3 -m nettest --profile quick

# Full diagnostic with your plan speed
python3 -m nettest --profile full --expected-speed 500

# Interactive mode
python3 -m nettest --interactive

# JSON output for scripting
python3 -m nettest --format json --quiet
```

### Command-Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--config` | auto | Path to YAML config file |
| `--expected-speed` | 100 | Your plan's download speed in Mbps |
| `--no-browser` | false | Skip auto-opening HTML report |
| `--output` | /tmp | Directory for HTML report |
| `--quiet` | false | Suppress terminal output |
| `--skip-check` | false | Skip pre-flight dependency check |
| `--targets` | - | Custom targets (comma-separated) |
| `--format` | text | Output format: text, json, html |
| `--ping-count` | 10 | Number of ping packets to send |
| `--profile` | - | Test profile: quick or full |
| `--log-file` | - | Path to JSON log file |
| `--interactive` | false | Run in interactive menu mode |
| `--parallel` | false | Run tests in parallel (faster) |
| `--check-ports` | - | Test TCP ports (comma-separated) |
| `--check-http` | - | Test HTTP URLs (comma-separated) |
| `--monitor` | false | Run in continuous monitoring mode |
| `--interval` | 30 | Monitoring interval in seconds |
| `--ipv4`, `-4` | false | Force IPv4 only |
| `--ipv6`, `-6` | false | Force IPv6 only |
| `--history` | - | Save results to file and compare with previous run |
| `--interface`, `-I` | - | Network interface to use (e.g., eth0, wlan0) |
| `--list-interfaces` | false | List available network interfaces |
| `--wizard` | false | Run configuration wizard |
| `--prometheus-port` | - | Enable Prometheus metrics on specified port |

### Test Profiles

| Profile | Tests Run | Packets | Use Case |
|---------|-----------|---------|----------|
| `quick` | Ping only | 3 | Fast connectivity check |
| `full` | All tests | 10 | Comprehensive diagnosis |
| `gaming` | Ping + MTR | 20 | Low-latency gaming check |

Custom profiles can be defined in the YAML config:

```yaml
profiles:
  gaming:
    description: "Gaming-optimized low-latency check"
    ping_count: 20
    skip_speedtest: true
    skip_mtr: false
    targets:
      "Google DNS": "8.8.8.8"
      "Cloudflare DNS": "1.1.1.1"
    thresholds:
      latency:
        good: 20
        warning: 50
```

### Configuration File

Create a YAML config file to customize defaults. The tool searches in order:
1. `./nettest.yml` (current directory)
2. `~/.config/nettest/config.yml` (user config)

See `scripts/nettest.yml.example` for a complete example.

```yaml
# Example config
targets:
  Google DNS: "8.8.8.8"
  Cloudflare DNS: "1.1.1.1"
  My Router: "192.168.1.1"

tests:
  ping_count: 10
  expected_speed: 500

thresholds:
  latency:
    good: 50
    warning: 100

output:
  directory: "/home/user/network-reports"
  open_browser: false

logging:
  enabled: true
  file: "/var/log/nettest.log"
```

### Output Formats

#### Terminal Output (default)

Rich-formatted tables with color-coded status indicators:
- 🟢 **Green** - Good (within normal thresholds)
- 🟡 **Yellow** - Warning (degraded performance)
- 🔴 **Red** - Bad (significant issues)

#### HTML Report

Interactive HTML report with:
- Summary cards with key metrics
- Latency comparison charts (Chart.js)
- Jitter and packet loss graphs
- Route visualization
- Problem diagnosis section

#### JSON Output

Machine-readable JSON for scripting and automation:

```bash
# Get JSON output
python3 -m nettest --format json --quiet > results.json

# Parse with jq
python3 -m nettest --format json --quiet | jq '.diagnostic.category'
```

### TCP Port Testing

Test if specific ports are open:

```bash
# Test common ports on default targets
python3 -m nettest --check-ports "80,443,22"

# Test specific host:port combinations
python3 -m nettest --check-ports "8.8.8.8:53,1.1.1.1:443"
```

### HTTP Latency Testing

Measure application-layer response times:

```bash
# Test HTTP latency to popular sites
python3 -m nettest --check-http "google.com,github.com,cloudflare.com"
```

### Structured Logging (Promtail/Loki)

Enable JSON logging for log aggregation:

```bash
# Enable via CLI
python3 -m nettest --log-file /var/log/nettest.log

# Enable via config
logging:
  enabled: true
  file: "/var/log/nettest.log"
```

Log format (one JSON object per line):
```json
{"timestamp": "2024-01-15T14:30:22", "level": "info", "event": "ping_result", "target": "8.8.8.8", "avg_ms": 32.5, "packet_loss": 0.0}
```

### Interactive Mode

Run with a menu-driven interface:

```bash
python3 -m nettest --interactive
```

Options:
1. Quick check (ping only)
2. Full diagnostic
3. Speed test only
4. Route analysis
5. Custom test
q. Quit

### Parallel Execution

Speed up testing by running ping and DNS tests concurrently:

```bash
python3 -m nettest --parallel
```

### Continuous Monitoring

Run a live dashboard that continuously monitors network connectivity:

```bash
# Monitor with default 30-second interval
python3 -m nettest --monitor

# Monitor with custom 60-second interval
python3 -m nettest --monitor --interval 60

# Monitor specific targets
python3 -m nettest --monitor --targets "Router:192.168.1.1,Google:8.8.8.8"
```

The monitoring dashboard shows:
- **Status** - Overall connection health (GOOD/FAIR/WARN/DOWN)
- **Latency** - Current ping time with color-coded thresholds
- **Jitter** - Latency variance
- **Loss** - Packet loss percentage
- **Trend** - Arrow indicating if latency is improving (↘), stable (→), or degrading (↗)
- **Min/Max** - Range of observed latencies

Press `Ctrl+C` to stop monitoring.

### IPv4/IPv6 Testing

Force a specific IP protocol for testing:

```bash
# Force IPv4 only
python3 -m nettest -4

# Force IPv6 only
python3 -m nettest -6

# Test IPv6 connectivity to specific targets
python3 -m nettest --ipv6 --targets "Google:ipv6.google.com,CF:2606:4700:4700::1111"
```

### Historical Comparison

Track network performance over time by saving results to a history file:

```bash
# First run - saves baseline
python3 -m nettest --history ~/nettest_history.json

# Subsequent runs - shows comparison with previous run
python3 -m nettest --history ~/nettest_history.json
```

The comparison table shows:
- **Current vs Previous** values for latency, packet loss, and speed
- **Change indicators**: `→ stable` (<5% change), `↓ improved` (green), `↑ degraded` (red)
- **Percentage change** for significant differences

History file keeps the last 100 test results in JSON format.

### Problem Diagnosis

The tool analyzes test results and identifies the likely source of problems:

| Category | Description | Typical Causes |
|----------|-------------|----------------|
| **LOCAL** | Problem with your local network | Router issues, WiFi interference, cable problems |
| **ISP** | Problem with your Internet Service Provider | Congestion, outages, throttling |
| **INTERNET** | Problem with internet backbone | Routing issues, peering problems |
| **TARGET** | Problem with specific service | Server issues, DDoS, maintenance |
| **NONE** | No significant issues | Connection is healthy |

### Thresholds

Default thresholds for status indicators (configurable in YAML):

| Metric | Good | Warning | Bad |
|--------|------|---------|-----|
| Latency | <50ms | 50-100ms | >100ms |
| Jitter | <15ms | 15-30ms | >30ms |
| Packet Loss | 0% | <2% | >2% |
| Download Speed | >80% of expected | 50-80% | <50% |

### Prerequisites

**Required:**
- Python 3.8+
- `rich` library (for terminal output)

**Optional:**
- `pyyaml` - For YAML config files
- `speedtest-cli` - For speed tests
- `mtr` - For route analysis
- `dig` - For DNS tests (usually pre-installed)

Install prerequisites:
```bash
# Install Python dependencies
pip install rich pyyaml

# Install network tools (Ubuntu/Debian)
sudo apt install speedtest-cli mtr-tiny dnsutils

# Install network tools (Fedora/RHEL)
sudo dnf install speedtest-cli mtr bind-utils
```

The tool will show which dependencies are missing at startup:
```
┌───────────────┬─────────────┬────────────────────────────────────┐
│ Tool          │   Status    │ Purpose                            │
├───────────────┼─────────────┼────────────────────────────────────┤
│ ping          │ ✓ Available │ Basic connectivity test (required) │
│ dig           │ ✓ Available │ DNS resolution testing             │
│ mtr           │ ✓ Available │ Route analysis and traceroute      │
│ speedtest-cli │  ✗ Missing  │ Internet speed testing             │
└───────────────┴─────────────┴────────────────────────────────────┘
```

### Automation

#### Cron Job
```bash
# Add to crontab (crontab -e)
# Run every 6 hours, save reports
0 */6 * * * cd /home/user/docker/scripts && /usr/bin/python3 -m nettest \
  --profile quick --quiet --no-browser \
  --output /home/user/network-reports \
  --log-file /var/log/nettest.log
```

#### Systemd Timer

Create `/etc/systemd/system/nettest.service`:
```ini
[Unit]
Description=Network Testing Tool

[Service]
Type=oneshot
WorkingDirectory=/home/user/docker/scripts
ExecStart=/usr/bin/python3 -m nettest \
  --profile quick --quiet --no-browser \
  --log-file /var/log/nettest.log
User=user
```

Create `/etc/systemd/system/nettest.timer`:
```ini
[Unit]
Description=Run network tests periodically

[Timer]
OnBootSec=5min
OnUnitActiveSec=6h

[Install]
WantedBy=timers.target
```

Enable: `sudo systemctl enable --now nettest.timer`

### Troubleshooting

<details>
<summary><strong>speedtest-cli not found</strong></summary>

Install speedtest-cli:
```bash
# Ubuntu/Debian
sudo apt install speedtest-cli

# Or via pip
pip install speedtest-cli
```

</details>

<details>
<summary><strong>mtr not installed</strong></summary>

Install mtr:
```bash
# Ubuntu/Debian
sudo apt install mtr-tiny

# Fedora/RHEL
sudo dnf install mtr
```

</details>

<details>
<summary><strong>Permission denied for mtr</strong></summary>

mtr requires root for some operations:
```bash
# Option 1: Run script with sudo
cd ~/docker/scripts && sudo python3 -m nettest

# Option 2: Give mtr capabilities
sudo setcap cap_net_raw+ep /usr/sbin/mtr
```

</details>

<details>
<summary><strong>HTML report doesn't open</strong></summary>

```bash
# Run without browser
cd ~/docker/scripts && python3 -m nettest --no-browser

# Manually open the report
xdg-open /tmp/nettest_report_*.html
```

</details>

<details>
<summary><strong>pyyaml not installed</strong></summary>

YAML config files require pyyaml:
```bash
pip install pyyaml
```

Without it, the tool uses built-in defaults.

</details>

### Docker Usage

Run network tests in a container for isolation and portability:

```bash
# Start monitoring mode with Prometheus metrics
docker compose -f docker-compose.nettest.yml up -d

# Run one-shot test
docker compose -f docker-compose.nettest.yml run --rm nettest --profile full

# View logs
docker compose -f docker-compose.nettest.yml logs -f

# Check Prometheus metrics
curl http://localhost:9101/metrics
```

The Docker configuration includes:
- **Port 9101**: Prometheus metrics endpoint
- **Volumes**: `/config` (YAML config), `/output` (HTML reports), `/data` (logs, history)
- **Capability**: `NET_RAW` for ping and mtr

Configuration file: `nettest/config/nettest.yml`

### Network Interface Selection

Test from a specific network interface (useful for multi-homed systems, VPNs):

```bash
# List available interfaces
python3 -m nettest --list-interfaces

# Test using specific interface
python3 -m nettest --interface eth0 --profile quick
python3 -m nettest -I wlan0 --profile full
```

### Configuration Wizard

Run the interactive wizard to generate a config file:

```bash
python3 -m nettest --wizard
```

The wizard guides you through:
1. Test targets configuration
2. Test parameters (ping count, MTR count)
3. Threshold settings
4. Output preferences
5. Logging options
6. Alert configuration
7. Save to YAML file

### Prometheus Metrics

Expose metrics for Prometheus scraping:

```bash
# Enable metrics on port 9101
python3 -m nettest --monitor --prometheus-port 9101
```

Available metrics:
| Metric | Type | Description |
|--------|------|-------------|
| `nettest_ping_latency_ms` | Gauge | Latency (min/avg/max) per target |
| `nettest_ping_jitter_ms` | Gauge | Jitter per target |
| `nettest_ping_packet_loss_percent` | Gauge | Packet loss per target |
| `nettest_speedtest_download_mbps` | Gauge | Download speed |
| `nettest_speedtest_upload_mbps` | Gauge | Upload speed |
| `nettest_dns_resolution_time_ms` | Gauge | DNS lookup time per target |
| `nettest_test_runs_total` | Counter | Total test runs (success/failure) |

Grafana dashboard example: Import dashboard ID or use the metrics directly.

### Integration with Troubleshooting

Use this tool when:
- Services can't connect to external APIs
- Downloads are slow or failing
- Streaming is buffering
- VPN connection is unstable

The diagnosis helps determine if the issue is:
- Something you can fix (local/router)
- Something to report to ISP
- Something temporary (internet/target)

---

[← Back to README](../README.md)
