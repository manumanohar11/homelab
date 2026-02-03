"""Network diagnostic analysis to determine problem location."""

from typing import List, Dict, Any, Optional, Tuple

from .models import PingResult, SpeedTestResult, MtrResult, MtrHop, DiagnosticResult


def diagnose_network(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    mtr_results: List[MtrResult],
    expected_speed: float,
    thresholds: Dict[str, Any],
) -> DiagnosticResult:
    """
    Analyze test results to determine where problems are occurring.

    Args:
        ping_results: Results from ping tests
        speedtest_result: Result from speed test
        mtr_results: Results from MTR route analysis
        expected_speed: Expected download speed in Mbps
        thresholds: Threshold configuration

    Returns:
        DiagnosticResult with problem category, confidence, and recommendations
    """
    issues: List[str] = []
    local_issues: List[str] = []
    isp_issues: List[str] = []
    internet_issues: List[str] = []
    target_issues: Dict[str, List[str]] = {}

    # Check speedtest results
    if speedtest_result.success:
        dl_pct = (speedtest_result.download_mbps / expected_speed) * 100 if expected_speed > 0 else 100
        if dl_pct < 50:
            isp_issues.append(f"Download speed is only {dl_pct:.0f}% of expected ({speedtest_result.download_mbps:.1f}/{expected_speed} Mbps)")
        elif dl_pct < 80:
            isp_issues.append(f"Download speed is below expected ({dl_pct:.0f}% of {expected_speed} Mbps)")

        if speedtest_result.ping_ms > 100:
            isp_issues.append(f"High latency to speed test server ({speedtest_result.ping_ms:.0f}ms)")
    else:
        issues.append("Speed test failed - cannot assess bandwidth")

    # Analyze ping results by target
    successful_pings = [p for p in ping_results if p.success]
    failed_pings = [p for p in ping_results if not p.success]

    # Check if all pings failed (likely local/ISP issue)
    if len(failed_pings) == len(ping_results):
        local_issues.append("All ping tests failed - check your network connection")
    elif failed_pings:
        for p in failed_pings:
            target_issues.setdefault(p.target_name, []).append(f"Ping failed: {p.error}")

    # Analyze successful pings
    high_latency_all = True
    high_loss_all = True
    high_jitter_all = True

    latency_threshold = thresholds.get("latency", {}).get("warning", 100)
    loss_threshold = thresholds.get("packet_loss", {}).get("warning", 2)
    jitter_threshold = thresholds.get("jitter", {}).get("warning", 30)

    for p in successful_pings:
        is_high_latency = p.avg_ms > latency_threshold
        is_high_loss = p.packet_loss > loss_threshold
        is_high_jitter = p.jitter_ms > jitter_threshold

        if not is_high_latency:
            high_latency_all = False
        if not is_high_loss:
            high_loss_all = False
        if not is_high_jitter:
            high_jitter_all = False

        # Target-specific issues
        if is_high_latency or is_high_loss or is_high_jitter:
            target_issue_list = target_issues.setdefault(p.target_name, [])
            if is_high_latency:
                target_issue_list.append(f"High latency ({p.avg_ms:.0f}ms)")
            if is_high_loss:
                target_issue_list.append(f"Packet loss ({p.packet_loss:.1f}%)")
            if is_high_jitter:
                target_issue_list.append(f"High jitter ({p.jitter_ms:.1f}ms)")

    # If all successful pings have issues, it's likely ISP/local
    if successful_pings:
        if high_latency_all:
            isp_issues.append("High latency to all tested servers")
        if high_loss_all:
            isp_issues.append("Packet loss to all tested servers")
        if high_jitter_all:
            isp_issues.append("High jitter (unstable connection) to all servers")

    # Analyze MTR results to pinpoint where problems start
    for mtr in mtr_results:
        if not mtr.success or not mtr.hops:
            continue

        first_problem_hop: Optional[Tuple[int, MtrHop]] = None
        for i, hop in enumerate(mtr.hops):
            if hop.loss_pct > loss_threshold or hop.avg_ms > latency_threshold:
                first_problem_hop = (i, hop)
                break

        if first_problem_hop:
            hop_num, hop = first_problem_hop
            # First few hops (0-2) are typically local/router
            # Hops 3-6 are typically ISP
            # Later hops are internet backbone/target
            if hop_num <= 2:
                local_issues.append(f"Problems start at hop {hop.hop_number} ({hop.host}) - likely local network/router issue")
            elif hop_num <= 6:
                isp_issues.append(f"Problems start at hop {hop.hop_number} ({hop.host}) - likely ISP issue")
            else:
                internet_issues.append(f"Problems start at hop {hop.hop_number} ({hop.host}) - internet backbone issue")

    # Determine the primary problem category
    category: str = "none"
    confidence: str = "low"
    summary: str = ""
    details: List[str] = []
    recommendations: List[str] = []

    if local_issues:
        category = "local"
        confidence = "high" if len(local_issues) > 1 else "medium"
        summary = "Problem appears to be with your local network"
        details = local_issues
        recommendations = [
            "Restart your router/modem",
            "Check Ethernet cable connections",
            "Try connecting via Ethernet instead of WiFi",
            "Check for local network congestion (other devices using bandwidth)",
        ]
    elif isp_issues:
        category = "isp"
        confidence = "high" if len(isp_issues) > 1 else "medium"
        summary = "Problem appears to be with your ISP"
        details = isp_issues
        recommendations = [
            "Contact your ISP to report the issue",
            "Check ISP status page for outages",
            "Try rebooting your modem",
            "Test at different times of day (peak congestion)",
        ]
    elif internet_issues:
        category = "internet"
        confidence = "medium"
        summary = "Problem appears to be with internet backbone/routing"
        details = internet_issues
        recommendations = [
            "This is typically temporary - try again later",
            "Use a VPN to route around the problem",
            "The issue is outside your control",
        ]
    elif target_issues:
        # Check if issues are target-specific
        targets_with_issues = list(target_issues.keys())
        targets_ok = [p.target_name for p in successful_pings if p.target_name not in targets_with_issues]

        if targets_ok:
            category = "target"
            confidence = "high"
            summary = f"Problem appears to be specific to: {', '.join(targets_with_issues)}"
            for target, issue_list in target_issues.items():
                details.extend([f"{target}: {issue}" for issue in issue_list])
            recommendations = [
                "The target servers may be experiencing issues",
                "Check status pages for affected services",
                "Try alternative servers/services",
            ]
        else:
            category = "internet"
            confidence = "low"
            summary = "General connectivity issues detected"
            for target, issue_list in target_issues.items():
                details.extend([f"{target}: {issue}" for issue in issue_list])
            recommendations = [
                "Monitor the situation - it may be temporary",
                "Check if other devices have the same issue",
            ]
    else:
        category = "none"
        confidence = "high"
        summary = "No significant network issues detected"
        details = ["All tests passed within acceptable thresholds"]
        recommendations = ["Your network connection appears healthy"]

    return DiagnosticResult(
        category=category,
        confidence=confidence,
        summary=summary,
        details=details,
        recommendations=recommendations
    )
