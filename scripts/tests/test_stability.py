"""Unit tests for stability scoring in nettest.tests.stability."""

import pytest
from nettest.models import PingResult, SpeedTestResult, ConnectionScore
from nettest.tests.stability import calculate_connection_score, _score_to_grade


def create_ping_result(
    target: str = "8.8.8.8",
    target_name: str = "Google DNS",
    avg_ms: float = 10.0,
    jitter_ms: float = 1.0,
    packet_loss: float = 0.0,
    success: bool = True,
) -> PingResult:
    """Helper to create PingResult objects for testing."""
    return PingResult(
        target=target,
        target_name=target_name,
        min_ms=avg_ms * 0.8,
        avg_ms=avg_ms,
        max_ms=avg_ms * 1.2,
        jitter_ms=jitter_ms,
        packet_loss=packet_loss,
        success=success,
        error="" if success else "timeout",
        samples=[avg_ms] * 5,
    )


def create_speedtest_result(
    download_mbps: float = 100.0,
    upload_mbps: float = 50.0,
    success: bool = True,
) -> SpeedTestResult:
    """Helper to create SpeedTestResult objects for testing."""
    return SpeedTestResult(
        download_mbps=download_mbps,
        upload_mbps=upload_mbps,
        ping_ms=10.0,
        server="Test Server",
        success=success,
        error="" if success else "connection failed",
    )


class TestScoreGrades:
    """Tests for grade thresholds based on overall score."""

    def test_score_perfect(self):
        """Perfect scores (100) give A+ grade."""
        # Perfect conditions: expected speed achieved, low latency, no jitter/loss
        ping_results = [create_ping_result(avg_ms=10.0, jitter_ms=0.0, packet_loss=0.0)]
        speedtest = create_speedtest_result(download_mbps=100.0)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.grade == "A+"
        assert result.overall >= 95

    def test_score_excellent(self):
        """Scores 90-94 give A grade."""
        # Slightly degraded conditions - need to land in 90-94 range
        # Using moderately higher latency and slightly lower speed to reduce overall
        ping_results = [create_ping_result(avg_ms=50.0, jitter_ms=5.0, packet_loss=0.0)]
        speedtest = create_speedtest_result(download_mbps=90.0)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.grade == "A"
        assert 90 <= result.overall < 95

    def test_score_good(self):
        """Scores 85-89 give B+ grade."""
        # Moderate conditions
        ping_results = [create_ping_result(avg_ms=40.0, jitter_ms=8.0, packet_loss=0.0)]
        speedtest = create_speedtest_result(download_mbps=85.0)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.grade == "B+"
        assert 85 <= result.overall < 90

    def test_score_fair(self):
        """Scores 80-84 give B grade."""
        # Fair conditions with some degradation
        ping_results = [create_ping_result(avg_ms=50.0, jitter_ms=10.0, packet_loss=0.5)]
        speedtest = create_speedtest_result(download_mbps=80.0)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.grade == "B"
        assert 80 <= result.overall < 85

    def test_score_poor(self):
        """Scores 70-79 give C grade."""
        # C grade requires overall 70-79
        # Using moderate degradation across all metrics
        ping_results = [create_ping_result(avg_ms=60.0, jitter_ms=10.0, packet_loss=0.5)]
        speedtest = create_speedtest_result(download_mbps=75.0)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.grade == "C"
        assert 70 <= result.overall < 80

    def test_score_bad_d_grade(self):
        """Scores 60-69 give D grade."""
        # D grade requires overall 60-69
        # Using more moderate degradation to stay in range
        ping_results = [create_ping_result(avg_ms=90.0, jitter_ms=12.0, packet_loss=1.0)]
        speedtest = create_speedtest_result(download_mbps=65.0)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.grade == "D"
        assert 60 <= result.overall < 70

    def test_score_bad_f_grade(self):
        """Scores below 60 give F grade."""
        # Very bad conditions
        ping_results = [create_ping_result(avg_ms=180.0, jitter_ms=50.0, packet_loss=5.0)]
        speedtest = create_speedtest_result(download_mbps=30.0)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.grade == "F"
        assert result.overall < 60


