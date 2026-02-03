"""TCP port connectivity test implementation."""

import socket
import time
from typing import List, Optional

from ..models import PortResult


def check_tcp_port(
    host: str,
    port: int,
    timeout: float = 5.0,
    source_interface: Optional[str] = None,
) -> PortResult:
    """
    Test TCP connectivity to a specific port.

    Args:
        host: Hostname or IP address
        port: Port number to test
        timeout: Connection timeout in seconds
        source_interface: Source interface IP to bind to (optional)

    Returns:
        PortResult with connection status and response time
    """
    result = PortResult(host=host, port=port)

    try:
        start_time = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        # Bind to specific interface if requested
        if source_interface:
            try:
                sock.bind((source_interface, 0))
            except OSError as e:
                result.error = f"Cannot bind to {source_interface}: {e}"
                result.error_simple = "Network adapter issue. Try: check your network settings"
                return result

        # Attempt connection
        error_code = sock.connect_ex((host, port))
        end_time = time.perf_counter()

        result.response_time_ms = (end_time - start_time) * 1000

        if error_code == 0:
            result.open = True
        else:
            result.open = False
            result.error = f"Connection refused (error code: {error_code})"
            result.error_simple = "Port is closed or blocked. This service may not be available"

        sock.close()

    except socket.timeout:
        result.error = f"Connection timed out after {timeout}s"
        result.error_simple = "Connection too slow. Try: restart your router"
    except socket.gaierror as e:
        result.error = f"DNS resolution failed: {e}"
        result.error_simple = "Cannot find server. Try: check if the address is correct"
    except OSError as e:
        result.error = f"Connection error: {e}"
        result.error_simple = "Connection failed. Try: check your internet connection"

    return result


def check_tcp_ports(
    host: str,
    ports: List[int],
    timeout: float = 5.0,
    source_interface: Optional[str] = None,
) -> List[PortResult]:
    """
    Test TCP connectivity to multiple ports on a host.

    Args:
        host: Hostname or IP address
        ports: List of port numbers to test
        timeout: Connection timeout in seconds per port
        source_interface: Source interface IP to bind to (optional)

    Returns:
        List of PortResult for each port
    """
    results = []
    for port in ports:
        result = check_tcp_port(host, port, timeout, source_interface)
        results.append(result)
    return results
