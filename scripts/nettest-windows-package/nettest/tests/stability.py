"""Connection stability and health scoring."""

from typing import List
from ..models import PingResult, SpeedTestResult, ConnectionScore, VoIPQuality


def calculate_connection_score(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    expected_speed: float,
    bufferbloat_ms: float = 0.0,
) -> ConnectionScore:
    """
    Calculate overall connection health score.

    Args:
        ping_results: List of ping test results
        speedtest_result: Speed test result
        expected_speed: Expected download speed in Mbps
        bufferbloat_ms: Latency increase under load (for future use)

    Returns:
        ConnectionScore with overall health assessment
    """
    # Speed score: 0-100 based on % of expected
    if speedtest_result.success and expected_speed > 0:
        speed_pct = (speedtest_result.download_mbps / expected_speed) * 100
        speed_score = min(100, int(speed_pct))
    else:
        speed_score = 0

    # Latency score: 100 for <20ms, 0 for >200ms
    successful_pings = [p for p in ping_results if p.success]
    if successful_pings:
        avg_latency = sum(p.avg_ms for p in successful_pings) / len(successful_pings)
        if avg_latency <= 20:
            latency_score = 100
        elif avg_latency >= 200:
            latency_score = 0
        else:
            latency_score = int(100 - ((avg_latency - 20) / 180) * 100)
    else:
        latency_score = 0

    # Stability score: based on jitter and packet loss
    if successful_pings:
        avg_jitter = sum(p.jitter_ms for p in successful_pings) / len(successful_pings)
        avg_loss = sum(p.packet_loss for p in successful_pings) / len(successful_pings)

        # Jitter penalty: -2 points per ms over 5ms
        jitter_penalty = max(0, (avg_jitter - 5) * 2)

        # Loss penalty: -10 points per % loss
        loss_penalty = avg_loss * 10

        # Bufferbloat penalty (for future)
        bloat_penalty = bufferbloat_ms * 0.2

        stability_score = max(0, int(100 - jitter_penalty - loss_penalty - bloat_penalty))
    else:
        stability_score = 0

    # Weighted overall score
    overall = int(
        speed_score * 0.35 +
        latency_score * 0.30 +
        stability_score * 0.35
    )

    # Calculate grade
    grade = _score_to_grade(overall)

    # Generate summary
    summary = _generate_summary(overall, speed_score, latency_score, stability_score, ping_results)

    return ConnectionScore(
        overall=overall,
        grade=grade,
        speed_score=speed_score,
        latency_score=latency_score,
        stability_score=stability_score,
        summary=summary,
    )


def calculate_mos_score(
    latency_ms: float,
    jitter_ms: float,
    packet_loss_pct: float,
) -> VoIPQuality:
    """
    Calculate Mean Opinion Score using simplified ITU-T E-model.

    MOS Scale:
    - 4.3-5.0: Excellent (HD voice capable)
    - 4.0-4.3: Good (standard voice)
    - 3.6-4.0: Fair (acceptable)
    - 3.1-3.6: Poor (degraded)
    - 1.0-3.1: Bad (unusable)
    """
    # Effective latency (one-way + jitter buffer + codec delay)
    effective_latency = latency_ms + (jitter_ms * 2) + 10

    # Delay impairment
    if effective_latency < 160:
        delay_factor = effective_latency / 40
    else:
        delay_factor = (effective_latency - 120) / 10

    # Loss impairment
    loss_factor = packet_loss_pct * 2.5

    # R-factor
    r_factor = 93.2 - delay_factor - loss_factor
    r_factor = max(0, min(100, r_factor))

    # Convert to MOS
    if r_factor < 0:
        mos = 1.0
    elif r_factor > 100:
        mos = 4.5
    else:
        mos = 1 + 0.035 * r_factor + r_factor * (r_factor - 60) * (100 - r_factor) * 7e-6

    mos = round(max(1.0, min(5.0, mos)), 2)

    # Determine quality and suitability
    if mos >= 4.3:
        quality = "Excellent"
        suitable = ["HD Voice", "Video Conferencing", "VoIP"]
    elif mos >= 4.0:
        quality = "Good"
        suitable = ["Video Conferencing", "VoIP"]
    elif mos >= 3.6:
        quality = "Fair"
        suitable = ["VoIP", "Voice Calls"]
    elif mos >= 3.1:
        quality = "Poor"
        suitable = ["Basic Voice"]
    else:
        quality = "Bad"
        suitable = []

    return VoIPQuality(
        mos_score=mos,
        r_factor=round(r_factor, 1),
        quality=quality,
        suitable_for=suitable,
    )


def _score_to_grade(score: int) -> str:
    """Convert numeric score to letter grade."""
    if score >= 95:
        return "A+"
    elif score >= 90:
        return "A"
    elif score >= 85:
        return "B+"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def _generate_summary(
    overall: int,
    speed_score: int,
    latency_score: int,
    stability_score: int,
    ping_results: List[PingResult],
) -> str:
    """Generate human-readable summary of connection health."""
    has_loss = any(p.packet_loss > 0 for p in ping_results if p.success)

    if overall >= 90:
        return "Excellent - Connection is healthy"
    elif overall >= 80:
        if has_loss:
            return "Good - Minor packet loss detected"
        return "Good - Connection is stable"
    elif overall >= 70:
        if speed_score < 70:
            return "Fair - Speed below expected"
        elif stability_score < 70:
            return "Fair - Connection unstable"
        return "Fair - Some issues detected"
    elif overall >= 50:
        if has_loss:
            return "Poor - Significant packet loss"
        elif speed_score < 50:
            return "Poor - Speed well below expected"
        return "Poor - Multiple issues detected"
    else:
        return "Critical - Serious connection problems"