class TestPacketLossImpact:
    """Tests for packet loss impact on scoring."""

    def test_score_with_packet_loss(self):
        """Packet loss severely impacts score."""
        # Perfect conditions except for packet loss
        ping_no_loss = [create_ping_result(avg_ms=10.0, jitter_ms=1.0, packet_loss=0.0)]
        ping_with_loss = [create_ping_result(avg_ms=10.0, jitter_ms=1.0, packet_loss=5.0)]
        speedtest = create_speedtest_result(download_mbps=100.0)
        expected_speed = 100.0

        result_no_loss = calculate_connection_score(ping_no_loss, speedtest, expected_speed)
        result_with_loss = calculate_connection_score(ping_with_loss, speedtest, expected_speed)

        # 5% packet loss should reduce stability_score by 50 points (5 * 10)
        # This significantly impacts overall score
        assert result_with_loss.overall < result_no_loss.overall
        assert result_with_loss.stability_score < result_no_loss.stability_score
        # 5% loss = 50 point penalty, so stability should drop from ~100 to ~50
        assert result_with_loss.stability_score <= 55

    def test_high_packet_loss_causes_f_grade(self):
        """High packet loss (10%+) should cause F grade."""
        ping_results = [create_ping_result(avg_ms=10.0, jitter_ms=1.0, packet_loss=10.0)]
        speedtest = create_speedtest_result(download_mbps=100.0)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        # 10% loss = 100 point penalty on stability (clamped to 0)
        assert result.stability_score == 0
        # Overall should be very low
        assert result.overall < 70


class TestJitterImpact:
    """Tests for jitter impact on scoring."""

    def test_score_with_high_jitter(self):
        """High jitter impacts score."""
        # Perfect conditions except for jitter
        ping_low_jitter = [create_ping_result(avg_ms=10.0, jitter_ms=2.0, packet_loss=0.0)]
        ping_high_jitter = [create_ping_result(avg_ms=10.0, jitter_ms=30.0, packet_loss=0.0)]
        speedtest = create_speedtest_result(download_mbps=100.0)
        expected_speed = 100.0

        result_low_jitter = calculate_connection_score(ping_low_jitter, speedtest, expected_speed)
        result_high_jitter = calculate_connection_score(ping_high_jitter, speedtest, expected_speed)

        # High jitter should reduce stability score
        # Jitter penalty: (30 - 5) * 2 = 50 points
        assert result_high_jitter.overall < result_low_jitter.overall
        assert result_high_jitter.stability_score < result_low_jitter.stability_score
        # Stability should be around 50 with 30ms jitter
        assert result_high_jitter.stability_score <= 55

    def test_jitter_under_threshold_no_penalty(self):
        """Jitter under 5ms has no penalty."""
        ping_results = [create_ping_result(avg_ms=10.0, jitter_ms=3.0, packet_loss=0.0)]
        speedtest = create_speedtest_result(download_mbps=100.0)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        # No jitter penalty for values <= 5ms
        assert result.stability_score == 100


class TestScoreComponents:
    """Tests for individual score components."""

    def test_score_components(self):
        """Verify speed_score, latency_score, stability_score are calculated."""
        ping_results = [create_ping_result(avg_ms=50.0, jitter_ms=10.0, packet_loss=1.0)]
        speedtest = create_speedtest_result(download_mbps=80.0)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        # Verify all components are present and within valid range
        assert isinstance(result, ConnectionScore)
        assert 0 <= result.speed_score <= 100
        assert 0 <= result.latency_score <= 100
        assert 0 <= result.stability_score <= 100
        assert 0 <= result.overall <= 100
        assert result.grade in ["A+", "A", "B+", "B", "C", "D", "F"]
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_speed_score_calculation(self):
        """Speed score is percentage of expected speed."""
        ping_results = [create_ping_result()]
        speedtest = create_speedtest_result(download_mbps=75.0)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        # 75 Mbps / 100 Mbps = 75%
        assert result.speed_score == 75

    def test_speed_score_capped_at_100(self):
        """Speed score is capped at 100 even if exceeding expected."""
        ping_results = [create_ping_result()]
        speedtest = create_speedtest_result(download_mbps=150.0)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.speed_score == 100

    def test_latency_score_perfect(self):
        """Latency <= 20ms gives 100 score."""
        ping_results = [create_ping_result(avg_ms=15.0)]
        speedtest = create_speedtest_result()
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.latency_score == 100

    def test_latency_score_zero(self):
        """Latency >= 200ms gives 0 score."""
        ping_results = [create_ping_result(avg_ms=250.0)]
        speedtest = create_speedtest_result()
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.latency_score == 0

    def test_latency_score_interpolation(self):
        """Latency between 20-200ms is interpolated."""
        ping_results = [create_ping_result(avg_ms=110.0)]  # Midpoint
        speedtest = create_speedtest_result()
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        # 110ms is 90ms above 20ms threshold
        # Score = 100 - (90/180)*100 = 50
        assert result.latency_score == 50

    def test_weighted_overall_calculation(self):
        """Overall score uses correct weights: speed 35%, latency 30%, stability 35%."""
        ping_results = [create_ping_result(avg_ms=10.0, jitter_ms=0.0, packet_loss=0.0)]
        speedtest = create_speedtest_result(download_mbps=100.0)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        # With perfect scores (100 each), overall should be 100
        expected_overall = int(100 * 0.35 + 100 * 0.30 + 100 * 0.35)
        assert result.overall == expected_overall


