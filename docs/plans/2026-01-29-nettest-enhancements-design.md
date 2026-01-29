# Nettest Enhancement Design

**Date:** 2026-01-29
**Status:** Approved
**Scope:** Bug fixes, new network tests, enhanced visualizations

---

## Overview

Comprehensive enhancement of the nettest tool to include:
- Bug fixes (MTR chart showing only first target)
- New network test categories (quality, infrastructure, real-world, gaming)
- Enhanced HTML report with executive summary, route heatmaps, and ISP evidence section

---

## 1. Bug Fixes & Core Improvements

### 1.1 MTR Chart Bug

**Problem:** In `output/html.py` lines 72-79, only the first target's MTR route is charted:
```python
if mtr_results and mtr_results[0].success:  # Only first!
```

**Solution:** Generate charts for all MTR routes with a tabbed/dropdown selector.

### 1.2 Data Model Enhancements

Add to `MtrHop` in `models.py`:
```python
@dataclass
class MtrHop:
    # existing fields...
    hop_type: str = ""       # "local", "isp", "backbone", "destination"
    as_number: str = ""      # e.g., "AS15169"
    as_name: str = ""        # e.g., "Google LLC"
    latency_delta: float = 0.0  # increase from previous hop
```

---

## 2. New Network Tests

### 2.1 Connection Quality Tests

| Test | Purpose | Implementation |
|------|---------|----------------|
| **Bufferbloat** | Latency under load | Ping during speed test, measure increase |
| **Bandwidth consistency** | Speed stability | Multiple samples over 30s, calculate std dev |
| **Connection stability score** | Overall health 0-100 | Weighted composite of metrics |

**New file:** `tests/bufferbloat.py`
```python
def detect_bufferbloat(
    target: str = "8.8.8.8",
    ping_count: int = 20,
    during_speedtest: bool = True
) -> BufferbloatResult:
    """
    Measures latency before and during bandwidth-intensive activity.
    Bufferbloat grades (based on DSLReports):
    - A: <5ms increase
    - B: 5-30ms increase
    - C: 30-60ms increase
    - D: 60-200ms increase
    - F: >200ms increase
    """
```

**New file:** `tests/stability.py`
```python
def calculate_connection_score(
    ping_results: List[PingResult],
    speedtest: SpeedTestResult,
    expected_speed: float,
    bufferbloat: Optional[BufferbloatResult] = None,
) -> ConnectionScore:
    """
    Calculates overall connection health score 0-100.

    Weights:
    - Speed: 35% (% of expected)
    - Latency: 30% (100 for <20ms, 0 for >200ms)
    - Stability: 35% (jitter, loss, bufferbloat)
    """
```

### 2.2 Real-World Performance Tests

| Test | Purpose | Implementation |
|------|---------|----------------|
| **Website TTFB** | Time to first byte | curl to common sites |
| **Streaming simulation** | Sustained throughput | 10s CDN download |
| **VoIP quality (MOS)** | Call quality 1-5 | ITU-T E-model calculation |

**New file:** `tests/realworld.py`
```python
def measure_website_latency(urls: List[str]) -> List[WebsiteLatency]:
    """Measures TTFB and total load time for each URL."""

def calculate_mos_score(
    latency_ms: float,
    jitter_ms: float,
    packet_loss_pct: float
) -> VoIPQuality:
    """
    Calculates Mean Opinion Score using ITU-T E-model.

    MOS Scale:
    - 4.3-5.0: Excellent (HD voice capable)
    - 4.0-4.3: Good (standard voice)
    - 3.6-4.0: Fair (acceptable)
    - 3.1-3.6: Poor (degraded)
    - 1.0-3.1: Bad (unusable)
    """
```

### 2.3 Infrastructure Diagnostics

| Test | Purpose | Implementation |
|------|---------|----------------|
| **DNS comparison** | Best DNS server | Query same domain against multiple servers |
| **Gateway health** | Router responsiveness | Rapid ping to default gateway |
| **IPv6 readiness** | Dual-stack support | Test IPv6 endpoints |
| **WiFi signal** | Signal strength | Parse iwconfig/nmcli (Linux) |

**New file:** `tests/infrastructure.py`
```python
def compare_dns_servers(
    servers: Dict[str, str],  # {"Google": "8.8.8.8", "Cloudflare": "1.1.1.1"}
    test_domain: str = "google.com",
    queries: int = 5
) -> List[DnsComparisonResult]:
    """Compares DNS response times across servers."""

def check_gateway_health(ping_count: int = 50) -> GatewayHealth:
    """Rapid ping to default gateway to detect micro-drops."""

def check_ipv6_readiness() -> IPv6Result:
    """Tests IPv6 connectivity to known dual-stack endpoints."""

def get_wifi_signal() -> Optional[WiFiSignal]:
    """Returns WiFi signal strength if on wireless (Linux only)."""
```

