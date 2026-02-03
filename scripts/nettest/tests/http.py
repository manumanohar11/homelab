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
        if e.code == 403:
            result.error_simple = "Access denied. The website blocked this request"
        elif e.code == 404:
            result.error_simple = "Page not found. Try: check if the address is correct"
        elif e.code >= 500:
            result.error_simple = "Website is having problems. Try: wait and try again later"
        else:
            result.error_simple = "Website returned an error. Try: check the address"
        result.success = False

    except urllib.error.URLError as e:
        result.error = f"Connection failed: {e.reason}"
        reason_str = str(e.reason).lower()
        if "timeout" in reason_str or "timed out" in reason_str:
            result.error_simple = "Website took too long to respond. Try: check your internet connection"
        elif "name or service not known" in reason_str or "getaddrinfo" in reason_str:
            result.error_simple = "Cannot find website. Try: check if the address is correct"
        elif "connection refused" in reason_str:
            result.error_simple = "Website is not responding. Try: check if the website is online"
        elif "ssl" in reason_str or "certificate" in reason_str:
            result.error_simple = "Security error. The website's certificate may have a problem"
        else:
            result.error_simple = "Cannot connect to website. Try: check your internet connection"
        result.success = False

    except Exception as e:
        result.error = f"Request failed: {str(e)}"
        result.error_simple = "Request failed. Try: check your internet connection"
        result.success = False

    return result
