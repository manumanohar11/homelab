# Video Conferencing Services Testing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add dedicated testing for 5 video conferencing services (Teams, Zoom, WhatsApp, Google Meet, Webex) with DNS, TCP port, and STUN connectivity checks.

**Architecture:** Opt-in feature via `--video-services` / `-vs` flag. Each service is tested for DNS resolution, TCP port connectivity, and STUN binding. Results displayed in a dedicated section in both CLI and HTML output.

**Tech Stack:** Python standard library (socket, struct for STUN), existing Rich library for CLI, existing HTML template system.

---

### Task 1: Add VideoServiceResult Model

**Files:**
- Modify: `nettest/models.py:140` (append after HttpResult)

**Step 1: Write the model code**

Add at end of `nettest/models.py`:

```python
@dataclass
class VideoServiceResult:
    """Result of video conferencing service connectivity test."""
    name: str                              # "Zoom", "WhatsApp", etc.
    domain: str                            # Primary domain tested
    dns_ok: bool = False                   # Could resolve primary domain
    dns_latency_ms: float = 0.0            # DNS resolution time
    tcp_ports: Dict[int, bool] = field(default_factory=dict)  # {443: True, 8801: False}
    tcp_latencies: Dict[int, float] = field(default_factory=dict)  # {443: 15.2, 8801: 0.0}
    stun_ok: bool = False                  # STUN binding succeeded
    stun_latency_ms: float = 0.0           # RTT to STUN server
    status: str = "blocked"                # "ready", "degraded", "blocked"
    issues: List[str] = field(default_factory=list)  # ["Port 8801 blocked"]
```

**Step 2: Add Dict import**

Update imports at top of `models.py`:

```python
from typing import List, Dict
```

**Step 3: Verify file is valid Python**

Run: `python -c "from nettest.models import VideoServiceResult; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add nettest/models.py
git commit -m "feat(models): add VideoServiceResult dataclass for video service testing"
```

---

### Task 2: Add Video Services Configuration

**Files:**
- Modify: `nettest/config.py:71` (after DEFAULT_CONFIG closing brace)

**Step 1: Add VIDEO_SERVICES constant**

Add after line 71 (after `DEFAULT_CONFIG` dict):

```python
# Video Conferencing Service Endpoints
VIDEO_SERVICES = {
    "Microsoft Teams": {
        "domain": "teams.microsoft.com",
        "tcp_ports": [443, 3478],
        "stun_server": "stun.teams.microsoft.com",
        "stun_port": 3478,
    },
    "Zoom": {
        "domain": "zoom.us",
        "tcp_ports": [443, 8801, 8802],
        "stun_server": "stun.zoom.us",
        "stun_port": 3478,
    },
    "WhatsApp": {
        "domain": "web.whatsapp.com",
        "tcp_ports": [443, 5222],
        "stun_server": "stun.whatsapp.net",
        "stun_port": 3478,
    },
    "Google Meet": {
        "domain": "meet.google.com",
        "tcp_ports": [443, 19302],
        "stun_server": "stun.l.google.com",
        "stun_port": 19302,
    },
    "Webex": {
        "domain": "webex.com",
        "tcp_ports": [443, 5004],
        "stun_server": "stun.webex.com",
        "stun_port": 3478,
    },
}
```

**Step 2: Verify file is valid Python**

Run: `python -c "from nettest.config import VIDEO_SERVICES; print(len(VIDEO_SERVICES), 'services')"`
Expected: `5 services`

**Step 3: Commit**

```bash
git add nettest/config.py
git commit -m "feat(config): add VIDEO_SERVICES configuration for 5 video conferencing services"
```

---

### Task 3: Create Video Services Test Module

**Files:**
- Create: `nettest/tests/video_services.py`

**Step 1: Create the video services test module**

Create `nettest/tests/video_services.py`:

```python
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
    else:
        result.status = "blocked"

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
```

**Step 2: Verify module imports correctly**