### 2.4 Gaming/Low-Latency Tests

| Test | Purpose | Implementation |
|------|---------|----------------|
| **Jitter pattern** | Latency variance | 100 rapid pings, analyze distribution |
| **Spike detection** | Latency outliers | Identify >2x average |
| **UDP latency** | Game-like traffic | UDP echo if available |

**New file:** `tests/gaming.py`
```python
def analyze_jitter_pattern(
    target: str,
    sample_count: int = 100,
    interval_ms: int = 50
) -> JitterAnalysis:
    """
    Rapid ping analysis for gaming use cases.

    Returns:
    - Distribution percentiles (p50, p95, p99)
    - Spike count and severity
    - Stability rating for gaming
    """

def detect_latency_spikes(
    ping_results: List[float],
    threshold_multiplier: float = 2.0
) -> List[SpikeEvent]:
    """Identifies latency spikes above threshold."""
```

### 2.5 New File Structure

```
scripts/nettest/tests/
├── ping.py           # existing
├── speedtest.py      # existing
├── dns.py            # existing
├── mtr.py            # existing (+ AS lookup enhancement)
├── tcp.py            # existing
├── http.py           # existing
├── bufferbloat.py    # NEW
├── stability.py      # NEW
├── realworld.py      # NEW
├── infrastructure.py # NEW
├── gaming.py         # NEW
```

---

## 3. New Data Models

Add to `models.py`:

```python
@dataclass
class ConnectionScore:
    overall: int              # 0-100
    grade: str                # A+, A, B+, B, C, D, F
    speed_score: int          # 0-100
    latency_score: int        # 0-100
    stability_score: int      # 0-100
    summary: str              # "Fair - ISP issues detected"

@dataclass
class BufferbloatResult:
    idle_latency_ms: float
    loaded_latency_ms: float
    bloat_ms: float
    bloat_grade: str          # A, B, C, D, F
    success: bool
    error: str = ""

@dataclass
class VoIPQuality:
    mos_score: float          # 1.0-5.0
    r_factor: float           # 0-100
    quality: str              # "Excellent", "Good", "Fair", "Poor", "Bad"
    suitable_for: List[str]   # ["HD Voice", "Video", "Basic calls"]

@dataclass
class WebsiteLatency:
    url: str
    ttfb_ms: float
    total_ms: float
    status_code: int
    success: bool
    error: str = ""

@dataclass
class DnsComparisonResult:
    server_name: str
    server_ip: str
    avg_ms: float
    min_ms: float
    max_ms: float
    success_rate: float

@dataclass
class GatewayHealth:
    gateway_ip: str
    avg_ms: float
    jitter_ms: float
    packet_loss: float
    micro_drops: int          # losses < 1s apart
    health: str               # "Healthy", "Degraded", "Failing"

@dataclass
class IPv6Result:
    supported: bool
    ipv6_address: str
    latency_ms: float
    error: str = ""

@dataclass
class WiFiSignal:
    interface: str
    ssid: str
    signal_dbm: int
    signal_percent: int
    frequency_ghz: float
    channel: int

@dataclass
class JitterAnalysis:
    samples: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    spike_count: int
    spike_severity: str       # "None", "Minor", "Moderate", "Severe"
    gaming_rating: str        # "Excellent", "Good", "Fair", "Poor"

@dataclass
class SpikeEvent:
    timestamp: float
    latency_ms: float
    baseline_ms: float
    multiplier: float
```

---

## 4. HTML Report Visualizations

### 4.1 Executive Summary Section

At top of report - large health score gauge with supporting metrics:

```
┌─────────────────────────────────────────────────────────────┐
│  CONNECTION HEALTH                                          │
│  ┌─────────────┐                                           │
│  │     73      │  Grade: C+                                │
│  │    /100     │  "Fair - ISP issues detected"             │
│  └─────────────┘                                           │
│                                                             │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│  │  75%   │ │  34ms  │ │  10%   │ │  2.1   │ │   B    │   │
│  │ Speed  │ │Latency │ │  Loss  │ │  MOS   │ │Bloat   │   │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘   │
└─────────────────────────────────────────────────────────────┘
```

Implementation: CSS gauge using conic-gradient, metric cards below.

### 4.2 Route Comparison Charts

**Multi-route MTR chart with tabs:**
- Tab for each target (Google DNS | Cloudflare | Teams)
- Line chart showing latency by hop
- Red markers for packet loss
- Tooltip with hop details

