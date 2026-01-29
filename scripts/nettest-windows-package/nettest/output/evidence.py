"""Generate ISP complaint evidence."""

from datetime import datetime
from typing import List
from ..models import (
    PingResult, SpeedTestResult, MtrResult,
    DiagnosticResult, ISPEvidence
)


def generate_isp_evidence(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    mtr_results: List[MtrResult],
    diagnostic: DiagnosticResult,
    expected_speed: float,
) -> ISPEvidence:
    """Generate documentation-ready evidence for ISP complaints."""
    evidence = ISPEvidence(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    complaints = []

    # Speed complaint
    if speedtest_result.success and expected_speed > 0:
        pct = (speedtest_result.download_mbps / expected_speed) * 100
        if pct < 80:
            deficit = 100 - pct
            evidence.speed_complaint = (
                f"Download speed {speedtest_result.download_mbps:.1f} Mbps vs "
                f"{expected_speed:.0f} Mbps expected ({deficit:.0f}% deficit)"
            )
            complaints.append(f"Speed: {evidence.speed_complaint}")

    # Packet loss complaint
    loss_targets = []
    for pr in ping_results:
        if pr.success and pr.packet_loss > 0:
            loss_targets.append(f"{pr.packet_loss:.0f}% loss to {pr.target_name}")
    if loss_targets:
        evidence.packet_loss_complaint = "; ".join(loss_targets)
        complaints.append(f"Packet Loss: {evidence.packet_loss_complaint}")

    # Latency complaint
    high_latency = []
    for pr in ping_results:
        if pr.success and pr.avg_ms > 100:
            high_latency.append(f"{pr.target_name}: {pr.avg_ms:.0f}ms")
    if high_latency:
        evidence.latency_complaint = "; ".join(high_latency)
        complaints.append(f"High Latency: {evidence.latency_complaint}")

    # Problem hops from MTR
    for mtr in mtr_results:
        if mtr.success:
            for hop in mtr.hops:
                if hop.loss_pct >= 10 and hop.host != "???":
                    evidence.problem_hops.append(
                        f"{mtr.target_name} Hop {hop.hop_number}: {hop.host} - "
                        f"{hop.loss_pct:.0f}% loss, {hop.avg_ms:.0f}ms avg"
                    )

    # Summary
    if complaints:
        evidence.summary = f"Network issues detected: {'; '.join(complaints)}"
    else:
        evidence.summary = "No significant issues detected"

    # Copy recommendations from diagnostic
    evidence.recommendations = diagnostic.recommendations.copy()

    return evidence