Run: `python -c "from nettest.tests.video_services import run_video_service_tests; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add nettest/tests/video_services.py
git commit -m "feat(tests): add video_services module with STUN and TCP port testing"
```

---

### Task 4: Export Video Services from Tests Package

**Files:**
- Modify: `nettest/tests/__init__.py`

**Step 1: Add exports**

Update `nettest/tests/__init__.py` to add the new imports and exports:

```python
"""Network test implementations."""

from .ping import run_ping_test
from .speedtest import run_speedtest
from .dns import run_dns_test
from .mtr import run_mtr
from .tcp import check_tcp_port, check_tcp_ports
from .http import measure_http_latency
from .runner import run_tests_with_progress
from .stability import calculate_connection_score, calculate_mos_score
from .bufferbloat import detect_bufferbloat, grade_bufferbloat
from .video_services import run_video_service_tests, test_video_service, check_stun_connectivity

__all__ = [
    "run_ping_test",
    "run_speedtest",
    "run_dns_test",
    "run_mtr",
    "check_tcp_port",
    "check_tcp_ports",
    "measure_http_latency",
    "run_tests_with_progress",
    "calculate_connection_score",
    "calculate_mos_score",
    "detect_bufferbloat",
    "grade_bufferbloat",
    "run_video_service_tests",
    "test_video_service",
    "check_stun_connectivity",
]
```

**Step 2: Verify exports**

Run: `python -c "from nettest.tests import run_video_service_tests; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add nettest/tests/__init__.py
git commit -m "feat(tests): export video service test functions"
```

---

### Task 5: Add CLI Flag and Integration

**Files:**
- Modify: `nettest/cli.py`

**Step 1: Add import for VideoServiceResult**

Update imports around line 14:

```python
from .models import PortResult, HttpResult, VideoServiceResult
```

**Step 2: Add import for run_video_service_tests**

Update imports around line 15-22 to include:

```python
from .tests import (
    run_tests_with_progress,
    check_tcp_port,
    measure_http_latency,
    calculate_connection_score,
    calculate_mos_score,
    detect_bufferbloat,
    run_video_service_tests,
)
```

**Step 3: Add --video-services argument**

Add after line 210 (after `--parallel` argument):

```python
    parser.add_argument(
        "--video-services", "-vs",
        action="store_true",
        help="Test video conferencing service connectivity (Teams, Zoom, WhatsApp, Meet, Webex)"
    )
```

**Step 4: Add video service test execution**

Add after line 435 (after HTTP latency tests section, before diagnostics):

```python
    # Run video service tests if requested
    video_service_results = []
    if args.video_services:
        if not suppress_output:
            console.print("[dim]Running video service connectivity tests...[/dim]")
        video_service_results = run_video_service_tests()
```

**Step 5: Add video service display in terminal output**

Add after line 514 (after VoIP quality display):

```python
            # Show video service results if tested
            if video_service_results:
                _display_video_services(video_service_results, console)
```

**Step 6: Add _display_video_services helper function**

Add before `_list_network_interfaces` function (around line 586):

```python
def _display_video_services(results: List[VideoServiceResult], console: Console) -> None:
    """Display video conferencing service test results."""
    from rich.table import Table
    from rich import box

    console.print()
    console.print("[bold]Video Conferencing Services[/bold]")

    table = Table(box=box.ROUNDED)
    table.add_column("Service", style="cyan")
    table.add_column("DNS", justify="center")
    table.add_column("Ports", justify="left")
    table.add_column("STUN", justify="center")
    table.add_column("Status", justify="center")

    for r in results:
        # DNS column
        dns_str = f"[green]{r.dns_latency_ms:.0f}ms[/green]" if r.dns_ok else "[red]fail[/red]"

        # Ports column
        port_strs = []
        for port, ok in r.tcp_ports.items():
            if ok:
                port_strs.append(f"[green]{port}[/green]")
            else:
                port_strs.append(f"[red]{port}[/red]")
        ports_str = " ".join(port_strs) if port_strs else "-"

        # STUN column
        if r.stun_ok:
            stun_str = f"[green]{r.stun_latency_ms:.0f}ms[/green]"
        else:
            stun_str = "[red]fail[/red]"

        # Status column
        status_colors = {"ready": "green", "degraded": "yellow", "blocked": "red"}
        status_icons = {"ready": "Ready", "degraded": "Degraded", "blocked": "Blocked"}
        status_color = status_colors.get(r.status, "white")
        status_text = status_icons.get(r.status, r.status)
        status_str = f"[{status_color}]{status_text}[/{status_color}]"

        table.add_row(r.name, dns_str, ports_str, stun_str, status_str)

    console.print(table)

    # Show issues if any
    issues = []
    for r in results:
        if r.issues:
            for issue in r.issues:
                issues.append(f"{r.name}: {issue}")

    if issues:
        console.print()
        console.print("[bold]Issues:[/bold]")
        for issue in issues:
            console.print(f"  [yellow]{issue}[/yellow]")

    console.print()
```

