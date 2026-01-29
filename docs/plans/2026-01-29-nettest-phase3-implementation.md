# Nettest Phase 3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ISP evidence documentation, CSV export, and integrate bufferbloat testing for complete network diagnostics.

**Architecture:** Create `ISPEvidence` model, add evidence generator, CSV exporter, wire bufferbloat into test runner, update HTML with evidence section.

**Tech Stack:** Python 3.8+, dataclasses, CSV module.

---

## Task 1: Add ISP Evidence Data Model

**Files:** `scripts/nettest/models.py`, `scripts/nettest/__init__.py`

Add after VoIPQuality:

```python
@dataclass
class ISPEvidence:
    """Documentation-ready evidence for ISP complaints."""
    timestamp: str = ""
    summary: str = ""
    speed_complaint: str = ""  # "Download 53 Mbps vs 100 Mbps expected (47% deficit)"
    packet_loss_complaint: str = ""  # "10% packet loss to Cloudflare DNS"
    latency_complaint: str = ""  # "Average latency 115ms (expected <50ms)"
    problem_hops: List[str] = field(default_factory=list)  # ["Hop 5: 103.77.108.118 - 90% loss"]
    recommendations: List[str] = field(default_factory=list)
```

Export in `__init__.py`.

**Commit:** `feat(models): add ISPEvidence dataclass for complaint documentation`

---

## Task 2: Create ISP Evidence Generator

**File:** `scripts/nettest/output/evidence.py` (new)

```python
"""Generate ISP complaint evidence."""

from datetime import datetime
from typing import List, Optional
from ..models import (
    PingResult, SpeedTestResult, MtrResult,
    DiagnosticResult, ISPEvidence
)


def generate_isp_evidence(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    mtr_results: List[MtrResult],
    diagnostic: DiagnosticResult,
    expected_speed: float,
) -> ISPEvidence:
    """Generate documentation-ready evidence for ISP complaints."""
    evidence = ISPEvidence(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    complaints = []

    # Speed complaint
    if speedtest_result.success and expected_speed > 0:
        pct = (speedtest_result.download_mbps / expected_speed) * 100
        if pct < 80:
            deficit = 100 - pct
            evidence.speed_complaint = (
                f"Download speed {speedtest_result.download_mbps:.1f} Mbps vs "
                f"{expected_speed:.0f} Mbps expected ({deficit:.0f}% deficit)"
            )
            complaints.append(f"Speed: {evidence.speed_complaint}")

    # Packet loss complaint
    loss_targets = []
    for pr in ping_results:
        if pr.success and pr.packet_loss > 0:
            loss_targets.append(f"{pr.packet_loss:.0f}% loss to {pr.target_name}")
    if loss_targets:
        evidence.packet_loss_complaint = "; ".join(loss_targets)
        complaints.append(f"Packet Loss: {evidence.packet_loss_complaint}")

    # Latency complaint
    high_latency = []
    for pr in ping_results:
        if pr.success and pr.avg_ms > 100:
            high_latency.append(f"{pr.target_name}: {pr.avg_ms:.0f}ms")
    if high_latency:
        evidence.latency_complaint = "; ".join(high_latency)
        complaints.append(f"High Latency: {evidence.latency_complaint}")

    # Problem hops from MTR
    for mtr in mtr_results:
        if mtr.success:
            for hop in mtr.hops:
                if hop.loss_pct >= 10 and hop.host != "???":
                    evidence.problem_hops.append(
                        f"{mtr.target_name} Hop {hop.hop_number}: {hop.host} - "
                        f"{hop.loss_pct:.0f}% loss, {hop.avg_ms:.0f}ms avg"
                    )

    # Summary
    if complaints:
        evidence.summary = f"Network issues detected: {'; '.join(complaints)}"
    else:
        evidence.summary = "No significant issues detected"

    # Copy recommendations from diagnostic
    evidence.recommendations = diagnostic.recommendations.copy()

    return evidence
```

Update `output/__init__.py` to export `generate_isp_evidence`.

**Commit:** `feat(output): add ISP evidence generator for complaint documentation`

---

## Task 3: Add CSV Export Function

**File:** `scripts/nettest/output/csv_export.py` (new)

```python
"""CSV export for network test results."""

import csv
import os
from datetime import datetime
from typing import List, Optional
from ..models import PingResult, SpeedTestResult, MtrResult, DnsResult


def export_csv(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    dns_results: List[DnsResult],
    mtr_results: List[MtrResult],
    output_dir: str,
) -> str:
    """
    Export results to CSV files.

    Creates three files:
    - nettest_ping_TIMESTAMP.csv
    - nettest_speed_TIMESTAMP.csv
    - nettest_mtr_TIMESTAMP.csv

    Returns the directory path.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Ping results
    ping_file = os.path.join(output_dir, f"nettest_ping_{timestamp}.csv")
    with open(ping_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Target", "Min (ms)", "Avg (ms)", "Max (ms)", "Jitter (ms)", "Loss (%)", "Success"])
        for pr in ping_results:
            writer.writerow([
                pr.target_name, pr.min_ms, pr.avg_ms, pr.max_ms,
                pr.jitter_ms, pr.packet_loss, pr.success
            ])

    # Speed test
    speed_file = os.path.join(output_dir, f"nettest_speed_{timestamp}.csv")
    with open(speed_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Download (Mbps)", "Upload (Mbps)", "Ping (ms)", "Server", "Success"])
        writer.writerow([
            speedtest_result.download_mbps, speedtest_result.upload_mbps,
            speedtest_result.ping_ms, speedtest_result.server, speedtest_result.success
        ])

    # MTR results
    mtr_file = os.path.join(output_dir, f"nettest_mtr_{timestamp}.csv")
    with open(mtr_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Target", "Hop", "Host", "Loss (%)", "Avg (ms)", "Best (ms)", "Worst (ms)"])
        for mtr in mtr_results:
            if mtr.success:
                for hop in mtr.hops:
                    writer.writerow([
                        mtr.target_name, hop.hop_number, hop.host,
                        hop.loss_pct, hop.avg_ms, hop.best_ms, hop.worst_ms
                    ])

    return output_dir
```

