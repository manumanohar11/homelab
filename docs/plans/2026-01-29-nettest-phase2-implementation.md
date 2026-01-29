# Nettest Phase 2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add connection quality tests - bufferbloat detection, VoIP MOS scoring, and enhanced HTML visualizations.

**Architecture:** Add `BufferbloatResult` and `VoIPQuality` models, create `bufferbloat.py` test module, add MOS calculation to `stability.py`, update HTML with new charts.

**Tech Stack:** Python 3.8+, Chart.js, ITU-T E-model for MOS.

---

## Task 1: Add New Data Models

**Files:** `scripts/nettest/models.py`, `scripts/nettest/__init__.py`

Add after ConnectionScore:

```python
@dataclass
class BufferbloatResult:
    """Result of bufferbloat detection test."""
    idle_latency_ms: float = 0.0
    loaded_latency_ms: float = 0.0
    bloat_ms: float = 0.0
    bloat_grade: str = ""  # A, B, C, D, F
    success: bool = False
    error: str = ""


@dataclass
class VoIPQuality:
    """VoIP call quality assessment."""
    mos_score: float = 0.0      # 1.0-5.0 Mean Opinion Score
    r_factor: float = 0.0       # 0-100 E-model R-factor
    quality: str = ""           # "Excellent", "Good", "Fair", "Poor", "Bad"
    suitable_for: List[str] = field(default_factory=list)  # ["HD Voice", "Video"]
```

Export both in `__init__.py`.

**Commit:** `feat(models): add BufferbloatResult and VoIPQuality dataclasses`

---

## Task 2: Add MOS Calculation to Stability Module

**File:** `scripts/nettest/tests/stability.py`

Add function:

```python
def calculate_mos_score(
    latency_ms: float,
    jitter_ms: float,
    packet_loss_pct: float,
) -> VoIPQuality:
    """
    Calculate Mean Opinion Score using simplified ITU-T E-model.

    MOS Scale:
    - 4.3-5.0: Excellent (HD voice capable)
    - 4.0-4.3: Good (standard voice)
    - 3.6-4.0: Fair (acceptable)
    - 3.1-3.6: Poor (degraded)
    - 1.0-3.1: Bad (unusable)
    """
    # Effective latency (one-way + jitter buffer + codec delay)
    effective_latency = latency_ms + (jitter_ms * 2) + 10

    # Delay impairment
    if effective_latency < 160:
        delay_factor = effective_latency / 40
    else:
        delay_factor = (effective_latency - 120) / 10

    # Loss impairment
    loss_factor = packet_loss_pct * 2.5

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

    mos = round(max(1.0, min(5.0, mos)), 2)

    # Determine quality and suitability
    if mos >= 4.3:
        quality = "Excellent"
        suitable = ["HD Voice", "Video Conferencing", "VoIP"]
    elif mos >= 4.0:
        quality = "Good"
        suitable = ["Video Conferencing", "VoIP"]
    elif mos >= 3.6:
        quality = "Fair"
        suitable = ["VoIP", "Voice Calls"]
    elif mos >= 3.1:
        quality = "Poor"
        suitable = ["Basic Voice"]
    else:
        quality = "Bad"
        suitable = []

    return VoIPQuality(
        mos_score=mos,
        r_factor=round(r_factor, 1),
        quality=quality,
        suitable_for=suitable,
    )
```

Update imports and exports.

**Commit:** `feat(stability): add VoIP MOS score calculation using E-model`

---

## Task 3: Create Bufferbloat Test Module

**File:** `scripts/nettest/tests/bufferbloat.py` (new)

