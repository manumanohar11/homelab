"""
Unit tests for nettest data models.

Tests dataclass instantiation, default values, JSON serialization roundtrip,
and proper handling of Dict and List fields.
"""

import pytest
from dataclasses import asdict

from nettest.models import (
    PingResult,
    SpeedTestResult,
    ConnectionScore,
    VideoServiceResult,
    DnsResult,
    MtrHop,
    MtrResult,
    DiagnosticResult,
    BufferbloatResult,
    VoIPQuality,
    ISPEvidence,
    PortResult,
    HttpResult,
)


class TestPingResult:
    """Tests for PingResult dataclass."""

    def test_instantiation_with_required_fields(self):
        """Test that PingResult can be created with only required fields."""
        result = PingResult(target="8.8.8.8", target_name="Google DNS")
        assert result.target == "8.8.8.8"
        assert result.target_name == "Google DNS"

    def test_default_values(self):
        """Test that optional fields have correct default values."""
        result = PingResult(target="8.8.8.8", target_name="Google DNS")
        assert result.min_ms == 0.0
        assert result.avg_ms == 0.0
        assert result.max_ms == 0.0
        assert result.jitter_ms == 0.0
        assert result.packet_loss == 0.0
        assert result.success is False
        assert result.error == ""
        assert result.samples == []

    def test_instantiation_with_all_fields(self):
        """Test creating PingResult with all fields specified."""
        samples = [10.5, 11.2, 9.8, 10.1]
        result = PingResult(
            target="8.8.8.8",
            target_name="Google DNS",
            min_ms=9.8,
            avg_ms=10.4,
            max_ms=11.2,
            jitter_ms=0.5,
            packet_loss=0.0,
            success=True,
            error="",
            samples=samples,
        )
        assert result.min_ms == 9.8
        assert result.avg_ms == 10.4
        assert result.max_ms == 11.2
        assert result.jitter_ms == 0.5
        assert result.success is True
        assert result.samples == samples

    def test_json_serialization_roundtrip(self):
        """Test that PingResult can be serialized to dict and recreated."""
        original = PingResult(
            target="1.1.1.1",
            target_name="Cloudflare",
            min_ms=5.0,
            avg_ms=7.5,
            max_ms=10.0,
            jitter_ms=2.0,
            packet_loss=1.5,
            success=True,
            error="",
            samples=[5.0, 7.5, 10.0],
        )
        data = asdict(original)
        recreated = PingResult(**data)

        assert recreated.target == original.target
        assert recreated.target_name == original.target_name
        assert recreated.min_ms == original.min_ms
        assert recreated.avg_ms == original.avg_ms
        assert recreated.max_ms == original.max_ms
        assert recreated.jitter_ms == original.jitter_ms
        assert recreated.packet_loss == original.packet_loss
        assert recreated.success == original.success
        assert recreated.error == original.error
        assert recreated.samples == original.samples

    def test_samples_list_is_independent(self):
        """Test that default samples list is independent between instances."""
        result1 = PingResult(target="8.8.8.8", target_name="Google DNS")
        result2 = PingResult(target="1.1.1.1", target_name="Cloudflare")

        result1.samples.append(10.0)
        assert result2.samples == []

    def test_samples_list_field_type(self):
        """Test that samples field accepts and stores list correctly."""
        samples = [1.1, 2.2, 3.3, 4.4, 5.5]
        result = PingResult(target="test", target_name="Test", samples=samples)
        assert isinstance(result.samples, list)
        assert len(result.samples) == 5
        assert all(isinstance(s, float) for s in result.samples)


class TestSpeedTestResult:
    """Tests for SpeedTestResult dataclass."""

    def test_instantiation_with_defaults(self):
        """Test that SpeedTestResult can be created with default values."""
        result = SpeedTestResult()
        assert result.download_mbps == 0.0
        assert result.upload_mbps == 0.0
        assert result.ping_ms == 0.0
        assert result.server == ""
        assert result.success is False
        assert result.error == ""

    def test_instantiation_with_all_fields(self):
        """Test creating SpeedTestResult with all fields specified."""
        result = SpeedTestResult(
            download_mbps=100.5,
            upload_mbps=50.25,
            ping_ms=15.3,
            server="Speedtest Server NYC",
            success=True,
            error="",
        )
        assert result.download_mbps == 100.5
        assert result.upload_mbps == 50.25
        assert result.ping_ms == 15.3
        assert result.server == "Speedtest Server NYC"
        assert result.success is True

    def test_json_serialization_roundtrip(self):
        """Test that SpeedTestResult can be serialized to dict and recreated."""
        original = SpeedTestResult(
            download_mbps=250.0,
            upload_mbps=125.0,
            ping_ms=8.5,
            server="Test Server",
            success=True,
            error="",
        )
        data = asdict(original)
        recreated = SpeedTestResult(**data)

        assert recreated.download_mbps == original.download_mbps
        assert recreated.upload_mbps == original.upload_mbps
        assert recreated.ping_ms == original.ping_ms
        assert recreated.server == original.server
        assert recreated.success == original.success
        assert recreated.error == original.error

    def test_error_state(self):
        """Test SpeedTestResult in error state."""
        result = SpeedTestResult(
            success=False,
            error="Connection timed out",
        )
        assert result.success is False
        assert result.error == "Connection timed out"
        assert result.download_mbps == 0.0


