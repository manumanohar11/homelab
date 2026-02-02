# Video Conferencing Services Testing Design

## Overview

Extend nettest to support dedicated testing for video conferencing services: Microsoft Teams, Zoom, WhatsApp, Google Meet, and Webex. Tests include DNS resolution, TCP port connectivity, and STUN binding checks.

## Services & Endpoints

| Service | Primary Domain | TCP Ports | STUN Server |
|---------|---------------|-----------|-------------|
| Microsoft Teams | teams.microsoft.com | 443, 3478 | stun.teams.microsoft.com:3478 |
| Zoom | zoom.us | 443, 8801, 8802 | stun.zoom.us:3478 |
| WhatsApp | web.whatsapp.com | 443, 5222 | stun.whatsapp.net:3478 |
| Google Meet | meet.google.com | 443, 19302 | stun.l.google.com:19302 |
| Webex | webex.com | 443, 5004 | stun.webex.com:3478 |

## Test Sequence

Per service:
1. DNS resolution of primary domain
2. TCP connectivity to required ports
3. STUN binding request to verify UDP relay capability

## Status Determination

- **Ready** - All checks pass
- **Degraded** - DNS/443 works but some ports blocked (will work but may have quality issues)
- **Blocked** - DNS fails or port 443 unreachable

## Data Model

```python
@dataclass
class VideoServiceResult:
    name: str                    # "Zoom", "WhatsApp", etc.
    dns_ok: bool                 # Could resolve primary domain
    dns_latency_ms: float        # DNS resolution time
    tcp_ports: dict[int, bool]   # {443: True, 8801: False, ...}
    stun_ok: bool                # STUN binding succeeded
    stun_latency_ms: Optional[float]  # RTT to STUN server
    status: str                  # "ready", "degraded", "blocked"
    issues: list[str]            # ["Port 8801 blocked", ...]
```

## CLI Interface

- Flag: `--video-services` / `-vs`
- Opt-in only (not run by default)
- Can combine with other flags: `nettest -vs --no-speedtest --json`

## HTML Output

Dedicated "Video Conferencing Services" section after Speed Test:
- Card grid showing each service with status icon and STUN latency
- Expandable detailed table with DNS, ports, STUN columns
- Color coding: green=ready, yellow=degraded, red=blocked

## CLI Output

Rich table with columns: Service, DNS, Ports, STUN, Status
- Issues summary below table for degraded/blocked services
- Only displayed when `-vs` flag is used

## Files to Create

| File | Purpose |
|------|---------|
| `nettest/tests/video_services.py` | STUN check + video service test logic |

## Files to Modify

| File | Changes |
|------|---------|
| `nettest/models.py` | Add `VideoServiceResult` dataclass |
| `nettest/config.py` | Add `VIDEO_SERVICES` configuration dict |
| `nettest/cli.py` | Add `-vs`/`--video-services` flag, call tests, display results |
| `nettest/tests/runner.py` | Integrate video service tests into test orchestration |
| `nettest/output/html.py` | Add `_build_video_services_section()` function |
| `nettest/output/terminal.py` | Add `_display_video_services()` function |

## Dependencies

No new external packages - STUN implemented with standard library UDP sockets.
