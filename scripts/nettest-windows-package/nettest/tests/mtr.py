"""MTR route analysis implementation."""

import json
import re
from typing import Optional

from ..models import MtrResult, MtrHop
from ..utils.commands import run_command


def run_mtr(
    target: str,
    target_name: str,
    count: int = 10,
    interface: Optional[str] = None,
) -> MtrResult:
    """
    Run mtr and parse results.

    Args:
        target: Hostname or IP to trace route to
        target_name: Display name for the target
        count: Number of packets per hop
        interface: Network interface to use (e.g., "eth0")

    Returns:
        MtrResult with hop-by-hop statistics
    """
    result = MtrResult(target=target, target_name=target_name)

    # Build base command
    base_cmd = ["mtr", "-c", str(count), "--no-dns"]
    if interface:
        base_cmd.extend(["-I", interface])

    # Try JSON output first
    cmd = base_cmd + ["--json", target]
    exit_code, stdout, stderr = run_command(cmd, timeout=count * 2 + 30)

    if exit_code == 0 and stdout:
        try:
            data = json.loads(stdout)
            hubs = data.get("report", {}).get("hubs", [])
            for hop in hubs:
                mtr_hop = MtrHop(
                    hop_number=hop.get("count", 0),
                    host=hop.get("host", "???"),
                    loss_pct=hop.get("Loss%", 0),
                    sent=hop.get("Snt", 0),
                    avg_ms=hop.get("Avg", 0),
                    best_ms=hop.get("Best", 0),
                    worst_ms=hop.get("Wrst", 0),
                )
                result.hops.append(mtr_hop)
            result.success = True
            return result
        except json.JSONDecodeError:
            pass

    # Fall back to report mode
    cmd = base_cmd + ["--report", "--report-wide", target]
    exit_code, stdout, stderr = run_command(cmd, timeout=count * 2 + 30)

    if exit_code != 0:
        # Provide actionable error messages
        if "Command not found" in stderr:
            result.error = (
                "mtr not found.\n"
                "  Install (Debian/Ubuntu): sudo apt install mtr-tiny\n"
                "  Install (Fedora/RHEL): sudo dnf install mtr"
            )
        elif "Operation not permitted" in stderr or "permission" in stderr.lower():
            result.error = (
                "mtr requires elevated privileges.\n"
                "  Option 1: Run with sudo: sudo python3 -m nettest\n"
                "  Option 2: Set capabilities: sudo setcap cap_net_raw+ep /usr/sbin/mtr"
            )
        elif "Name or service not known" in stderr:
            result.error = f"Cannot resolve '{target}'. Check DNS settings or use IP address."
        elif "SO_BINDTODEVICE" in stderr:
            result.error = f"Cannot bind to interface '{interface}'. Check interface name or run with sudo."
        else:
            result.error = stderr or "mtr failed - check network connectivity"
        return result

    # Parse report output
    # Format: HOST                             Loss%   Snt   Last   Avg  Best  Wrst StDev
    hop_pattern = r"^\s*(\d+)\.\s+(\S+)\s+(\d+\.?\d*)%\s+(\d+)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)"

    for line in stdout.split('\n'):
        match = re.match(hop_pattern, line)
        if match:
            mtr_hop = MtrHop(
                hop_number=int(match.group(1)),
                host=match.group(2),
                loss_pct=float(match.group(3)),
                sent=int(match.group(4)),
                avg_ms=float(match.group(6)),
                best_ms=float(match.group(7)),
                worst_ms=float(match.group(8)),
            )
            result.hops.append(mtr_hop)

    result.success = len(result.hops) > 0
    if not result.success:
        result.error = (
            "Could not parse mtr output. This may indicate:\n"
            "  - Target is unreachable (100% packet loss on all hops)\n"
            "  - Firewall blocking ICMP/UDP packets\n"
            "  - Incompatible mtr version (try updating mtr)"
        )

    return result
