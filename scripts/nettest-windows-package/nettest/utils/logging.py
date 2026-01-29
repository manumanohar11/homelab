"""
Structured JSON logging for Promtail/Loki integration.
"""

import json
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import (
        PingResult, SpeedTestResult, DnsResult,
        MtrResult, DiagnosticResult
    )


class JsonLogger:
    """
    Structured JSON logger for Promtail/Loki integration.

    Writes newline-delimited JSON entries that can be ingested
    by log aggregation systems.
    """

    def __init__(self, log_file: Optional[str] = None, enabled: bool = False):
        """
        Initialize the JSON logger.

        Args:
            log_file: Path to log file
            enabled: Whether logging is enabled
        """
        self.log_file = log_file
        self.enabled = enabled and log_file is not None
        self._file_handle = None

    def _write(self, entry: dict) -> None:
        """Write a log entry to the log file."""
        if not self.enabled:
            return

        entry["timestamp"] = datetime.now().isoformat()

        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + "\n")
        except IOError:
            pass  # Silently fail if we can't write to log

    def log_start(self, targets: List[str], profile: Optional[str] = None) -> None:
        """Log test session start."""
        self._write({
            "level": "info",
            "event": "session_start",
            "targets": targets,
            "profile": profile,
        })

    def log_ping_result(self, result: "PingResult") -> None:
        """Log a ping test result."""
        self._write({
            "level": "info" if result.success else "warning",
            "event": "ping_result",
            "target": result.target,
            "target_name": result.target_name,
            "success": result.success,
            "avg_ms": result.avg_ms,
            "min_ms": result.min_ms,
            "max_ms": result.max_ms,
            "jitter_ms": result.jitter_ms,
            "packet_loss": result.packet_loss,
            "error": result.error or None,
        })

    def log_speedtest_result(self, result: "SpeedTestResult") -> None:
        """Log a speed test result."""
        self._write({
            "level": "info" if result.success else "warning",
            "event": "speedtest_result",
            "success": result.success,
            "download_mbps": result.download_mbps,
            "upload_mbps": result.upload_mbps,
            "ping_ms": result.ping_ms,
            "server": result.server,
            "error": result.error or None,
        })

    def log_dns_result(self, result: "DnsResult") -> None:
        """Log a DNS test result."""
        self._write({
            "level": "info" if result.success else "warning",
            "event": "dns_result",
            "target": result.target,
            "success": result.success,
            "resolution_time_ms": result.resolution_time_ms,
            "resolved_ip": result.resolved_ip,
            "error": result.error or None,
        })

    def log_mtr_result(self, result: "MtrResult") -> None:
        """Log an MTR result."""
        self._write({
            "level": "info" if result.success else "warning",
            "event": "mtr_result",
            "target": result.target,
            "target_name": result.target_name,
            "success": result.success,
            "hop_count": len(result.hops),
            "error": result.error or None,
        })

    def log_diagnostic(self, diagnostic: "DiagnosticResult") -> None:
        """Log diagnostic analysis."""
        self._write({
            "level": "warning" if diagnostic.category != "none" else "info",
            "event": "diagnostic",
            "category": diagnostic.category,
            "confidence": diagnostic.confidence,
            "summary": diagnostic.summary,
            "details": diagnostic.details,
        })

    def log_end(self, success: bool = True) -> None:
        """Log test session end."""
        self._write({
            "level": "info",
            "event": "session_end",
            "success": success,
        })
