"""JSON output formatter for machine-readable results."""

import json
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional

from ..models import (
    PingResult, SpeedTestResult, DnsResult,
    MtrResult, DiagnosticResult, PortResult, HttpResult, VideoServiceResult
)


def output_json(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    dns_results: List[DnsResult],
    mtr_results: List[MtrResult],
    diagnostic: DiagnosticResult,
    port_results: Optional[List[PortResult]] = None,
    http_results: Optional[List[HttpResult]] = None,
    video_service_results: Optional[List[VideoServiceResult]] = None,
) -> None:
    """
    Output all results as JSON to stdout.

    Args:
        ping_results: Ping test results
        speedtest_result: Speed test result
        dns_results: DNS test results
        mtr_results: MTR results
        diagnostic: Diagnostic analysis result
        port_results: TCP port test results (optional)
        http_results: HTTP latency test results (optional)
    """
    output = {
        "timestamp": datetime.now().isoformat(),
        "ping_results": [asdict(r) for r in ping_results],
        "speedtest": asdict(speedtest_result),
        "dns_results": [asdict(r) for r in dns_results],
        "mtr_results": [
            {
                "target": r.target,
                "target_name": r.target_name,
                "success": r.success,
                "error": r.error,
                "hops": [asdict(h) for h in r.hops],
            }
            for r in mtr_results
        ],
        "diagnostic": asdict(diagnostic),
    }

    # Add optional results if present
    if port_results:
        output["port_results"] = [asdict(r) for r in port_results]
    if http_results:
        output["http_results"] = [asdict(r) for r in http_results]
    if video_service_results:
        output["video_services"] = [asdict(r) for r in video_service_results]

    print(json.dumps(output, indent=2))


def results_to_dict(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    dns_results: List[DnsResult],
    mtr_results: List[MtrResult],
    diagnostic: DiagnosticResult,
    port_results: Optional[List[PortResult]] = None,
    http_results: Optional[List[HttpResult]] = None,
    video_service_results: Optional[List[VideoServiceResult]] = None,
) -> dict:
    """
    Convert all results to a dictionary (for API use).

    Returns the same structure as output_json but as a dict instead
    of printing to stdout.
    """
    output = {
        "timestamp": datetime.now().isoformat(),
        "ping_results": [asdict(r) for r in ping_results],
        "speedtest": asdict(speedtest_result),
        "dns_results": [asdict(r) for r in dns_results],
        "mtr_results": [
            {
                "target": r.target,
                "target_name": r.target_name,
                "success": r.success,
                "error": r.error,
                "hops": [asdict(h) for h in r.hops],
            }
            for r in mtr_results
        ],
        "diagnostic": asdict(diagnostic),
    }

    if port_results:
        output["port_results"] = [asdict(r) for r in port_results]
    if http_results:
        output["http_results"] = [asdict(r) for r in http_results]
    if video_service_results:
        output["video_services"] = [asdict(r) for r in video_service_results]

    return output