**Route health heatmap:**
```
              Hop1  Hop2  Hop3  Hop4  Hop5  Hop6  Hop7
Google DNS    🟢    🟢    🟢    🟢    🟢    🟢    🟢
Cloudflare    🟢    🟢    🟢    🟢    🔴    🟡    🟡
Teams         🟢    🟢    🟢    🟡    🔴    🔴    🟢
```

Implementation: CSS grid with colored cells, Chart.js for line charts.

### 4.3 Technical Deep-Dive Charts

| Chart | Type | Library |
|-------|------|---------|
| Latency distribution | Histogram | Chart.js |
| Jitter timeline | Line | Chart.js |
| Speed over time | Area | Chart.js |
| DNS comparison | Horizontal bar | Chart.js |
| Bufferbloat impact | Grouped bar | Chart.js |

### 4.4 ISP Evidence Section

Dedicated printable section:

```
┌─────────────────────────────────────────────────────────────┐
│ 📋 ISP EVIDENCE REPORT                           [Copy All] │
├─────────────────────────────────────────────────────────────┤
│ Test Date: 2026-01-29 15:57:30                              │
│ Expected Speed: 100 Mbps | Actual: 74.9 Mbps (75%)          │
│                                                             │
│ ISSUES DETECTED:                                            │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ • 50% packet loss at hop 5 (103.77.108.118)            │ │
│ │ • 10% packet loss to Microsoft Teams                    │ │
│ │ • Bufferbloat grade: D (78ms latency increase)         │ │
│ │ • Download speed 25% below plan                        │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ FOR TECHNICAL SUPPORT:                                      │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ "MTR shows 50% packet loss starting at 103.77.108.118  │ │
│ │ (hop 5, your network). Local hops 1-3 show 0% loss.    │ │
│ │ This affects routes to 1.1.1.1 and Microsoft Teams.    │ │
│ │ Can you check interface health on that node?"          │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ FOR NON-TECHNICAL SUPPORT:                                  │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ "My internet is slow and video calls keep freezing.    │ │
│ │ My tests show the problem starts at your equipment,    │ │
│ │ not my router. About half my data packets are lost.    │ │
│ │ Can you check for issues on your network?"             │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Print Report] [Copy Technical] [Copy Simple] [Export PDF]  │
└─────────────────────────────────────────────────────────────┘
```

### 4.5 Monitoring Dashboard Mode

For `--monitor` with HTML output:
- Auto-refresh every interval
- Sparklines for 1-hour history
- Compact card grid
- Alert banners when thresholds exceeded
- Sound notification option

---

## 5. CLI Changes

### 5.1 New Profiles

```bash
# Existing
python3 -m nettest --profile quick       # ping only
python3 -m nettest --profile full        # all current tests

# New profiles
python3 -m nettest --profile quality     # + bufferbloat, stability, MOS
python3 -m nettest --profile infra       # + DNS compare, gateway, IPv6
python3 -m nettest --profile realworld   # + TTFB, streaming
python3 -m nettest --profile gaming      # + jitter analysis, spikes
python3 -m nettest --profile everything  # all tests
```

### 5.2 New Flags

```bash
python3 -m nettest --isp-report          # Generate ISP evidence section
python3 -m nettest --score-only          # Output just health score (for scripts)
python3 -m nettest --no-external         # Skip tests requiring external servers
python3 -m nettest --compare-dns         # Include DNS server comparison
```

### 5.3 Config File Additions

```yaml
# nettest.yml additions
profiles:
  quality:
    description: "Connection quality analysis"
    include_bufferbloat: true
    include_mos: true
    include_stability_score: true

  gaming:
    description: "Gaming/low-latency analysis"
    ping_count: 100
    ping_interval_ms: 50
    include_jitter_analysis: true
    include_spike_detection: true
    thresholds:
      latency:
        good: 20
        warning: 50

scoring:
  weights:
    speed: 0.35
    latency: 0.30
    stability: 0.35

isp_report:
  enabled: true
  include_technical: true
  include_simple: true
```

---

## 6. Implementation Phases

### Phase 1: Bug Fixes + Executive Summary
**Scope:**
- Fix MTR chart to show all routes
- Add route selector/tabs to HTML
- Add executive summary with health score gauge
- Add metric cards (speed, latency, loss, MOS placeholder, bloat placeholder)

**Files changed:**
- `output/html.py` - major updates
- `models.py` - add ConnectionScore
- `tests/stability.py` - new file (scoring only)

**Deliverable:** Working report with health score, all routes charted

---

### Phase 2: Connection Quality Tests
**Scope:**
- Bufferbloat detection
- Bandwidth consistency measurement
- Full stability scoring with all inputs
- VoIP MOS calculation