**Step 7: Update generate_html call to pass video_service_results**

Update the `generate_html` call around line 537-551 to add `video_service_results`:

```python
        html_path = generate_html(
            ping_results,
            speedtest_result,
            dns_results,
            mtr_results,
            expected_speed,
            output_dir,
            diagnostic,
            thresholds,
            historical_data=previous_history,
            connection_score=connection_score,
            voip_quality=voip_quality,
            isp_evidence=isp_evidence,
            bufferbloat_result=bufferbloat_result,
            video_service_results=video_service_results,
        )
```

**Step 8: Verify CLI parses correctly**

Run: `python -m nettest.cli --help | grep -A1 video`
Expected: Shows `--video-services, -vs` option

**Step 9: Commit**

```bash
git add nettest/cli.py
git commit -m "feat(cli): add --video-services flag and display function"
```

---

### Task 6: Add Terminal Display Function

**Files:**
- Modify: `nettest/output/terminal.py`

**Step 1: Add VideoServiceResult import**

Update imports around line 11-14:

```python
from ..models import (
    PingResult, SpeedTestResult, DnsResult,
    MtrResult, DiagnosticResult, PortResult, HttpResult, VideoServiceResult
)
```

**Step 2: Add video_service_results parameter to display_terminal**

Update function signature at line 56-67:

```python
def display_terminal(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    dns_results: List[DnsResult],
    mtr_results: List[MtrResult],
    expected_speed: float,
    diagnostic: DiagnosticResult,
    thresholds: Dict[str, Any],
    console: Console,
    port_results: List[PortResult] = None,
    http_results: List[HttpResult] = None,
    video_service_results: List[VideoServiceResult] = None,
) -> None:
```

**Step 3: Add video services display call**

Add after line 113 (after http_results display):

```python
    # Video Service Results (if any)
    if video_service_results:
        _display_video_services(video_service_results, console)
```

**Step 4: Add _display_video_services function**

Add at end of file:

```python
def _display_video_services(results: List[VideoServiceResult], console: Console) -> None:
    """Display video conferencing service test results."""
    console.print("[bold]Video Conferencing Services[/bold]")

    table = Table(box=box.ROUNDED)
    table.add_column("Service", style="cyan")
    table.add_column("DNS", justify="center")
    table.add_column("Ports", justify="left")
    table.add_column("STUN", justify="center")
    table.add_column("Status", justify="center")

    for r in results:
        # DNS column
        dns_str = f"[green]{r.dns_latency_ms:.0f}ms[/green]" if r.dns_ok else "[red]fail[/red]"

        # Ports column
        port_strs = []
        for port, ok in r.tcp_ports.items():
            if ok:
                port_strs.append(f"[green]{port}[/green]")
            else:
                port_strs.append(f"[red]{port}[/red]")
        ports_str = " ".join(port_strs) if port_strs else "-"

        # STUN column
        if r.stun_ok:
            stun_str = f"[green]{r.stun_latency_ms:.0f}ms[/green]"
        else:
            stun_str = "[red]fail[/red]"

        # Status column
        status_colors = {"ready": "green", "degraded": "yellow", "blocked": "red"}
        status_icons = {"ready": "Ready", "degraded": "Degraded", "blocked": "Blocked"}
        status_color = status_colors.get(r.status, "white")
        status_text = status_icons.get(r.status, r.status)
        status_str = f"[{status_color}]{status_text}[/{status_color}]"

        table.add_row(r.name, dns_str, ports_str, stun_str, status_str)

    console.print(table)

    # Show issues if any
    issues = []
    for r in results:
        if r.issues:
            for issue in r.issues:
                issues.append(f"{r.name}: {issue}")

    if issues:
        console.print()
        console.print("[bold]Issues:[/bold]")
        for issue in issues:
            console.print(f"  [yellow]{issue}[/yellow]")

    console.print()
```

