"""Threshold checking for alert generation."""

from dataclasses import dataclass
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import PingResult, SpeedTestResult, DnsResult


@dataclass
class ThresholdViolation:
    """Represents a threshold violation that should trigger an alert."""
    metric: str  # e.g., "latency", "packet_loss", "download_speed"
    target: str  # Target name or "speedtest"
    value: float  # Actual value
    threshold: float  # Threshold that was exceeded
    severity: str  # "warning" or "critical"
    message: str  # Human-readable description


def check_thresholds(
    ping_results: List["PingResult"],
    speedtest_result: "SpeedTestResult",
    dns_results: List["DnsResult"],
    thresholds: Dict[str, Any],
    expected_speed: float,
) -> List[ThresholdViolation]:
    """
    Check test results against thresholds and return violations.

    Args:
        ping_results: List of ping test results
        speedtest_result: Speed test result
        dns_results: List of DNS test results
        thresholds: Threshold configuration dict
        expected_speed: Expected download speed in Mbps

    Returns:
        List of ThresholdViolation objects for metrics exceeding thresholds
    """
    violations = []

    # Get threshold values with defaults
    latency_warn = thresholds.get("latency", {}).get("warning", 100)
    latency_crit = thresholds.get("latency", {}).get("critical", latency_warn * 2)

    jitter_warn = thresholds.get("jitter", {}).get("warning", 30)
    jitter_crit = thresholds.get("jitter", {}).get("critical", jitter_warn * 2)

    loss_warn = thresholds.get("packet_loss", {}).get("warning", 2)
    loss_crit = thresholds.get("packet_loss", {}).get("critical", 10)

    dl_warn_pct = thresholds.get("download_pct", {}).get("warning", 50)
    dl_crit_pct = thresholds.get("download_pct", {}).get("critical", 25)

    # Check ping results
    for result in ping_results:
        if not result.success:
            violations.append(ThresholdViolation(
                metric="connectivity",
                target=result.target_name,
                value=0,
                threshold=0,
                severity="critical",
                message=f"Ping failed to {result.target_name}: {result.error}"
            ))
            continue

        # Check latency
        if result.avg_ms > latency_crit:
            violations.append(ThresholdViolation(
                metric="latency",
                target=result.target_name,
                value=result.avg_ms,
                threshold=latency_crit,
                severity="critical",
                message=f"Critical latency to {result.target_name}: {result.avg_ms:.1f}ms (threshold: {latency_crit}ms)"
            ))
        elif result.avg_ms > latency_warn:
            violations.append(ThresholdViolation(
                metric="latency",
                target=result.target_name,
                value=result.avg_ms,
                threshold=latency_warn,
                severity="warning",
                message=f"High latency to {result.target_name}: {result.avg_ms:.1f}ms (threshold: {latency_warn}ms)"
            ))

        # Check jitter
        if result.jitter_ms > jitter_crit:
            violations.append(ThresholdViolation(
                metric="jitter",
                target=result.target_name,
                value=result.jitter_ms,
                threshold=jitter_crit,
                severity="critical",
                message=f"Critical jitter to {result.target_name}: {result.jitter_ms:.1f}ms (threshold: {jitter_crit}ms)"
            ))
        elif result.jitter_ms > jitter_warn:
            violations.append(ThresholdViolation(
                metric="jitter",
                target=result.target_name,
                value=result.jitter_ms,
                threshold=jitter_warn,
                severity="warning",
                message=f"High jitter to {result.target_name}: {result.jitter_ms:.1f}ms (threshold: {jitter_warn}ms)"
            ))

        # Check packet loss
        if result.packet_loss > loss_crit:
            violations.append(ThresholdViolation(
                metric="packet_loss",
                target=result.target_name,
                value=result.packet_loss,
                threshold=loss_crit,
                severity="critical",
                message=f"Critical packet loss to {result.target_name}: {result.packet_loss:.1f}% (threshold: {loss_crit}%)"
            ))
        elif result.packet_loss > loss_warn:
            violations.append(ThresholdViolation(
                metric="packet_loss",
                target=result.target_name,
                value=result.packet_loss,
                threshold=loss_warn,
                severity="warning",
                message=f"Packet loss to {result.target_name}: {result.packet_loss:.1f}% (threshold: {loss_warn}%)"
            ))

    # Check speed test
    if speedtest_result.success and expected_speed > 0:
        dl_pct = (speedtest_result.download_mbps / expected_speed) * 100
        if dl_pct < dl_crit_pct:
            violations.append(ThresholdViolation(
                metric="download_speed",
                target="speedtest",
                value=speedtest_result.download_mbps,
                threshold=expected_speed * dl_crit_pct / 100,
                severity="critical",
                message=f"Critical: Download speed {speedtest_result.download_mbps:.1f}Mbps is only {dl_pct:.0f}% of expected {expected_speed}Mbps"
            ))
        elif dl_pct < dl_warn_pct:
            violations.append(ThresholdViolation(
                metric="download_speed",
                target="speedtest",
                value=speedtest_result.download_mbps,
                threshold=expected_speed * dl_warn_pct / 100,
                severity="warning",
                message=f"Download speed {speedtest_result.download_mbps:.1f}Mbps is only {dl_pct:.0f}% of expected {expected_speed}Mbps"
            ))
    elif not speedtest_result.success:
        violations.append(ThresholdViolation(
            metric="speedtest",
            target="speedtest",
            value=0,
            threshold=0,
            severity="warning",
            message=f"Speed test failed: {speedtest_result.error}"
        ))

    return violations


def format_violations_summary(violations: List[ThresholdViolation]) -> str:
    """
    Format violations into a summary message.

    Args:
        violations: List of threshold violations

    Returns:
        Formatted summary string
    """
    if not violations:
        return "All metrics within acceptable thresholds."

    critical = [v for v in violations if v.severity == "critical"]
    warnings = [v for v in violations if v.severity == "warning"]

    lines = []
    if critical:
        lines.append(f"CRITICAL ({len(critical)}):")
        for v in critical:
            lines.append(f"  - {v.message}")

    if warnings:
        lines.append(f"WARNING ({len(warnings)}):")
        for v in warnings:
            lines.append(f"  - {v.message}")

    return "\n".join(lines)
