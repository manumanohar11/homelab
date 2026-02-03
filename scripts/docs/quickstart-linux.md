# Quickstart Guide: Linux

This guide covers installing and running nettest on Linux distributions.

## Installation

### Install nettest

```bash
pip install nettest
```

For all optional features:

```bash
pip install nettest[full]
```

### Install System Tools

The following system tools enable full functionality:

**Debian/Ubuntu:**

```bash
sudo apt update
sudo apt install speedtest-cli mtr dnsutils iputils-ping
```

**Fedora/RHEL/CentOS:**

```bash
sudo dnf install speedtest-cli mtr bind-utils iputils
```

**Arch Linux:**

```bash
sudo pacman -S speedtest-cli mtr bind-tools iputils
```

## Quick Test

Run a fast connectivity check:

```bash
nettest --profile quick
```

Run a full diagnostic:

```bash
nettest --profile full
```

Test video conferencing services:

```bash
nettest --video-services
```

## Running as a Systemd Timer

Create a systemd service and timer for scheduled monitoring.

**Service file** (`/etc/systemd/system/nettest.service`):

```ini
[Unit]
Description=Network Testing Tool
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/nettest --profile quick --format json --output /var/log/nettest/result.json
User=nobody
```

**Timer file** (`/etc/systemd/system/nettest.timer`):

```ini
[Unit]
Description=Run nettest every 15 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo mkdir -p /var/log/nettest
sudo systemctl daemon-reload
sudo systemctl enable --now nettest.timer
```

## Using with Docker

```bash
docker run --rm --cap-add NET_RAW nettest --profile quick
```

See [quickstart-docker.md](quickstart-docker.md) for detailed Docker instructions.

## Troubleshooting

### Permission denied for ping

Some systems require raw socket permissions:

```bash
sudo setcap cap_net_raw+ep $(which ping)
```

Or run nettest with sudo for ICMP tests.

### speedtest-cli not found

Install via pip if the system package is unavailable:

```bash
pip install speedtest-cli
```

### MTR requires root

MTR needs raw socket access. Either run with sudo or set capabilities:

```bash
sudo setcap cap_net_raw+ep $(which mtr)
```

### dig command not found

Install DNS utilities:

```bash
# Debian/Ubuntu
sudo apt install dnsutils

# Fedora/RHEL
sudo dnf install bind-utils
```

## Next Steps

- See the main [README](../README.md) for full documentation
- Run `nettest --wizard` for interactive configuration setup
- Use `nettest --interactive` for menu-driven test selection