**Files changed:**
- `tests/bufferbloat.py` - new file
- `tests/stability.py` - enhance with bandwidth consistency
- `tests/realworld.py` - new file (MOS calculation)
- `models.py` - add BufferbloatResult, VoIPQuality
- `cli.py` - add `--profile quality`
- `output/html.py` - add bufferbloat chart

**Deliverable:** `--profile quality` working

---

### Phase 3: Infrastructure Tests
**Scope:**
- DNS server comparison
- Gateway health check
- IPv6 readiness test
- WiFi signal (Linux)

**Files changed:**
- `tests/infrastructure.py` - new file
- `models.py` - add infrastructure dataclasses
- `cli.py` - add `--profile infra`, `--compare-dns`
- `output/html.py` - add DNS comparison chart

**Deliverable:** `--profile infra` working

---

### Phase 4: Real-World Tests
**Scope:**
- Website TTFB measurement
- Streaming simulation

**Files changed:**
- `tests/realworld.py` - add TTFB, streaming
- `models.py` - add WebsiteLatency
- `cli.py` - add `--profile realworld`
- `output/html.py` - add TTFB chart

**Deliverable:** `--profile realworld` working

---

### Phase 5: Gaming Tests + ISP Report
**Scope:**
- Jitter pattern analysis
- Spike detection
- ISP evidence report section
- Copy/print functionality

**Files changed:**
- `tests/gaming.py` - new file
- `models.py` - add JitterAnalysis, SpikeEvent
- `cli.py` - add `--profile gaming`, `--isp-report`
- `output/html.py` - add ISP evidence section, jitter histogram

**Deliverable:** `--profile gaming` and `--isp-report` working

---

### Phase 6: Monitoring Dashboard
**Scope:**
- Enhanced monitor mode HTML
- Auto-refresh
- Sparklines
- Alert banners

**Files changed:**
- `output/html.py` - add dashboard template
- `tui/monitor.py` - HTML output option
- `cli.py` - add `--monitor --format html`

**Deliverable:** Live HTML monitoring dashboard

---

## 7. Testing Strategy

### Unit Tests
- Test each new test module independently
- Mock subprocess calls for ping, mtr, speedtest
- Verify scoring algorithms with known inputs

### Integration Tests
- Run full profiles and verify output structure
- Test HTML generation with all data types
- Verify JSON output includes new fields

### Manual Testing
- Run on real network with known issues
- Verify ISP report text is accurate and helpful
- Test print/copy functionality in browsers

---

## 8. Success Criteria

- [ ] MTR charts show all routes (bug fixed)
- [ ] Health score displays prominently
- [ ] Bufferbloat detected and graded
- [ ] MOS score calculated correctly
- [ ] DNS comparison identifies fastest server
- [ ] ISP evidence section generates useful text
- [ ] All new profiles work without errors
- [ ] HTML report renders correctly in Chrome, Firefox, Safari
- [ ] Print layout is clean and readable

---

## Appendix: MOS Score Calculation

Using simplified ITU-T E-model:

```python
def calculate_mos(latency_ms: float, jitter_ms: float, loss_pct: float) -> float:
    """
    Simplified E-model for MOS calculation.

    R = 93.2 - latency_factor - jitter_factor - loss_factor
    MOS = 1 + 0.035*R + R*(R-60)*(100-R)*7e-6
    """
    # Effective latency (one-way delay + jitter buffer)
    effective_latency = latency_ms + (jitter_ms * 2) + 10  # 10ms codec delay

    # Delay impairment
    if effective_latency < 160:
        delay_factor = effective_latency / 40
    else:
        delay_factor = (effective_latency - 120) / 10

    # Loss impairment (Bpl = 25 for G.711)
    loss_factor = loss_pct * 2.5

    # R-factor
    r_factor = 93.2 - delay_factor - loss_factor
    r_factor = max(0, min(100, r_factor))

    # Convert to MOS
    if r_factor < 0:
        mos = 1.0
    elif r_factor > 100:
        mos = 4.5
    else:
        mos = 1 + 0.035 * r_factor + r_factor * (r_factor - 60) * (100 - r_factor) * 7e-6

    return round(mos, 2)
```

---

## Appendix: Bufferbloat Grades

Based on DSLReports methodology:

| Grade | Latency Increase | Description |
|-------|------------------|-------------|
| A+ | <5ms | Excellent - no bloat |
| A | 5-15ms | Good - minimal bloat |
| B | 15-30ms | Acceptable |
| C | 30-60ms | Moderate bloat |
| D | 60-200ms | Significant bloat |
| F | >200ms | Severe bloat |