class TestConnectionScore:
    """Tests for ConnectionScore dataclass."""

    def test_instantiation_with_required_fields(self):
        """Test that ConnectionScore can be created with required fields."""
        score = ConnectionScore(
            overall=85,
            grade="B+",
            speed_score=90,
            latency_score=80,
            stability_score=85,
            summary="Good connection",
        )
        assert score.overall == 85
        assert score.grade == "B+"
        assert score.speed_score == 90
        assert score.latency_score == 80
        assert score.stability_score == 85
        assert score.summary == "Good connection"

    def test_json_serialization_roundtrip(self):
        """Test that ConnectionScore can be serialized to dict and recreated."""
        original = ConnectionScore(
            overall=95,
            grade="A",
            speed_score=98,
            latency_score=92,
            stability_score=95,
            summary="Excellent - No issues detected",
        )
        data = asdict(original)
        recreated = ConnectionScore(**data)

        assert recreated.overall == original.overall
        assert recreated.grade == original.grade
        assert recreated.speed_score == original.speed_score
        assert recreated.latency_score == original.latency_score
        assert recreated.stability_score == original.stability_score
        assert recreated.summary == original.summary

    def test_various_grades(self):
        """Test ConnectionScore with various grade values."""
        grades = ["A+", "A", "B+", "B", "C", "D", "F"]
        for grade in grades:
            score = ConnectionScore(
                overall=50,
                grade=grade,
                speed_score=50,
                latency_score=50,
                stability_score=50,
                summary=f"Grade {grade}",
            )
            assert score.grade == grade

    def test_boundary_scores(self):
        """Test ConnectionScore with boundary score values."""
        # Minimum scores
        min_score = ConnectionScore(
            overall=0,
            grade="F",
            speed_score=0,
            latency_score=0,
            stability_score=0,
            summary="Critical - Connection unavailable",
        )
        assert min_score.overall == 0
        assert min_score.speed_score == 0

        # Maximum scores
        max_score = ConnectionScore(
            overall=100,
            grade="A+",
            speed_score=100,
            latency_score=100,
            stability_score=100,
            summary="Perfect connection",
        )
        assert max_score.overall == 100
        assert max_score.speed_score == 100


