"""
Data models for network test results.

All result types are immutable dataclasses that can be serialized to JSON.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class PingResult:
    """Result of a ping test to a single target."""
    target: str
    target_name: str
    min_ms: float = 0.0
    avg_ms: float = 0.0
    max_ms: float = 0.0
    jitter_ms: float = 0.0
    packet_loss: float = 0.0
    success: bool = False
    error: str = ""
    samples: List[float] = field(default_factory=list)


@dataclass
class SpeedTestResult:
    """Result of an internet speed test."""
    download_mbps: float = 0.0
    upload_mbps: float = 0.0
    ping_ms: float = 0.0
    server: str = ""
    success: bool = False
    error: str = ""


@dataclass
class DnsResult:
    """Result of a DNS resolution test."""
    target: str
    resolution_time_ms: float = 0.0
    resolved_ip: str = ""
    success: bool = False
    error: str = ""


@dataclass
class MtrHop:
    """Single hop in an MTR route trace."""
    hop_number: int
    host: str
    loss_pct: float
    sent: int
    avg_ms: float
    best_ms: float
    worst_ms: float


@dataclass
class MtrResult:
    """Result of an MTR route analysis."""
    target: str
    target_name: str
    hops: List[MtrHop] = field(default_factory=list)
    success: bool = False
    error: str = ""


@dataclass
class DiagnosticResult:
    """Diagnostic analysis of where network problems might be occurring."""
    category: str  # "local", "isp", "internet", "target", "none"
    confidence: str  # "high", "medium", "low"
    summary: str
    details: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ConnectionScore:
    """Overall connection health score."""
    overall: int              # 0-100
    grade: str                # A+, A, B+, B, C, D, F
    speed_score: int          # 0-100
    latency_score: int        # 0-100
    stability_score: int      # 0-100
    summary: str              # "Fair - ISP issues detected"


@dataclass
class BufferbloatResult:
    """Result of bufferbloat detection test."""
    idle_latency_ms: float = 0.0
    loaded_latency_ms: float = 0.0
    bloat_ms: float = 0.0
    bloat_grade: str = ""  # A, B, C, D, F
    success: bool = False
    error: str = ""


@dataclass
class VoIPQuality:
    """VoIP call quality assessment."""
    mos_score: float = 0.0      # 1.0-5.0 Mean Opinion Score
    r_factor: float = 0.0       # 0-100 E-model R-factor
    quality: str = ""           # "Excellent", "Good", "Fair", "Poor", "Bad"
    suitable_for: List[str] = field(default_factory=list)  # ["HD Voice", "Video"]


@dataclass
class ISPEvidence:
    """Documentation-ready evidence for ISP complaints."""
    timestamp: str = ""
    summary: str = ""
    speed_complaint: str = ""  # "Download 53 Mbps vs 100 Mbps expected (47% deficit)"
    packet_loss_complaint: str = ""  # "10% packet loss to Cloudflare DNS"
    latency_complaint: str = ""  # "Average latency 115ms (expected <50ms)"
    problem_hops: List[str] = field(default_factory=list)  # ["Hop 5: 103.77.108.118 - 90% loss"]
    recommendations: List[str] = field(default_factory=list)


@dataclass
class PortResult:
    """Result of a TCP port connectivity test."""
    host: str
    port: int
    open: bool = False
    response_time_ms: float = 0.0
    error: str = ""


@dataclass
class HttpResult:
    """Result of an HTTP/HTTPS latency test."""
    url: str
    status_code: int = 0
    response_time_ms: float = 0.0
    success: bool = False
    error: str = ""
