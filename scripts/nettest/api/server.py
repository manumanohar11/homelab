"""REST API server for the network testing tool.

Provides HTTP endpoints for running network tests and retrieving results.
Uses Python's stdlib http.server to avoid external dependencies.
"""

import json
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .. import __version__
from ..config import load_config, apply_profile, list_profiles, DEFAULT_CONFIG
from ..diagnostics import diagnose_network
from ..models import SpeedTestResult
from ..output.json_output import results_to_dict
from ..tests.runner import run_tests_with_progress

# Thread lock for serializing test execution
_test_lock = threading.Lock()

# Timeout for acquiring the test lock (seconds)
_TEST_LOCK_TIMEOUT = 300  # 5 minutes


class NettestAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the nettest REST API.

    Endpoints:
        GET /health - Health check endpoint
        GET /run - Run tests with quick profile
        GET /run/<profile> - Run tests with specified profile
        GET /metrics - Return Prometheus-format metrics
    """

    # Server version for response headers
    server_version = f"nettest/{__version__}"

    def log_message(self, format: str, *args: Any) -> None:
        """Log HTTP requests to stderr.

        Args:
            format: Log message format string
            *args: Format arguments
        """
        sys.stderr.write(
            f"[{datetime.now().isoformat()}] {self.address_string()} - {format % args}\n"
        )

    def send_json_response(
        self,
        data: Dict[str, Any],
        status_code: int = 200,
    ) -> None:
        """Send a JSON response with appropriate headers.

        Args:
            data: Dictionary to serialize as JSON
            status_code: HTTP status code (default: 200)
        """
        response_body = json.dumps(data, indent=2).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

        self.wfile.write(response_body)

    def send_text_response(
        self,
        text: str,
        content_type: str = "text/plain",
        status_code: int = 200,
    ) -> None:
        """Send a text response with appropriate headers.

        Args:
            text: Text content to send
            content_type: MIME type (default: text/plain)
            status_code: HTTP status code (default: 200)
        """
        response_body = text.encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        self.wfile.write(response_body)

    def send_error_json(
        self,
        status_code: int,
        message: str,
        details: Optional[str] = None,
    ) -> None:
        """Send a JSON error response.

        Args:
            status_code: HTTP status code
            message: Error message
            details: Optional additional details
        """
        error_data: Dict[str, Any] = {
            "error": message,
            "status": status_code,
        }
        if details:
            error_data["details"] = details

        self.send_json_response(error_data, status_code)

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        """Handle GET requests and route to appropriate handler."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path.rstrip("/")

        # Route to appropriate handler
        if path == "/health":
            self.handle_health()
        elif path == "/run":
            self.handle_run("quick")
        elif path.startswith("/run/"):
            profile = path[5:]  # Remove "/run/" prefix
            self.handle_run(profile)
        elif path == "/metrics":
            self.handle_metrics()
        else:
            self.send_error_json(
                404,
                "Not Found",
                f"Unknown endpoint: {path}. Available: /health, /run, /run/<profile>, /metrics",
            )

    def handle_health(self) -> None:
        """Handle GET /health endpoint.

        Returns server health status and version.
        """
        self.send_json_response({
            "status": "ok",
            "version": __version__,
            "timestamp": datetime.now().isoformat(),
        })

    def handle_run(self, profile: str) -> None:
        """Handle GET /run and GET /run/<profile> endpoints.

        Runs network tests with the specified profile and returns JSON results.

        Args:
            profile: Test profile name (e.g., "quick", "full", "gaming")
        """
        # Load configuration
        config = load_config(quiet=True)

        # Validate profile
        available_profiles = list_profiles(config)
        if profile not in available_profiles:
            self.send_error_json(
                400,
                "Invalid profile",
                f"Profile '{profile}' not found. Available: {', '.join(available_profiles)}",
            )
            return

        # Apply the profile
        config = apply_profile(config, profile)

        # Try to acquire the test lock (non-blocking with timeout)
        acquired = _test_lock.acquire(timeout=_TEST_LOCK_TIMEOUT)
        if not acquired:
            self.send_error_json(
                503,
                "Service Unavailable",
                "Another test is currently running. Please try again later.",
            )
            return

        try:
            # Extract test parameters from config
            targets = config["targets"]
            thresholds = config["thresholds"]
            ping_count = config["tests"]["ping_count"]
            mtr_count = config["tests"]["mtr_count"]
            expected_speed = config["tests"]["expected_speed"]

            # Get profile-specific skip flags
            profile_config = config.get("profiles", {}).get(profile, {})
            skip_speedtest = profile_config.get("skip_speedtest", False)
            skip_dns = profile_config.get("skip_dns", False)
            skip_mtr = profile_config.get("skip_mtr", False)

            # Run tests (with quiet=True to suppress console output)
            (
                ping_results,
                speedtest_result,
                dns_results,
                mtr_results,
                bufferbloat_result,
                video_service_results,
            ) = run_tests_with_progress(
                targets,
                ping_count=ping_count,
                mtr_count=mtr_count,
                quiet=True,
                skip_speedtest=skip_speedtest,
                skip_dns=skip_dns,
                skip_mtr=skip_mtr,
                parallel=True,  # Use parallel execution for API
            )

            # Run diagnostics
            diagnostic = diagnose_network(
                ping_results,
                speedtest_result,
                mtr_results,
                expected_speed,
                thresholds,
            )

            # Convert results to dict
            results = results_to_dict(
                ping_results=ping_results,
                speedtest_result=speedtest_result,
                dns_results=dns_results,
                mtr_results=mtr_results,
                diagnostic=diagnostic,
                video_service_results=video_service_results if video_service_results else None,
            )

            # Add profile and config info
            results["profile"] = profile
            results["config"] = {
                "ping_count": ping_count,
                "mtr_count": mtr_count,
                "expected_speed": expected_speed,
                "targets": list(targets.keys()),
            }

            self.send_json_response(results)

        except Exception as e:
            self.send_error_json(
                500,
                "Internal Server Error",
                str(e),
            )
        finally:
            _test_lock.release()

    def handle_metrics(self) -> None:
        """Handle GET /metrics endpoint.

        Returns Prometheus-format metrics if available.
        """
        try:
            from ..output.prometheus import get_metrics_text, PROMETHEUS_AVAILABLE

            if not PROMETHEUS_AVAILABLE:
                self.send_error_json(
                    503,
                    "Prometheus not available",
                    "prometheus-client is not installed. Install with: pip install prometheus-client",
                )
                return

            metrics_text = get_metrics_text()
            self.send_text_response(
                metrics_text,
                content_type="text/plain; version=0.0.4; charset=utf-8",
            )

        except ImportError:
            self.send_error_json(
                503,
                "Prometheus not available",
                "prometheus-client is not installed",
            )