class TestVideoServiceResult:
    """Tests for VideoServiceResult dataclass."""

    def test_instantiation_with_required_fields(self):
        """Test that VideoServiceResult can be created with required fields."""
        result = VideoServiceResult(name="Zoom", domain="zoom.us")
        assert result.name == "Zoom"
        assert result.domain == "zoom.us"

    def test_default_values(self):
        """Test that optional fields have correct default values."""
        result = VideoServiceResult(name="Zoom", domain="zoom.us")
        assert result.dns_ok is False
        assert result.dns_latency_ms == 0.0
        assert result.tcp_ports == {}
        assert result.tcp_latencies == {}
        assert result.stun_ok is False
        assert result.stun_latency_ms == 0.0
        assert result.status == "blocked"
        assert result.issues == []

    def test_instantiation_with_all_fields(self):
        """Test creating VideoServiceResult with all fields specified."""
        tcp_ports = {443: True, 8801: True, 8802: False}
        tcp_latencies = {443: 15.2, 8801: 18.5, 8802: 0.0}
        issues = ["Port 8802 blocked", "High latency on 8801"]

        result = VideoServiceResult(
            name="Zoom",
            domain="zoom.us",
            dns_ok=True,
            dns_latency_ms=5.5,
            tcp_ports=tcp_ports,
            tcp_latencies=tcp_latencies,
            stun_ok=True,
            stun_latency_ms=20.3,
            status="degraded",
            issues=issues,
        )

        assert result.name == "Zoom"
        assert result.domain == "zoom.us"
        assert result.dns_ok is True
        assert result.dns_latency_ms == 5.5
        assert result.tcp_ports == tcp_ports
        assert result.tcp_latencies == tcp_latencies
        assert result.stun_ok is True
        assert result.stun_latency_ms == 20.3
        assert result.status == "degraded"
        assert result.issues == issues

    def test_json_serialization_roundtrip(self):
        """Test that VideoServiceResult can be serialized to dict and recreated."""
        original = VideoServiceResult(
            name="Teams",
            domain="teams.microsoft.com",
            dns_ok=True,
            dns_latency_ms=8.0,
            tcp_ports={443: True, 3478: True},
            tcp_latencies={443: 12.0, 3478: 15.0},
            stun_ok=True,
            stun_latency_ms=25.0,
            status="ready",
            issues=[],
        )
        data = asdict(original)
        recreated = VideoServiceResult(**data)

        assert recreated.name == original.name
        assert recreated.domain == original.domain
        assert recreated.dns_ok == original.dns_ok
        assert recreated.dns_latency_ms == original.dns_latency_ms
        assert recreated.tcp_ports == original.tcp_ports
        assert recreated.tcp_latencies == original.tcp_latencies
        assert recreated.stun_ok == original.stun_ok
        assert recreated.stun_latency_ms == original.stun_latency_ms
        assert recreated.status == original.status
        assert recreated.issues == original.issues

    def test_tcp_ports_dict_is_independent(self):
        """Test that default tcp_ports dict is independent between instances."""
        result1 = VideoServiceResult(name="Zoom", domain="zoom.us")
        result2 = VideoServiceResult(name="Teams", domain="teams.microsoft.com")

        result1.tcp_ports[443] = True
        assert result2.tcp_ports == {}

    def test_tcp_latencies_dict_is_independent(self):
        """Test that default tcp_latencies dict is independent between instances."""
        result1 = VideoServiceResult(name="Zoom", domain="zoom.us")
        result2 = VideoServiceResult(name="Teams", domain="teams.microsoft.com")

        result1.tcp_latencies[443] = 15.0
        assert result2.tcp_latencies == {}

    def test_issues_list_is_independent(self):
        """Test that default issues list is independent between instances."""
        result1 = VideoServiceResult(name="Zoom", domain="zoom.us")
        result2 = VideoServiceResult(name="Teams", domain="teams.microsoft.com")

        result1.issues.append("Port blocked")
        assert result2.issues == []

    def test_dict_field_types(self):
        """Test that Dict fields accept and store dictionaries correctly."""
        tcp_ports = {443: True, 8801: False, 3478: True}
        tcp_latencies = {443: 10.5, 8801: 0.0, 3478: 22.3}

        result = VideoServiceResult(
            name="Test",
            domain="test.com",
            tcp_ports=tcp_ports,
            tcp_latencies=tcp_latencies,
        )

        assert isinstance(result.tcp_ports, dict)
        assert len(result.tcp_ports) == 3
        assert all(isinstance(k, int) for k in result.tcp_ports.keys())
        assert all(isinstance(v, bool) for v in result.tcp_ports.values())

        assert isinstance(result.tcp_latencies, dict)
        assert len(result.tcp_latencies) == 3
        assert all(isinstance(k, int) for k in result.tcp_latencies.keys())
        assert all(isinstance(v, float) for v in result.tcp_latencies.values())

    def test_status_values(self):
        """Test VideoServiceResult with various status values."""
        statuses = ["ready", "degraded", "blocked"]
        for status in statuses:
            result = VideoServiceResult(
                name="Test",
                domain="test.com",
                status=status,
            )
            assert result.status == status


class TestDnsResult:
    """Tests for DnsResult dataclass."""

    def test_instantiation_with_required_fields(self):
        """Test that DnsResult can be created with required field."""
        result = DnsResult(target="google.com")
        assert result.target == "google.com"

    def test_default_values(self):
        """Test that optional fields have correct default values."""
        result = DnsResult(target="google.com")
        assert result.resolution_time_ms == 0.0
        assert result.resolved_ip == ""
        assert result.success is False
        assert result.error == ""

    def test_json_serialization_roundtrip(self):
        """Test that DnsResult can be serialized to dict and recreated."""
        original = DnsResult(
            target="example.com",
            resolution_time_ms=12.5,
            resolved_ip="93.184.216.34",
            success=True,
            error="",
        )
        data = asdict(original)
        recreated = DnsResult(**data)

        assert recreated.target == original.target
        assert recreated.resolution_time_ms == original.resolution_time_ms
        assert recreated.resolved_ip == original.resolved_ip
        assert recreated.success == original.success


