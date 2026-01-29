"""Prometheus metrics exporter for network test results."""

import threading
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import PingResult, SpeedTestResult, DnsResult, MtrResult

# Try to import prometheus_client
try:
    from prometheus_client import (
        Gauge, Counter, start_http_server,
        REGISTRY, CollectorRegistry
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Gauge = None  # type: ignore
    Counter = None  # type: ignore


# Metrics definitions (created lazily)
_metrics_initialized = False
_ping_latency: Optional["Gauge"] = None
_ping_jitter: Optional["Gauge"] = None
_ping_loss: Optional["Gauge"] = None
_speedtest_download: Optional["Gauge"] = None
_speedtest_upload: Optional["Gauge"] = None
_speedtest_ping: Optional["Gauge"] = None
_dns_resolution_time: Optional["Gauge"] = None
_mtr_hop_latency: Optional["Gauge"] = None
_mtr_hop_loss: Optional["Gauge"] = None
_test_runs: Optional["Counter"] = None

_server_started = False
_server_lock = threading.Lock()


def _init_metrics() -> None:
    """Initialize Prometheus metrics (lazy initialization)."""
    global _metrics_initialized
    global _ping_latency, _ping_jitter, _ping_loss
    global _speedtest_download, _speedtest_upload, _speedtest_ping
    global _dns_resolution_time
    global _mtr_hop_latency, _mtr_hop_loss
    global _test_runs

    if _metrics_initialized or not PROMETHEUS_AVAILABLE:
        return

    # Ping metrics
    _ping_latency = Gauge(
        'nettest_ping_latency_ms',
        'Ping latency in milliseconds',
        ['target', 'metric']  # metric: min, avg, max
    )
    _ping_jitter = Gauge(
        'nettest_ping_jitter_ms',
        'Ping jitter (variation) in milliseconds',
        ['target']
    )
    _ping_loss = Gauge(
        'nettest_ping_packet_loss_percent',
        'Packet loss percentage',
        ['target']
    )

    # Speed test metrics
    _speedtest_download = Gauge(
        'nettest_speedtest_download_mbps',
        'Download speed in Mbps'
    )
    _speedtest_upload = Gauge(
        'nettest_speedtest_upload_mbps',
        'Upload speed in Mbps'
    )
    _speedtest_ping = Gauge(
        'nettest_speedtest_ping_ms',
        'Speed test server ping in milliseconds'
    )

    # DNS metrics
    _dns_resolution_time = Gauge(
        'nettest_dns_resolution_time_ms',
        'DNS resolution time in milliseconds',
        ['target']
    )

    # MTR metrics
    _mtr_hop_latency = Gauge(
        'nettest_mtr_hop_latency_ms',
        'MTR hop latency in milliseconds',
        ['target', 'hop', 'host']
    )
    _mtr_hop_loss = Gauge(
        'nettest_mtr_hop_loss_percent',
        'MTR hop packet loss percentage',
        ['target', 'hop', 'host']
    )

    # Test run counter
    _test_runs = Counter(
        'nettest_test_runs_total',
        'Total number of test runs',
        ['status']  # success, failure
    )

    _metrics_initialized = True


def start_metrics_server(port: int = 9101) -> bool:
    """
    Start the Prometheus metrics HTTP server.

    Args:
        port: Port to listen on (default: 9101)

    Returns:
        True if server started successfully, False otherwise
    """
    global _server_started

    if not PROMETHEUS_AVAILABLE:
        raise ImportError("prometheus-client is not installed")

    with _server_lock:
        if _server_started:
            return True

        _init_metrics()
        start_http_server(port)
        _server_started = True
        return True


def update_metrics(
    ping_results: List["PingResult"],
    speedtest_result: "SpeedTestResult",
    dns_results: List["DnsResult"],
    mtr_results: List["MtrResult"],
) -> None:
    """
    Update Prometheus metrics with test results.

    Args:
        ping_results: List of ping test results
        speedtest_result: Speed test result
        dns_results: List of DNS test results
        mtr_results: List of MTR results
    """
    if not PROMETHEUS_AVAILABLE or not _metrics_initialized:
        return

    # Update ping metrics
    for result in ping_results:
        if result.success:
            _ping_latency.labels(target=result.target_name, metric='min').set(result.min_ms)
            _ping_latency.labels(target=result.target_name, metric='avg').set(result.avg_ms)
            _ping_latency.labels(target=result.target_name, metric='max').set(result.max_ms)
            _ping_jitter.labels(target=result.target_name).set(result.jitter_ms)
            _ping_loss.labels(target=result.target_name).set(result.packet_loss)

    # Update speed test metrics
    if speedtest_result.success:
        _speedtest_download.set(speedtest_result.download_mbps)
        _speedtest_upload.set(speedtest_result.upload_mbps)
        _speedtest_ping.set(speedtest_result.ping_ms)

    # Update DNS metrics
    for result in dns_results:
        if result.success and result.resolution_time_ms > 0:
            _dns_resolution_time.labels(target=result.target).set(result.resolution_time_ms)

    # Update MTR metrics
    for mtr_result in mtr_results:
        if mtr_result.success:
            for hop in mtr_result.hops:
                _mtr_hop_latency.labels(
                    target=mtr_result.target_name,
                    hop=str(hop.hop_number),
                    host=hop.host
                ).set(hop.avg_ms)
                _mtr_hop_loss.labels(
                    target=mtr_result.target_name,
                    hop=str(hop.hop_number),
                    host=hop.host
                ).set(hop.loss_pct)

    # Increment test run counter
    all_success = all(r.success for r in ping_results) and speedtest_result.success
    _test_runs.labels(status='success' if all_success else 'partial').inc()


def get_metrics_text() -> str:
    """
    Get current metrics in Prometheus text format.

    Returns:
        Metrics in Prometheus exposition format
    """
    if not PROMETHEUS_AVAILABLE:
        return "# prometheus-client not installed\n"

    from prometheus_client import generate_latest
    return generate_latest(REGISTRY).decode('utf-8')
