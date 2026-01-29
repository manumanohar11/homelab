"""DNS resolution test implementation."""

import re

from ..models import DnsResult
from ..utils.commands import run_command


def run_dns_test(target: str) -> DnsResult:
    """
    Test DNS resolution time using dig.

    Args:
        target: Hostname to resolve

    Returns:
        DnsResult with resolution time and resolved IP
    """
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
