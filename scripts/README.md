# nettest

A simple, powerful network testing tool. Find out if your internet is working well in seconds.

## Quick Start

```bash
# Install
pip install git+https://github.com/manumanohar11/nettest.git

# Run
nettest
```

That's it! You'll see a report of your network health.

---

## What Does It Do?

nettest checks your internet connection and tells you:

- **Is my internet fast?** - Tests download/upload speeds
- **Is my connection stable?** - Measures latency, jitter, packet loss
- **Can I use video calls?** - Tests Zoom, Teams, Meet, WhatsApp, Webex
- **Where's the problem?** - Traces the route to find issues
- **What should I do?** - Gives actionable recommendations

## Installation

### Option 1: Install from GitHub (Recommended)

```bash
pip install git+https://github.com/manumanohar11/nettest.git
```

### Option 2: Install locally (for development)

```bash
git clone https://github.com/manumanohar11/nettest.git
cd nettest
pip install -e .
```

### Option 3: Run without installing

```bash
git clone https://github.com/manumanohar11/nettest.git
cd nettest
python -m nettest
```

## Usage Examples

### Basic Usage

```bash
# Simple output (for non-technical users)
nettest --simple

# Quick test (fastest, ~10 seconds)
nettest --profile quick

# Full test (comprehensive, ~2-3 minutes)
nettest --profile full
```

### Test Video Conferencing

```bash
# Check if Zoom, Teams, Meet, etc. will work
nettest --video-services
```

### Generate Reports

```bash
# HTML report (opens in browser)
nettest --format html

# JSON output (for scripts/automation)
nettest --format json

# Save to specific location
nettest --format html --output ~/Desktop
```

### Track History

```bash
# Save results to database
nettest --history-db

# View trends over time
nettest --history-trends

# View statistics
nettest --history-stats
```

### Interactive Modes

```bash
# Menu-driven interface
nettest --interactive

# Live monitoring dashboard
nettest --monitor

# Configuration wizard
nettest --wizard
```

### Advanced

```bash
# Use specific network interface
nettest --interface eth0

# Test specific targets
nettest --targets "Google:8.8.8.8,Cloudflare:1.1.1.1"

# Start REST API server
nettest --api --api-port 8080

# Check specific ports
nettest --check-ports 80,443,22

# Check HTTP endpoints
nettest --check-http https://example.com
```

## Output Modes

### Simple Mode (--simple)
For non-technical users. Shows a letter grade and plain English summary:

```
Your Internet: A+ ★★★★★
Your connection is Excellent

Speed: Fast (95 Mbps down | 20 Mbps up)
Responsiveness: Excellent (12ms)
```

### Standard Mode (default)
Technical details with color-coded tables showing latency, jitter, packet loss, and route analysis.

### HTML Report (--format html)
Beautiful interactive report with charts, saved to a file and opened in your browser.

## Profiles

| Profile | What it tests | Time |
|---------|--------------|------|
| `quick` | Ping only | ~10 sec |
| `full` | Everything (ping, speed, DNS, routes, video services) | ~3 min |
| `gaming` | Optimized for gaming (low latency focus) | ~1 min |
| `voip` | Optimized for voice/video calls | ~1 min |
| `streaming` | Optimized for streaming | ~1 min |

```bash
nettest --profile gaming
```

## System Requirements

### Required
- Python 3.9 or newer
- `ping` command (included in all operating systems)

### Optional (for full functionality)

| Tool | What it enables | Install |
|------|-----------------|---------|
| `speedtest-cli` | Speed tests | `pip install speedtest-cli` or `apt install speedtest-cli` |
| `mtr` | Route analysis | `apt install mtr` or `brew install mtr` |
| `dig` | DNS timing | `apt install dnsutils` or `brew install bind` |

**Ubuntu/Debian:**
```bash
sudo apt install speedtest-cli mtr dnsutils
```

**macOS:**
```bash
brew install speedtest-cli mtr
```

**Windows:**
Use WSL (Windows Subsystem for Linux) for best results, or install speedtest-cli via pip.

## Configuration

Create a config file at `./nettest.yml` or `~/.config/nettest/config.yml`:

```yaml
# Targets to test
targets:
  - 8.8.8.8        # Google DNS
  - 1.1.1.1        # Cloudflare DNS
  - your-server.com

# Your ISP speed (for scoring)
tests:
  expected_speed: 100  # Mbps

# Thresholds (when to warn)
thresholds:
  latency:
    good: 50      # ms
    warning: 100  # ms
  packet_loss:
    good: 1       # %
    warning: 5    # %
```

Or run the wizard:
```bash
nettest --wizard
```

## REST API

Start an API server for integration with other tools:

```bash
nettest --api --api-port 8080
```

Endpoints:
- `GET /health` - Health check
- `GET /run` - Run quick test
- `GET /run/full` - Run full test
- `GET /metrics` - Prometheus metrics

```bash
curl http://localhost:8080/health
curl http://localhost:8080/run
```

## Docker

```bash
# Build
docker build -t nettest .

# Run
docker run --rm nettest --profile quick --simple

# With network access for accurate results
docker run --rm --net=host nettest --profile full
```

## Project Structure

```
nettest/
├── cli/           # Command-line interface
├── tests/         # Network test implementations
├── output/        # Output formatters (terminal, HTML, JSON)
├── api/           # REST API server
├── tui/           # Interactive interfaces (wizard, monitor)
├── utils/         # Utilities (commands, storage, network)
├── alerts/        # Alerting and thresholds
└── models.py      # Data models
```

## Troubleshooting

### "Permission denied" when pinging
```bash
# On Linux, you may need:
sudo setcap cap_net_raw+ep $(which ping)
```

### "speedtest-cli not found"
```bash
pip install speedtest-cli
# or
sudo apt install speedtest-cli
```

### "mtr requires root"
```bash
# Run with sudo for MTR features
sudo nettest --profile full
```

### Tests are slow
```bash
# Use quick profile
nettest --profile quick
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest tests/`
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Made with ❤️ for anyone who's ever wondered "Is it my internet or is it the website?"**