**Step 5: Verify module imports**

Run: `python -c "from nettest.output.terminal import display_terminal; print('OK')"`
Expected: `OK`

**Step 6: Commit**

```bash
git add nettest/output/terminal.py
git commit -m "feat(terminal): add video services display function"
```

---

### Task 7: Add HTML Output Section

**Files:**
- Modify: `nettest/output/html.py`

**Step 1: Add VideoServiceResult import**

Update imports around line 8-12:

```python
from ..models import (
    PingResult, SpeedTestResult, DnsResult,
    MtrResult, DiagnosticResult, ConnectionScore, VoIPQuality, ISPEvidence,
    BufferbloatResult, VideoServiceResult
)
```

**Step 2: Add video_service_results parameter to generate_html**

Update function signature at line 114-128:

```python
def generate_html(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    dns_results: List[DnsResult],
    mtr_results: List[MtrResult],
    expected_speed: float,
    output_dir: str,
    diagnostic: DiagnosticResult,
    thresholds: Dict[str, Any],
    historical_data: Optional[Dict] = None,
    connection_score: Optional[ConnectionScore] = None,
    voip_quality: Optional[VoIPQuality] = None,
    isp_evidence: Optional[ISPEvidence] = None,
    bufferbloat_result: Optional[BufferbloatResult] = None,
    video_service_results: Optional[List[VideoServiceResult]] = None,
) -> str:
```

**Step 3: Build video services section**

Add after line 198 (after bufferbloat_section):

```python
    # Build video services section
    video_services_section = _build_video_services_section(video_service_results)
```

**Step 4: Pass to template**

Update `_generate_html_template` call around line 200-220 to include:

```python
    html = _generate_html_template(
        timestamp=timestamp,
        executive_summary=executive_summary,
        quality_section=quality_section,
        evidence_section=evidence_section,
        bufferbloat_section=bufferbloat_section,
        video_services_section=video_services_section,
        diagnostic_section=diagnostic_section,
        ...
    )
```

**Step 5: Add _build_video_services_section function**

Add after `_build_bufferbloat_section` function (around line 703):