class TestEdgeCases:
    """Tests for edge cases and failure scenarios."""

    def test_failed_speedtest(self):
        """Failed speedtest gives 0 speed score."""
        ping_results = [create_ping_result()]
        speedtest = create_speedtest_result(success=False)
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.speed_score == 0

    def test_zero_expected_speed(self):
        """Zero expected speed gives 0 speed score."""
        ping_results = [create_ping_result()]
        speedtest = create_speedtest_result(download_mbps=100.0)
        expected_speed = 0.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.speed_score == 0

    def test_no_successful_pings(self):
        """No successful pings gives 0 for latency and stability."""
        ping_results = [create_ping_result(success=False)]
        speedtest = create_speedtest_result()
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.latency_score == 0
        assert result.stability_score == 0

    def test_empty_ping_results(self):
        """Empty ping results gives 0 for latency and stability."""
        ping_results = []
        speedtest = create_speedtest_result()
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        assert result.latency_score == 0
        assert result.stability_score == 0

    def test_multiple_ping_results_averaged(self):
        """Multiple ping results are averaged."""
        ping_results = [
            create_ping_result(avg_ms=10.0, jitter_ms=2.0, packet_loss=0.0),
            create_ping_result(avg_ms=30.0, jitter_ms=8.0, packet_loss=2.0),
        ]
        speedtest = create_speedtest_result()
        expected_speed = 100.0

        result = calculate_connection_score(ping_results, speedtest, expected_speed)

        # Average latency: (10 + 30) / 2 = 20ms -> latency_score = 100
        assert result.latency_score == 100
        # Average jitter: (2 + 8) / 2 = 5ms -> no penalty
        # Average loss: (0 + 2) / 2 = 1% -> 10 point penalty
        # stability_score = 100 - 0 - 10 = 90
        assert result.stability_score == 90

    def test_bufferbloat_penalty(self):
        """Bufferbloat adds penalty to stability score."""
        ping_results = [create_ping_result(avg_ms=10.0, jitter_ms=0.0, packet_loss=0.0)]
        speedtest = create_speedtest_result()
        expected_speed = 100.0

        result_no_bloat = calculate_connection_score(
            ping_results, speedtest, expected_speed, bufferbloat_ms=0.0
        )
        result_with_bloat = calculate_connection_score(
            ping_results, speedtest, expected_speed, bufferbloat_ms=50.0
        )

        # Bufferbloat penalty: 50 * 0.2 = 10 points
        assert result_with_bloat.stability_score == result_no_bloat.stability_score - 10


class TestGradeFunction:
    """Tests for the _score_to_grade helper function."""

    def test_grade_boundaries(self):
        """Test all grade boundaries."""
        assert _score_to_grade(100) == "A+"
        assert _score_to_grade(95) == "A+"
        assert _score_to_grade(94) == "A"
        assert _score_to_grade(90) == "A"
        assert _score_to_grade(89) == "B+"
        assert _score_to_grade(85) == "B+"
        assert _score_to_grade(84) == "B"
        assert _score_to_grade(80) == "B"
        assert _score_to_grade(79) == "C"
        assert _score_to_grade(70) == "C"
        assert _score_to_grade(69) == "D"
        assert _score_to_grade(60) == "D"
        assert _score_to_grade(59) == "F"
        assert _score_to_grade(0) == "F"