def start_api_server(
    port: int = 8080,
    host: str = "0.0.0.0",
    blocking: bool = True,
) -> Optional[HTTPServer]:
    """Start the REST API server.

    Args:
        port: Port to listen on (default: 8080)
        host: Host to bind to (default: 0.0.0.0)
        blocking: If True, run server in blocking mode. If False, run in
            background thread and return the server instance.

    Returns:
        HTTPServer instance if blocking=False, None otherwise.
    """
    server_address = (host, port)
    httpd = HTTPServer(server_address, NettestAPIHandler)

    sys.stderr.write(f"[{datetime.now().isoformat()}] Starting nettest API server on {host}:{port}\n")
    sys.stderr.write(f"[{datetime.now().isoformat()}] Endpoints:\n")
    sys.stderr.write(f"  GET /health       - Health check\n")
    sys.stderr.write(f"  GET /run          - Run quick profile test\n")
    sys.stderr.write(f"  GET /run/<profile> - Run specific profile (quick, full, gaming, etc.)\n")
    sys.stderr.write(f"  GET /metrics      - Prometheus metrics\n")
    sys.stderr.write(f"[{datetime.now().isoformat()}] Press Ctrl+C to stop\n")

    if blocking:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            sys.stderr.write(f"\n[{datetime.now().isoformat()}] Shutting down API server\n")
            httpd.shutdown()
        return None
    else:
        # Run in background thread
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        return httpd
