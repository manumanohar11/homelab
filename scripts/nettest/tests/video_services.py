"""Video conferencing service connectivity tests."""

import socket
import struct
import time
from typing import List, Optional, Tuple

from ..models import VideoServiceResult
from ..config import VIDEO_SERVICES
from .dns import run_dns_test
from .tcp import check_tcp_port


def check_stun_connectivity(
    server: str,
    port: int,
    timeout: float = 5.0,
) -> Tuple[bool, float]:
    """
    Test STUN connectivity by sending a binding request.

    Args:
        server: STUN server hostname
        port: STUN server port
        timeout: Timeout in seconds

    Returns:
        Tuple of (success, latency_ms)
    """
    try:
        # Resolve server hostname
        try:
            server_ip = socket.gethostbyname(server)
        except socket.gaierror:
            return False, 0.0

        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        # Build STUN Binding Request (RFC 5389)
        # Message Type: 0x0001 (Binding Request)
        # Message Length: 0 (no attributes)
        # Magic Cookie: 0x2112A442
        # Transaction ID: 12 random bytes
        import os
        transaction_id = os.urandom(12)
        magic_cookie = 0x2112A442

        stun_header = struct.pack(
            '>HHI12s',
            0x0001,          # Message Type: Binding Request
            0,               # Message Length
            magic_cookie,    # Magic Cookie
            transaction_id   # Transaction ID
        )

        start_time = time.perf_counter()
        sock.sendto(stun_header, (server_ip, port))

        # Wait for response
        try:
            data, _ = sock.recvfrom(1024)
            end_time = time.perf_counter()

            # Verify response is a STUN Binding Response (0x0101)
            if len(data) >= 20:
                msg_type = struct.unpack('>H', data[:2])[0]
                if msg_type == 0x0101:  # Binding Success Response
                    latency_ms = (end_time - start_time) * 1000
                    sock.close()
                    return True, latency_ms

            sock.close()
            return False, 0.0

        except socket.timeout:
            sock.close()
            return False, 0.0

    except Exception:
        return False, 0.0


def test_video_service(
    name: str,
    config: dict,
    timeout: float = 5.0,
) -> VideoServiceResult:
    """
    Test connectivity to a single video conferencing service.

    Args:
        name: Service name
        config: Service configuration dict
        timeout: Timeout per test in seconds

    Returns:
        VideoServiceResult with all test results
    """
    result = VideoServiceResult(
        name=name,
        domain=config["domain"],
    )

    issues = []

    # Test 1: DNS Resolution
    dns_result = run_dns_test(config["domain"])
    result.dns_ok = dns_result.success
    result.dns_latency_ms = dns_result.resolution_time_ms

    if not result.dns_ok:
        issues.append(f"DNS resolution failed: {dns_result.error}")
        result.status = "blocked"
        result.issues = issues
        result.error = f"DNS resolution failed for {name}: {dns_result.error}"
        result.error_simple = f"Cannot connect to {name}. Try: check your internet connection"
        return result

    # Test 2: TCP Port Connectivity
    all_ports_ok = True
    critical_port_ok = False  # Port 443 is critical

    for port in config["tcp_ports"]:
        port_result = check_tcp_port(config["domain"], port, timeout=timeout)
        result.tcp_ports[port] = port_result.open
        result.tcp_latencies[port] = port_result.response_time_ms

        if port_result.open:
            if port == 443:
                critical_port_ok = True
        else:
            all_ports_ok = False
            issues.append(f"Port {port} blocked")

    if not critical_port_ok:
        result.status = "blocked"
        result.issues = issues
        result.error = f"Port 443 (HTTPS) blocked for {name}"
        result.error_simple = f"{name} is blocked. Your network may be restricting video calls"
        return result

    # Test 3: STUN Connectivity
    stun_ok, stun_latency = check_stun_connectivity(
        config["stun_server"],
        config["stun_port"],
        timeout=timeout,
    )
    result.stun_ok = stun_ok
    result.stun_latency_ms = stun_latency

    if not stun_ok:
        issues.append("STUN connectivity failed (UDP may be blocked)")

    # Determine overall status
    if all_ports_ok and stun_ok:
        result.status = "ready"
    elif critical_port_ok:
        result.status = "degraded"
        result.error = f"{name} connectivity is degraded: {', '.join(issues)}"
        result.error_simple = f"{name} may have issues. Video calls might not work perfectly"
    else:
        result.status = "blocked"
        result.error = f"{name} is blocked: {', '.join(issues)}"
        result.error_simple = f"{name} is blocked. Your network may be restricting video calls"

    result.issues = issues
    return result


def run_video_service_tests(
    services: Optional[dict] = None,
    timeout: float = 5.0,
) -> List[VideoServiceResult]:
    """
    Run connectivity tests for all video conferencing services.

    Args:
        services: Service configuration dict (defaults to VIDEO_SERVICES)
        timeout: Timeout per test in seconds

    Returns:
        List of VideoServiceResult for each service
    """
    if services is None:
        services = VIDEO_SERVICES

    results = []
    for name, config in services.items():
        result = test_video_service(name, config, timeout)
        results.append(result)

    return results
