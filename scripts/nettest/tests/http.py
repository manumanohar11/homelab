"""HTTP/HTTPS latency test implementation."""

import time
import urllib.request
import urllib.error

from ..models import HttpResult


def measure_http_latency(url: str, timeout: float = 10.0) -> HttpResult:
    """
    Measure HTTP/HTTPS response time.

    Uses urllib to make a HEAD request and measure response time.
    This tests application-layer connectivity, not just ICMP.

    Args:
        url: Full URL (must include http:// or https://)
        timeout: Request timeout in seconds

    Returns:
        HttpResult with status code and response time
    """
    result = HttpResult(url=url)

    # Ensure URL has a scheme
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        result.url = url

    start_time = time.perf_counter()

    try:
        request = urllib.request.Request(url, method='HEAD')
        request.add_header('User-Agent', 'nettest/2.0')

        with urllib.request.urlopen(request, timeout=timeout) as response:
            end_time = time.perf_counter()
            result.status_code = response.status
            result.response_time_ms = (end_time - start_time) * 1000
            result.success = 200 <= response.status < 400

    except urllib.error.HTTPError as e:
        end_time = time.perf_counter()
        result.status_code = e.code
        result.response_time_ms = (end_time - start_time) * 1000
        result.error = f"HTTP {e.code}: {e.reason}"
        result.success = False

    except urllib.error.URLError as e:
        result.error = f"Connection failed: {e.reason}"
        result.success = False

    except Exception as e:
        result.error = f"Request failed: {str(e)}"
        result.success = False

    return result