Update `output/__init__.py` to export `export_csv`.

**Commit:** `feat(output): add CSV export for test results`

---

## Task 4: Add ISP Evidence Section to HTML

**File:** `scripts/nettest/output/html.py`

1. Update imports to include `ISPEvidence`

2. Update `generate_html()` signature to accept `isp_evidence: Optional[ISPEvidence] = None`

3. Add helper function `_build_evidence_section()`:

```python
def _build_evidence_section(evidence: Optional[ISPEvidence]) -> str:
    """Build ISP complaint evidence section."""
    if evidence is None:
        return ""

    # Only show if there are actual complaints
    has_issues = (
        evidence.speed_complaint or
        evidence.packet_loss_complaint or
        evidence.latency_complaint or
        evidence.problem_hops
    )

    if not has_issues:
        return ""

    complaints_html = ""
    if evidence.speed_complaint:
        complaints_html += f'<li class="bad">{evidence.speed_complaint}</li>'
    if evidence.packet_loss_complaint:
        complaints_html += f'<li class="bad">{evidence.packet_loss_complaint}</li>'
    if evidence.latency_complaint:
        complaints_html += f'<li class="warning">{evidence.latency_complaint}</li>'

    hops_html = ""
    if evidence.problem_hops:
        hops_html = "<h4>Problem Hops (for ISP reference)</h4><ul>"
        for hop in evidence.problem_hops:
            hops_html += f"<li><code>{hop}</code></li>"
        hops_html += "</ul>"

    return f"""
        <div class="section" style="border-left: 4px solid var(--bad);">
            <h2>ISP Complaint Evidence</h2>
            <p class="dim">Generated: {evidence.timestamp}</p>
            <p><strong>{evidence.summary}</strong></p>
            <h4>Issues Documented</h4>
            <ul>{complaints_html}</ul>
            {hops_html}
            <div class="export-buttons" style="margin-top: 1rem;">
                <button class="export-btn" onclick="copyEvidence()">Copy Evidence Text</button>
            </div>
        </div>
    """
```

4. Call and pass to template after quality_section

5. Add JavaScript function in template for copying evidence:

```javascript
function copyEvidence() {
    const evidence = `Network Test Evidence - TIMESTAMP

Issues:
- SPEED_COMPLAINT
- LOSS_COMPLAINT
- LATENCY_COMPLAINT

Problem Hops:
HOPS_LIST

Generated by nettest`;
    navigator.clipboard.writeText(evidence).then(() => alert('Evidence copied!'));
}
```

**Commit:** `feat(html): add ISP complaint evidence section with copy button`

---

## Task 5: Integrate Bufferbloat into CLI

**File:** `scripts/nettest/cli.py`

1. Import `detect_bufferbloat` from tests

2. Add CLI argument:
```python
parser.add_argument(
    "--bufferbloat",
    action="store_true",
    help="Run bufferbloat detection test"
)
```

3. In main test flow, after speed test, if `--bufferbloat` flag:
```python
bufferbloat_result = None
if args.bufferbloat:
    console.print("[dim]Running bufferbloat test...[/dim]")
    bufferbloat_result = detect_bufferbloat(interface=args.interface)
    if bufferbloat_result.success:
        console.print(f"Bufferbloat: Grade {bufferbloat_result.bloat_grade} ({bufferbloat_result.idle_latency_ms:.1f}ms baseline)")
```

**Commit:** `feat(cli): add --bufferbloat flag for bufferbloat detection`

---

## Task 6: Add Export CLI Options

**File:** `scripts/nettest/cli.py`

1. Add CLI argument:
```python
parser.add_argument(
    "--export-csv",
    action="store_true",
    help="Export results to CSV files"
)
```

2. After HTML generation, if `--export-csv`:
```python
if args.export_csv:
    csv_dir = export_csv(
        ping_results, speedtest_result, dns_results, mtr_results,
        output_dir=output_dir
    )
    console.print(f"[green]CSV files saved to: {csv_dir}[/green]")
```

3. Import `export_csv` and `generate_isp_evidence` from output module

4. Generate ISP evidence and pass to `generate_html()`:
```python
isp_evidence = generate_isp_evidence(
    ping_results, speedtest_result, mtr_results, diagnostic, expected_speed
)
```

**Commit:** `feat(cli): add --export-csv flag and ISP evidence generation`

---

## Task 7: Test and Push

Run `python3 -m nettest --profile full --export-csv --no-browser`

Verify:
- ISP Evidence section appears in HTML when issues exist
- CSV files are created
- Copy evidence button works

Fix any issues, then push all changes.

**Commit:** Any fixes needed.
