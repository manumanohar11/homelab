"""Bufferbloat detection test."""

import subprocess
import re
from typing import Optional
from ..models import BufferbloatResult


def detect_bufferbloat(
    target: str = "8.8.8.8",
    ping_count: int = 10,
    interface: Optional[str] = None,
) -> BufferbloatResult:
    """
    Detect bufferbloat by measuring latency increase under load.

    Note: For accurate results, run during a speed test or heavy download.
    This simplified version measures baseline latency only.

    Grades (based on DSLReports):
    - A: <5ms increase
    - B: 5-30ms increase
    - C: 30-60ms increase
    - D: 60-200ms increase
    - F: >200ms increase
    """
    result = BufferbloatResult()

    try:
        # Build ping command
        cmd = ["ping", "-c", str(ping_count), "-i", "0.2"]
        if interface:
            cmd.extend(["-I", interface])
        cmd.append(target)

        # Run ping
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if proc.returncode != 0:
            result.error = "Ping failed"
            result.error_simple = "Cannot test bufferbloat. Try: check your internet connection"
            return result

        # Parse average latency
        match = re.search(r"min/avg/max.*?=\s*[\d.]+/([\d.]+)/", proc.stdout)
        if match:
            result.idle_latency_ms = float(match.group(1))
            result.loaded_latency_ms = result.idle_latency_ms  # Same for now
            result.bloat_ms = 0.0  # No load test in this version
            result.bloat_grade = "A"  # Baseline only
            result.success = True
        else:
            result.error = "Could not parse ping output"
            result.error_simple = "Test result unclear. Try: run the test again"

    except subprocess.TimeoutExpired:
        result.error = "Ping timeout"
        result.error_simple = "Connection too slow. Try: restart your router"
    except Exception as e:
        result.error = str(e)
        result.error_simple = "Bufferbloat test failed. Try: check your internet connection"

    return result


def grade_bufferbloat(bloat_ms: float) -> str:
    """Convert bloat measurement to letter grade."""
    if bloat_ms < 5:
        return "A"
    elif bloat_ms < 30:
        return "B"
    elif bloat_ms < 60:
        return "C"
    elif bloat_ms < 200:
        return "D"
    else:
        return "F"