```python
def _build_video_services_section(results: Optional[List[VideoServiceResult]]) -> str:
    """Build video conferencing services section."""
    if not results:
        return ""

    # Build service cards
    cards_html = ""
    for r in results:
        status_colors = {"ready": "var(--good)", "degraded": "var(--warning)", "blocked": "var(--bad)"}
        status_icons = {"ready": "Ready", "degraded": "Degraded", "blocked": "Blocked"}
        status_class = {"ready": "good", "degraded": "warning", "blocked": "bad"}

        color = status_colors.get(r.status, "var(--text-dim)")
        icon = status_icons.get(r.status, r.status)
        css_class = status_class.get(r.status, "")

        stun_text = f"{r.stun_latency_ms:.0f}ms STUN" if r.stun_ok else "STUN blocked"

        cards_html += f"""
            <div class="card" style="border-top: 3px solid {color};">
                <div class="card-title">{r.name}</div>
                <div class="card-value {css_class}">{icon}</div>
                <div class="card-subtitle">{stun_text}</div>
            </div>
        """

    # Build detailed table
    rows_html = ""
    for r in results:
        dns_class = "good" if r.dns_ok else "bad"
        dns_text = f"{r.dns_latency_ms:.0f}ms" if r.dns_ok else "Failed"

        ports_html = ""
        for port, ok in r.tcp_ports.items():
            port_class = "good" if ok else "bad"
            ports_html += f'<span class="{port_class}">{port}</span> '

        stun_class = "good" if r.stun_ok else "bad"
        stun_text = f"{r.stun_latency_ms:.0f}ms" if r.stun_ok else "Failed"

        status_class = {"ready": "good", "degraded": "warning", "blocked": "bad"}.get(r.status, "")
        status_text = {"ready": "Ready", "degraded": "Degraded", "blocked": "Blocked"}.get(r.status, r.status)

        rows_html += f"""
            <tr>
                <td>{r.name}</td>
                <td class="{dns_class}">{dns_text}</td>
                <td>{ports_html}</td>
                <td class="{stun_class}">{stun_text}</td>
                <td class="{status_class}">{status_text}</td>
            </tr>
        """

    # Build issues list
    issues_html = ""
    all_issues = []
    for r in results:
        for issue in r.issues:
            all_issues.append(f"{r.name}: {issue}")

    if all_issues:
        issues_html = "<h4>Issues</h4><ul>"
        for issue in all_issues:
            issues_html += f"<li class='warning'>{issue}</li>"
        issues_html += "</ul>"

    return f"""
        <div class="section">
            <h2>Video Conferencing Services</h2>
            <div class="cards">
                {cards_html}
            </div>
            <details style="margin-top: 1rem;">
                <summary style="cursor: pointer; color: var(--text-dim);">Detailed Results</summary>
                <table style="margin-top: 1rem;">
                    <thead>
                        <tr>
                            <th>Service</th>
                            <th>DNS</th>
                            <th>Ports</th>
                            <th>STUN</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
                {issues_html}
            </details>
        </div>
    """
```

**Step 6: Add section to HTML template**

Update `_generate_html_template` function body around line 1120-1128 to add video services section after bufferbloat:

```python
        {kwargs.get('bufferbloat_section', '')}

        {kwargs.get('video_services_section', '')}

        {kwargs['diagnostic_section']}
```

**Step 7: Verify module imports**

Run: `python -c "from nettest.output.html import generate_html; print('OK')"`
Expected: `OK`

**Step 8: Commit**

```bash
git add nettest/output/html.py
git commit -m "feat(html): add video conferencing services section"
```

---

### Task 8: Update CLI display_terminal Call

**Files:**
- Modify: `nettest/cli.py`

**Step 1: Update display_terminal call**

Update the `display_terminal` call around line 494-505 to pass video_service_results:

```python
            display_terminal(
                ping_results,
                speedtest_result,
                dns_results,
                mtr_results,
                expected_speed,
                diagnostic,
                thresholds,
                console,
                port_results=port_results,
                http_results=http_results,
                video_service_results=video_service_results,
            )
```

**Step 2: Remove duplicate _display_video_services from cli.py**

Remove the `_display_video_services` function added in Task 5 Step 6 and the call added in Task 5 Step 5, since terminal.py now handles this.

**Step 3: Verify full integration**

Run: `python -m nettest.cli --help`
Expected: Help output shows `--video-services` option

**Step 4: Commit**

```bash
git add nettest/cli.py
git commit -m "feat(cli): integrate video services with terminal display"
```

---

### Task 9: End-to-End Test

**Step 1: Run quick test with video services**

Run: `python -m nettest.cli --video-services --profile quick --no-browser`

Expected:
- Shows "Running video service connectivity tests..."
- Displays Video Conferencing Services table
- Shows status for each of the 5 services

**Step 2: Verify HTML output**

Run: `python -m nettest.cli --video-services --profile quick --no-browser 2>&1 | grep -i "HTML report saved"`

Expected: Path to HTML report

**Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: any final integration fixes for video services"
```
