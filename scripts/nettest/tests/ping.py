"""Ping test implementation."""

import re
from typing import Optional

from ..models import PingResult
from ..utils.commands import run_command


def run_ping_test(
    target: str,
    target_name: str,
    count: int = 10,
    ip_version: Optional[int] = None,
    interface: Optional[str] = None,
) -> PingResult:
    """
    Run ping test and parse results.

    Args:
        target: Hostname or IP to ping
        target_name: Display name for the target
        count: Number of ping packets to send
        ip_version: Force IPv4 (4) or IPv6 (6), or None for auto
        interface: Network interface to use (e.g., "eth0")

    Returns:
        PingResult with latency statistics
    """
    result = PingResult(target=target, target_name=target_name)

    cmd = ["ping", "-c", str(count), "-W", "2"]
    if ip_version == 4:
        cmd.append("-4")
    elif ip_version == 6:
        cmd.append("-6")
    if interface:
        cmd.extend(["-I", interface])
    cmd.append(target)

    exit_code, stdout, stderr = run_command(cmd, timeout=count * 3 + 10)

    if exit_code != 0 and not stdout:
        # Provide actionable error messages (technical and simple)
        if "Name or service not known" in stderr or "Temporary failure in name resolution" in stderr:
            result.error = f"DNS resolution failed for '{target}'. Check your DNS settings or try an IP address."
            result.error_simple = "Cannot find server. Try: check if the address is correct"
        elif "Network is unreachable" in stderr:
            result.error = "Network unreachable. Check your network connection and default gateway."
            result.error_simple = "Cannot reach the internet. Try: check your WiFi connection"
        elif "Operation not permitted" in stderr:
            result.error = "Permission denied. Try running with sudo or check firewall settings."
            result.error_simple = "Permission issue. Try: run the program with administrator access"
        elif "Command timed out" in stderr:
            result.error = f"Ping timed out after {count * 3 + 10}s. Host may be down or blocking ICMP."
            result.error_simple = "Connection too slow. Try: restart your router"
        elif "Command not found" in stderr:
            result.error = "ping not found. Install: sudo apt install iputils-ping"
            result.error_simple = "Ping tool not installed. Ask your system administrator for help"
        elif "SO_BINDTODEVICE" in stderr or "invalid argument" in stderr.lower():
            result.error = f"Cannot bind to interface '{interface}'. Check interface name or run with sudo."
            result.error_simple = "Network interface issue. Try: check your network adapter settings"
        else:
            result.error = stderr or "Ping failed - check network connectivity"
            result.error_simple = "Connection failed. Try: check your internet connection"
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
