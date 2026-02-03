"""Speed test implementation."""

import json

from ..models import SpeedTestResult
from ..utils.commands import run_command


def run_speedtest() -> SpeedTestResult:
    """
    Run speedtest using speedtest-cli or ookla speedtest.

    Tries speedtest-cli first, then falls back to ookla official CLI.

    Returns:
        SpeedTestResult with download/upload speeds and ping
    """
    result = SpeedTestResult()
    last_error = ""

    # Try speedtest-cli first
    cmd = ["speedtest-cli", "--json"]
    exit_code, stdout, stderr = run_command(cmd, timeout=120)

    if exit_code == 0 and stdout:
        try:
            data = json.loads(stdout)
            result.download_mbps = data.get("download", 0) / 1_000_000  # Convert to Mbps
            result.upload_mbps = data.get("upload", 0) / 1_000_000
            result.ping_ms = data.get("ping", 0)
            result.server = data.get("server", {}).get("sponsor", "Unknown")
            result.success = True
            return result
        except json.JSONDecodeError:
            last_error = "Failed to parse speedtest-cli output"
    elif stderr:
        last_error = stderr.strip()

    # Try alternative: speedtest (ookla official)
    cmd = ["speedtest", "--format=json"]
    exit_code, stdout, stderr = run_command(cmd, timeout=120)

    if exit_code == 0 and stdout:
        try:
            data = json.loads(stdout)
            result.download_mbps = data.get("download", {}).get("bandwidth", 0) * 8 / 1_000_000
            result.upload_mbps = data.get("upload", {}).get("bandwidth", 0) * 8 / 1_000_000
            result.ping_ms = data.get("ping", {}).get("latency", 0)
            result.server = data.get("server", {}).get("name", "Unknown")
            result.success = True
            return result
        except json.JSONDecodeError:
            last_error = "Failed to parse speedtest output"
    elif stderr and not last_error:
        last_error = stderr.strip()

    # Provide error message with actual error if available (technical and simple)
    if last_error:
        if "403" in last_error or "Forbidden" in last_error:
            result.error = (
                "Speed test blocked by speedtest.net (HTTP 403).\n"
                "  Try again later or use Ookla official CLI:\n"
                "  https://www.speedtest.net/apps/cli"
            )
            result.error_simple = "Speed test temporarily blocked. Try: wait a few minutes and try again"
        elif "timeout" in last_error.lower():
            result.error = f"Speed test timed out: {last_error}"
            result.error_simple = "Speed test took too long. Try: check your internet connection"
        elif "connection" in last_error.lower() or "network" in last_error.lower():
            result.error = f"Speed test failed: {last_error}"
            result.error_simple = "Cannot test speed. Check your internet connection"
        else:
            result.error = f"Speed test failed: {last_error}"
            result.error_simple = "Speed test failed. Try: restart your router and try again"
    else:
        result.error = (
            "Speed test tools not found.\n"
            "  Install (Debian/Ubuntu): sudo apt install speedtest-cli\n"
            "  Install (Fedora/RHEL): pip install speedtest-cli\n"
            "  Or use Ookla official: https://www.speedtest.net/apps/cli"
        )
        result.error_simple = "Speed test unavailable. Install speedtest-cli for this feature"
    return result
