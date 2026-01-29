"""
Network Testing Tool Package

A comprehensive network testing and diagnostics tool with TUI,
monitoring capabilities, and multiple output formats.
"""

__version__ = "2.0.0"
__author__ = "Network Testing Tool Contributors"

from .models import (
    PingResult,
    SpeedTestResult,
    DnsResult,
    MtrHop,
    MtrResult,
    DiagnosticResult,
    ConnectionScore,
    BufferbloatResult,
    VoIPQuality,
    ISPEvidence,
    PortResult,
    HttpResult,
)

__all__ = [
    "PingResult",
    "SpeedTestResult",
    "DnsResult",
    "MtrHop",
    "MtrResult",
    "DiagnosticResult",
    "ConnectionScore",
    "BufferbloatResult",
    "VoIPQuality",
    "ISPEvidence",
    "PortResult",
    "HttpResult",
    "__version__",
]
