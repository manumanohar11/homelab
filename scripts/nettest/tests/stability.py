"""Connection stability and health scoring."""

from typing import List
from ..models import PingResult, SpeedTestResult, ConnectionScore


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