class TestMtrHopAndMtrResult:
    """Tests for MtrHop and MtrResult dataclasses."""

    def test_mtr_hop_instantiation(self):
        """Test that MtrHop can be created with all required fields."""
        hop = MtrHop(
            hop_number=1,
            host="192.168.1.1",
            loss_pct=0.0,
            sent=10,
            avg_ms=1.5,
            best_ms=1.0,
            worst_ms=2.5,
        )
        assert hop.hop_number == 1
        assert hop.host == "192.168.1.1"
        assert hop.loss_pct == 0.0
        assert hop.sent == 10
        assert hop.avg_ms == 1.5

    def test_mtr_result_instantiation(self):
        """Test that MtrResult can be created with required fields."""
        result = MtrResult(target="8.8.8.8", target_name="Google DNS")
        assert result.target == "8.8.8.8"
        assert result.target_name == "Google DNS"
        assert result.hops == []
        assert result.success is False

    def test_mtr_result_with_hops(self):
        """Test MtrResult with hop data."""
        hops = [
            MtrHop(1, "192.168.1.1", 0.0, 10, 1.5, 1.0, 2.5),
            MtrHop(2, "10.0.0.1", 0.0, 10, 5.0, 4.0, 6.0),
            MtrHop(3, "8.8.8.8", 0.0, 10, 10.0, 8.0, 12.0),
        ]
        result = MtrResult(
            target="8.8.8.8",
            target_name="Google DNS",
            hops=hops,
            success=True,
        )
        assert len(result.hops) == 3
        assert result.hops[0].hop_number == 1
        assert result.hops[2].host == "8.8.8.8"

    def test_mtr_result_json_serialization_roundtrip(self):
        """Test that MtrResult can be serialized to dict and recreated."""
        original = MtrResult(
            target="1.1.1.1",
            target_name="Cloudflare",
            hops=[
                MtrHop(1, "router.local", 0.0, 10, 2.0, 1.0, 3.0),
            ],
            success=True,
            error="",
        )
        data = asdict(original)
        # Recreate hops from dict
        hops_data = data.pop("hops")
        recreated_hops = [MtrHop(**h) for h in hops_data]
        recreated = MtrResult(**data, hops=recreated_hops)

        assert recreated.target == original.target
        assert len(recreated.hops) == len(original.hops)
        assert recreated.hops[0].host == original.hops[0].host


class TestDiagnosticResult:
    """Tests for DiagnosticResult dataclass."""

    def test_instantiation_with_required_fields(self):
        """Test that DiagnosticResult can be created with required fields."""
        result = DiagnosticResult(
            category="isp",
            confidence="high",
            summary="ISP routing issues detected",
        )
        assert result.category == "isp"
        assert result.confidence == "high"
        assert result.summary == "ISP routing issues detected"

    def test_default_list_values(self):
        """Test that list fields have correct default values."""
        result = DiagnosticResult(
            category="none",
            confidence="low",
            summary="No issues detected",
        )
        assert result.details == []
        assert result.recommendations == []

    def test_lists_are_independent(self):
        """Test that default lists are independent between instances."""
        result1 = DiagnosticResult(
            category="local", confidence="medium", summary="Local issue"
        )
        result2 = DiagnosticResult(
            category="isp", confidence="high", summary="ISP issue"
        )

        result1.details.append("Detail 1")
        result1.recommendations.append("Recommendation 1")

        assert result2.details == []
        assert result2.recommendations == []


class TestBufferbloatResult:
    """Tests for BufferbloatResult dataclass."""

    def test_instantiation_with_defaults(self):
        """Test that BufferbloatResult can be created with default values."""
        result = BufferbloatResult()
        assert result.idle_latency_ms == 0.0
        assert result.loaded_latency_ms == 0.0
        assert result.bloat_ms == 0.0
        assert result.bloat_grade == ""
        assert result.success is False
        assert result.error == ""

    def test_instantiation_with_all_fields(self):
        """Test creating BufferbloatResult with all fields specified."""
        result = BufferbloatResult(
            idle_latency_ms=15.0,
            loaded_latency_ms=250.0,
            bloat_ms=235.0,
            bloat_grade="F",
            success=True,
            error="",
        )
        assert result.idle_latency_ms == 15.0
        assert result.loaded_latency_ms == 250.0
        assert result.bloat_ms == 235.0
        assert result.bloat_grade == "F"

    def test_json_serialization_roundtrip(self):
        """Test that BufferbloatResult can be serialized to dict and recreated."""
        original = BufferbloatResult(
            idle_latency_ms=10.0,
            loaded_latency_ms=25.0,
            bloat_ms=15.0,
            bloat_grade="A",
            success=True,
        )
        data = asdict(original)
        recreated = BufferbloatResult(**data)

        assert recreated.idle_latency_ms == original.idle_latency_ms
        assert recreated.loaded_latency_ms == original.loaded_latency_ms
        assert recreated.bloat_grade == original.bloat_grade