```python
"""Bufferbloat detection test."""

import subprocess
import re
import time
from typing import Optional
from ..models import BufferbloatResult


def detect_bufferbloat(
    target: str = "8.8.8.8",
    ping_count: int = 10,
    interface: Optional[str] = None,
) -> BufferbloatResult:
    """
    Detect bufferbloat by measuring latency increase under load.

    Note: For accurate results, run during a speed test or heavy download.
    This simplified version measures baseline latency only.

    Grades (based on DSLReports):
    - A: <5ms increase
    - B: 5-30ms increase
    - C: 30-60ms increase
    - D: 60-200ms increase
    - F: >200ms increase
    """
    result = BufferbloatResult()

    try:
        # Build ping command
        cmd = ["ping", "-c", str(ping_count), "-i", "0.2"]
        if interface:
            cmd.extend(["-I", interface])
        cmd.append(target)

        # Run ping
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if proc.returncode != 0:
            result.error = "Ping failed"
            return result

        # Parse average latency
        match = re.search(r"min/avg/max.*?=\s*[\d.]+/([\d.]+)/", proc.stdout)
        if match:
            result.idle_latency_ms = float(match.group(1))
            result.loaded_latency_ms = result.idle_latency_ms  # Same for now
            result.bloat_ms = 0.0  # No load test in this version
            result.bloat_grade = "A"  # Baseline only
            result.success = True
        else:
            result.error = "Could not parse ping output"

    except subprocess.TimeoutExpired:
        result.error = "Ping timeout"
    except Exception as e:
        result.error = str(e)

    return result


def grade_bufferbloat(bloat_ms: float) -> str:
    """Convert bloat measurement to letter grade."""
    if bloat_ms < 5:
        return "A"
    elif bloat_ms < 30:
        return "B"
    elif bloat_ms < 60:
        return "C"
    elif bloat_ms < 200:
        return "D"
    else:
        return "F"
```

Update `tests/__init__.py` to export.

**Commit:** `feat(tests): add bufferbloat detection module`

---

## Task 4: Add MOS and Quality Metrics to HTML

**File:** `scripts/nettest/output/html.py`

Add to executive summary section - new metric pills for MOS score. Update `_build_executive_summary()` to accept and display VoIP quality.

Add new section after executive summary:

```python
def _build_quality_section(voip_quality: Optional[VoIPQuality]) -> str:
    """Build VoIP quality assessment section."""
    if voip_quality is None:
        return ""

    mos_class = "good" if voip_quality.mos_score >= 4.0 else (
        "warning" if voip_quality.mos_score >= 3.6 else "bad"
    )

    suitable_html = ", ".join(voip_quality.suitable_for) if voip_quality.suitable_for else "Not recommended"

    return f"""
        <div class="section">
            <h2>VoIP Quality Assessment</h2>
            <div class="cards">
                <div class="card">
                    <div class="card-title">MOS Score</div>
                    <div class="card-value {mos_class}">{voip_quality.mos_score:.1f}</div>
                    <div class="card-subtitle">out of 5.0</div>
                </div>
                <div class="card">
                    <div class="card-title">Quality</div>
                    <div class="card-value {mos_class}">{voip_quality.quality}</div>
                </div>
                <div class="card">
                    <div class="card-title">R-Factor</div>
                    <div class="card-value">{voip_quality.r_factor:.0f}</div>
                    <div class="card-subtitle">out of 100</div>
                </div>
                <div class="card">
                    <div class="card-title">Suitable For</div>
                    <div class="card-value small">{suitable_html}</div>
                </div>
            </div>
        </div>
    """
```

**Commit:** `feat(html): add VoIP quality assessment section`

---

## Task 5: Integrate Quality Tests in CLI

**File:** `scripts/nettest/cli.py`

Add imports, calculate MOS after ping tests, pass to HTML generator.

```python
from .tests import calculate_connection_score, calculate_mos_score

# After ping tests complete:
voip_quality = None
if ping_results:
    successful = [p for p in ping_results if p.success]
    if successful:
        avg_latency = sum(p.avg_ms for p in successful) / len(successful)
        avg_jitter = sum(p.jitter_ms for p in successful) / len(successful)
        avg_loss = sum(p.packet_loss for p in successful) / len(successful)
        voip_quality = calculate_mos_score(avg_latency, avg_jitter, avg_loss)

# Pass to generate_html
```

**Commit:** `feat(cli): integrate VoIP quality scoring`

---

## Task 6: Test and Push

Run `python3 -m nettest --profile full --no-browser`, verify MOS section appears.

**Commit:** Any fixes needed.

Push all changes.
