# Quickstart Guide: macOS

This guide covers installing and running nettest on macOS.

## Installation

### Install nettest

Using pip:

```bash
pip install nettest
```

For all optional features:

```bash
pip install nettest[full]
```

### Install System Tools with Homebrew

Install Homebrew if not already installed:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Install network testing tools:

```bash
brew install speedtest-cli mtr
```

Note: macOS includes `ping` and `dig` by default.

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

Generate an HTML report:

```bash
nettest --format html --output ~/Desktop/network-report.html
```

## macOS-Specific Notes

### Ping and Raw Sockets

macOS restricts raw socket access. Some ping options may require elevated privileges:

```bash
sudo nettest --profile full
```

For regular use without sudo, the standard ping functionality works fine.

### MTR Requires sudo

MTR needs raw socket access on macOS:

```bash
sudo mtr google.com
```

When running nettest, MTR tests will be skipped if not running with appropriate permissions.

### Gatekeeper and Python

If you installed Python via Homebrew, ensure it is in your PATH:

```bash
export PATH="/opt/homebrew/bin:$PATH"
```

Add this to your `~/.zshrc` for persistence.

## Running as a Launch Agent

Create a scheduled task using launchd.

**Plist file** (`~/Library/LaunchAgents/com.nettest.monitor.plist`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nettest.monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/nettest</string>
        <string>--profile</string>
        <string>quick</string>
        <string>--format</string>
        <string>json</string>
        <string>--output</string>
        <string>/tmp/nettest-result.json</string>
    </array>
    <key>StartInterval</key>
    <integer>900</integer>
    <key>StandardOutPath</key>
    <string>/tmp/nettest.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/nettest-error.log</string>
</dict>
</plist>
```

Load the agent:

```bash
launchctl load ~/Library/LaunchAgents/com.nettest.monitor.plist
```

## Troubleshooting

### Command not found: nettest

Ensure pip installed to a directory in your PATH:

```bash
python -m nettest --profile quick
```

Or add the pip bin directory to PATH:

```bash
export PATH="$HOME/Library/Python/3.x/bin:$PATH"
```

### speedtest-cli not found

Install via Homebrew:

```bash
brew install speedtest-cli
```

### MTR shows no output

MTR requires sudo on macOS:

```bash
sudo nettest --profile full
```

### SSL certificate errors

Update certificates:

```bash
pip install --upgrade certifi
```

### Rich library display issues

If terminal output looks broken, ensure your terminal supports Unicode:

```bash
export LANG=en_US.UTF-8
```

## Next Steps

- See the main [README](../README.md) for full documentation
- Run `nettest --wizard` for interactive configuration setup
- Use `nettest --monitor` for live dashboard monitoring