class TestVoIPQuality:
    """Tests for VoIPQuality dataclass."""

    def test_instantiation_with_defaults(self):
        """Test that VoIPQuality can be created with default values."""
        result = VoIPQuality()
        assert result.mos_score == 0.0
        assert result.r_factor == 0.0
        assert result.quality == ""
        assert result.suitable_for == []

    def test_instantiation_with_all_fields(self):
        """Test creating VoIPQuality with all fields specified."""
        result = VoIPQuality(
            mos_score=4.2,
            r_factor=85.0,
            quality="Good",
            suitable_for=["HD Voice", "Video", "Screen Share"],
        )
        assert result.mos_score == 4.2
        assert result.r_factor == 85.0
        assert result.quality == "Good"
        assert result.suitable_for == ["HD Voice", "Video", "Screen Share"]

    def test_suitable_for_list_is_independent(self):
        """Test that default suitable_for list is independent between instances."""
        result1 = VoIPQuality()
        result2 = VoIPQuality()

        result1.suitable_for.append("Voice")
        assert result2.suitable_for == []


class TestISPEvidence:
    """Tests for ISPEvidence dataclass."""

    def test_instantiation_with_defaults(self):
        """Test that ISPEvidence can be created with default values."""
        result = ISPEvidence()
        assert result.timestamp == ""
        assert result.summary == ""
        assert result.speed_complaint == ""
        assert result.packet_loss_complaint == ""
        assert result.latency_complaint == ""
        assert result.problem_hops == []
        assert result.recommendations == []

    def test_lists_are_independent(self):
        """Test that default lists are independent between instances."""
        result1 = ISPEvidence()
        result2 = ISPEvidence()

        result1.problem_hops.append("Hop 5: 10.0.0.1 - 50% loss")
        result1.recommendations.append("Contact ISP")

        assert result2.problem_hops == []
        assert result2.recommendations == []


class TestPortResult:
    """Tests for PortResult dataclass."""

    def test_instantiation_with_required_fields(self):
        """Test that PortResult can be created with required fields."""
        result = PortResult(host="example.com", port=443)
        assert result.host == "example.com"
        assert result.port == 443

    def test_default_values(self):
        """Test that optional fields have correct default values."""
        result = PortResult(host="example.com", port=22)
        assert result.open is False
        assert result.response_time_ms == 0.0
        assert result.error == ""

    def test_json_serialization_roundtrip(self):
        """Test that PortResult can be serialized to dict and recreated."""
        original = PortResult(
            host="google.com",
            port=443,
            open=True,
            response_time_ms=25.5,
            error="",
        )
        data = asdict(original)
        recreated = PortResult(**data)

        assert recreated.host == original.host
        assert recreated.port == original.port
        assert recreated.open == original.open
        assert recreated.response_time_ms == original.response_time_ms


class TestHttpResult:
    """Tests for HttpResult dataclass."""

    def test_instantiation_with_required_fields(self):
        """Test that HttpResult can be created with required field."""
        result = HttpResult(url="https://example.com")
        assert result.url == "https://example.com"

    def test_default_values(self):
        """Test that optional fields have correct default values."""
        result = HttpResult(url="https://example.com")
        assert result.status_code == 0
        assert result.response_time_ms == 0.0
        assert result.success is False
        assert result.error == ""

    def test_json_serialization_roundtrip(self):
        """Test that HttpResult can be serialized to dict and recreated."""
        original = HttpResult(
            url="https://api.example.com/health",
            status_code=200,
            response_time_ms=150.5,
            success=True,
            error="",
        )
        data = asdict(original)
        recreated = HttpResult(**data)

        assert recreated.url == original.url
        assert recreated.status_code == original.status_code
        assert recreated.response_time_ms == original.response_time_ms
        assert recreated.success == original.success
