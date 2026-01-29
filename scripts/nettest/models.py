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
