# Quickstart Guide: Windows

This guide covers installing and running nettest on Windows.

## Installation

### Install Python

Download Python 3.9+ from [python.org](https://www.python.org/downloads/windows/).

During installation, check "Add Python to PATH".

### Install nettest

Open Command Prompt or PowerShell:

```powershell
pip install nettest
```

For all optional features:

```powershell
pip install nettest[full]
```

### Install speedtest-cli

```powershell
pip install speedtest-cli
```

## Quick Test

Run a fast connectivity check:

```powershell
nettest --profile quick
```

Run a full diagnostic:

```powershell
nettest --profile full
```

Test video conferencing services:

```powershell
nettest --video-services
```

Generate an HTML report:

```powershell
nettest --format html --output network-report.html
```

## Using WSL for Best Experience

Windows Subsystem for Linux provides the best nettest experience with full tool support.

### Install WSL

```powershell
wsl --install
```

Restart your computer, then set up Ubuntu when prompted.

### Install nettest in WSL

```bash
sudo apt update
sudo apt install python3-pip speedtest-cli mtr dnsutils
pip install nettest[full]
```

Run nettest:

```bash
nettest --profile full
```

## Windows-Specific Notes

### MTR Alternatives

MTR is not natively available on Windows. Alternatives:

- **WinMTR**: Download from [winmtr.net](https://winmtr.net/)
- **PathPing**: Built into Windows, use via Command Prompt

When MTR is unavailable, nettest will skip route analysis tests.

### Ping Limitations

Windows ping works differently than Unix ping. Some features may behave differently:

- Packet sizes may be limited
- Timing precision varies

### PowerShell vs Command Prompt

Both work, but PowerShell provides better Unicode support for the Rich terminal output.

## Scheduled Task for Monitoring

Create a scheduled task using Task Scheduler:

1. Open Task Scheduler (`taskschd.msc`)
2. Click "Create Basic Task"
3. Name: "Network Test Monitor"
4. Trigger: Daily, repeat every 15 minutes
5. Action: Start a program
6. Program: `python`
7. Arguments: `-m nettest --profile quick --format json --output C:\Logs\nettest.json`

Or via PowerShell:

```powershell
$action = New-ScheduledTaskAction -Execute "python" -Argument "-m nettest --profile quick --format json --output C:\Logs\nettest.json"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15)
Register-ScheduledTask -TaskName "NettestMonitor" -Action $action -Trigger $trigger
```

## Troubleshooting

### 'nettest' is not recognized

Python scripts directory may not be in PATH. Use:

```powershell
python -m nettest --profile quick
```

Or add Python Scripts to PATH:

```powershell
$env:PATH += ";$env:APPDATA\Python\Python312\Scripts"
```

### Permission denied errors

Run PowerShell as Administrator for some network operations:

1. Right-click PowerShell
2. Select "Run as administrator"

### speedtest-cli fails

Try the alternative speedtest package:

```powershell
pip uninstall speedtest-cli
pip install speedtest-cli --force-reinstall
```

### Unicode/emoji display issues

Use Windows Terminal instead of Command Prompt for better Unicode support:

```powershell
winget install Microsoft.WindowsTerminal
```

### Firewall blocking tests

Ensure Python is allowed through Windows Firewall:

1. Open Windows Security
2. Firewall & network protection
3. Allow an app through firewall
4. Add Python

## Next Steps

- See the main [README](../README.md) for full documentation
- Run `nettest --wizard` for interactive configuration setup
- Consider using WSL for full Linux tool compatibility
