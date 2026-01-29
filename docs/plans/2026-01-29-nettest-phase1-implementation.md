# Nettest Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix MTR chart bug, add route selector for all targets, add executive summary with connection health score gauge.

**Architecture:** Enhance `models.py` with `ConnectionScore` dataclass, refactor `html.py` to generate charts for all MTR routes with a tab selector, add health score calculation in new `tests/stability.py`, update HTML template with executive summary section at top.

**Tech Stack:** Python 3.8+, Chart.js for charts, CSS for gauge styling, dataclasses for models.

---

## Task 1: Add ConnectionScore Model

**Files:**
- Modify: `scripts/nettest/models.py`

**Step 1: Add the ConnectionScore dataclass**

Add after the `DiagnosticResult` class (around line 77):

```python
@dataclass
class ConnectionScore:
    """Overall connection health score."""
    overall: int              # 0-100
    grade: str                # A+, A, B+, B, C, D, F
    speed_score: int          # 0-100
    latency_score: int        # 0-100
    stability_score: int      # 0-100
    summary: str              # "Fair - ISP issues detected"
```

**Step 2: Update __init__.py exports**

Modify `scripts/nettest/__init__.py` to add `ConnectionScore` to `__all__` list and imports.

**Step 3: Commit**

```bash
git add scripts/nettest/models.py scripts/nettest/__init__.py
git commit -m "feat(models): add ConnectionScore dataclass for health scoring"
```

---

## Task 2: Create Stability Module with Scoring

**Files:**
- Create: `scripts/nettest/tests/stability.py`
- Modify: `scripts/nettest/tests/__init__.py`

**Step 1: Create the stability.py file**

```python
"""Connection stability and health scoring."""

from typing import List, Optional
from ..models import PingResult, SpeedTestResult, ConnectionScore


def calculate_connection_score(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    expected_speed: float,
    bufferbloat_ms: float = 0.0,
) -> ConnectionScore:
    """
    Calculate overall connection health score.

    Args:
        ping_results: List of ping test results
        speedtest_result: Speed test result
        expected_speed: Expected download speed in Mbps
        bufferbloat_ms: Latency increase under load (for future use)

    Returns:
        ConnectionScore with overall health assessment
    """
    # Speed score: 0-100 based on % of expected
    if speedtest_result.success and expected_speed > 0:
        speed_pct = (speedtest_result.download_mbps / expected_speed) * 100
        speed_score = min(100, int(speed_pct))
    else:
        speed_score = 0

    # Latency score: 100 for <20ms, 0 for >200ms
    successful_pings = [p for p in ping_results if p.success]
    if successful_pings:
        avg_latency = sum(p.avg_ms for p in successful_pings) / len(successful_pings)
        if avg_latency <= 20:
            latency_score = 100
        elif avg_latency >= 200:
            latency_score = 0
        else:
            latency_score = int(100 - ((avg_latency - 20) / 180) * 100)
    else:
        latency_score = 0

    # Stability score: based on jitter and packet loss
    if successful_pings:
        avg_jitter = sum(p.jitter_ms for p in successful_pings) / len(successful_pings)
        avg_loss = sum(p.packet_loss for p in successful_pings) / len(successful_pings)

        # Jitter penalty: -2 points per ms over 5ms
        jitter_penalty = max(0, (avg_jitter - 5) * 2)

        # Loss penalty: -10 points per % loss
        loss_penalty = avg_loss * 10

        # Bufferbloat penalty (for future)
        bloat_penalty = bufferbloat_ms * 0.2

        stability_score = max(0, int(100 - jitter_penalty - loss_penalty - bloat_penalty))
    else:
        stability_score = 0

    # Weighted overall score
    overall = int(
        speed_score * 0.35 +
        latency_score * 0.30 +
        stability_score * 0.35
    )

    # Calculate grade
    grade = _score_to_grade(overall)

    # Generate summary
    summary = _generate_summary(overall, speed_score, latency_score, stability_score, ping_results)

    return ConnectionScore(
        overall=overall,
        grade=grade,
        speed_score=speed_score,
        latency_score=latency_score,
        stability_score=stability_score,
        summary=summary,
    )


def _score_to_grade(score: int) -> str:
    """Convert numeric score to letter grade."""
    if score >= 95:
        return "A+"
    elif score >= 90:
        return "A"
    elif score >= 85:
        return "B+"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def _generate_summary(
    overall: int,
    speed_score: int,
    latency_score: int,
    stability_score: int,
    ping_results: List[PingResult],
) -> str:
    """Generate human-readable summary of connection health."""
    # Check for packet loss issues
    has_loss = any(p.packet_loss > 0 for p in ping_results if p.success)

    if overall >= 90:
        return "Excellent - Connection is healthy"
    elif overall >= 80:
        if has_loss:
            return "Good - Minor packet loss detected"
        return "Good - Connection is stable"
    elif overall >= 70:
        if speed_score < 70:
            return "Fair - Speed below expected"
        elif stability_score < 70:
            return "Fair - Connection unstable"
        return "Fair - Some issues detected"
    elif overall >= 50:
        if has_loss:
            return "Poor - Significant packet loss"
        elif speed_score < 50:
            return "Poor - Speed well below expected"
        return "Poor - Multiple issues detected"
    else:
        return "Critical - Serious connection problems"
```

**Step 2: Update tests/__init__.py**

Add to `scripts/nettest/tests/__init__.py`:

```python
from .stability import calculate_connection_score
```

And add `calculate_connection_score` to the `__all__` list.

**Step 3: Commit**

```bash
git add scripts/nettest/tests/stability.py scripts/nettest/tests/__init__.py
git commit -m "feat(tests): add connection health scoring in stability module"
```

---

## Task 3: Prepare MTR Data for All Routes

**Files:**
- Modify: `scripts/nettest/output/html.py`

**Step 1: Create helper function for MTR chart data**

Add after the `get_status_class` function (around line 32):

```python
def _prepare_mtr_chart_data(mtr_results: List[MtrResult]) -> Dict[str, Any]:
    """
    Prepare MTR data for all routes for charting.

    Returns dict with:
        - target_names: list of target names
        - routes: list of dicts with labels, latency, loss for each route
    """
    chart_data = {
        "target_names": [],
        "routes": [],
    }

    for mtr in mtr_results:
        if mtr.success and mtr.hops:
            route_data = {
                "name": mtr.target_name,
                "labels": [f"Hop {h.hop_number}" for h in mtr.hops],
                "latency": [h.avg_ms for h in mtr.hops],
                "loss": [h.loss_pct for h in mtr.hops],
                "hosts": [h.host for h in mtr.hops],
            }
            chart_data["target_names"].append(mtr.target_name)
            chart_data["routes"].append(route_data)

    return chart_data
```

**Step 2: Commit**

```bash
git add scripts/nettest/output/html.py
git commit -m "feat(html): add helper to prepare MTR chart data for all routes"
```

---

## Task 4: Update generate_html to Use All MTR Routes

**Files:**
- Modify: `scripts/nettest/output/html.py`

**Step 1: Update the generate_html function**

Replace lines 72-79 (the MTR data preparation) with:

```python
    # MTR data for all targets (not just first)
    mtr_chart_data = _prepare_mtr_chart_data(mtr_results)
    mtr_all_routes_json = json.dumps(mtr_chart_data)
```

**Step 2: Update the _generate_html_template call**

Add `mtr_all_routes_json` to the kwargs passed to `_generate_html_template`, and remove the old `mtr_hops_labels`, `mtr_hops_latency`, `mtr_hops_loss` parameters.

Update the function call (around line 104-121) to:

```python
    html = _generate_html_template(
        timestamp=timestamp,
        diagnostic_section=diagnostic_section,
        speed_section=speed_section,
        latency_rows=latency_rows,
        dns_rows=dns_rows,
        mtr_sections=mtr_sections,
        historical_section=historical_section,
        ping_labels=ping_labels,
        ping_min=ping_min,
        ping_avg=ping_avg,
        ping_max=ping_max,
        ping_jitter=ping_jitter,
        ping_loss=ping_loss,
        mtr_all_routes=mtr_all_routes_json,
    )
```

**Step 3: Commit**

```bash
git add scripts/nettest/output/html.py
git commit -m "refactor(html): pass all MTR routes to template instead of just first"
```

---

## Task 5: Update HTML Template with Route Tabs

**Files:**
- Modify: `scripts/nettest/output/html.py`

**Step 1: Add CSS for tabs**

In the `_generate_html_template` function, add to the style section (after `.export-btn:hover`):

```css
        .tab-container {
            margin-bottom: 1rem;
        }

        .tab-buttons {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }

        .tab-btn {
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.5rem 1rem;
            color: var(--text);
            cursor: pointer;
            font-size: 0.875rem;
            transition: all 0.2s;
        }

        .tab-btn:hover {
            border-color: var(--text-dim);
        }

        .tab-btn.active {
            background: var(--good);
            color: var(--bg);
            border-color: var(--good);
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }
```

**Step 2: Replace the MTR chart section in the template**

Find the section with `Route Latency (First Target)` (around line 728-733) and replace with:

```html
            <div class="section">
                <h2>Route Analysis</h2>
                <div class="tab-container">
                    <div class="tab-buttons" id="mtrTabs"></div>
                    <div id="mtrChartContainer">
                        <div class="chart-container">
                            <canvas id="mtrChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
```

**Step 3: Replace the MTR chart JavaScript**

Replace the MTR Chart JavaScript section (around lines 901-964) with new JavaScript that:
- Reads MTR data from `mtr_all_routes` JSON
- Creates tab buttons dynamically using DOM methods (createElement, appendChild)
- Renders chart for selected route
- Updates on tab click

The JavaScript should use safe DOM methods:
- `document.createElement('button')` for creating tab buttons
- `element.textContent = name` for setting button text (not innerHTML)
- `element.appendChild(btn)` for adding to DOM

**Step 4: Commit**

```bash
git add scripts/nettest/output/html.py
git commit -m "feat(html): add tabbed route selector for MTR charts

Shows all routes instead of just the first target.
Users can click tabs to switch between Google DNS, Cloudflare, Teams, etc."
```

---

## Task 6: Add Route Heatmap

**Files:**
- Modify: `scripts/nettest/output/html.py`

**Step 1: Add helper function for route heatmap**

Add after `_prepare_mtr_chart_data`:

```python
def _build_route_heatmap(mtr_results: List[MtrResult], thresholds: Dict) -> str:
    """Build HTML for route health heatmap grid."""
    if not mtr_results or not any(m.success for m in mtr_results):
        return ""

    # Find max hops across all routes
    max_hops = max(len(m.hops) for m in mtr_results if m.success)

    # Build header row
    header_cells = "<th>Route</th>"
    for i in range(1, max_hops + 1):
        header_cells += f"<th>Hop {i}</th>"

    # Build data rows
    rows = ""
    for mtr in mtr_results:
        if not mtr.success:
            continue

        cells = f"<td><strong>{mtr.target_name}</strong></td>"
        for i in range(max_hops):
            if i < len(mtr.hops):
                hop = mtr.hops[i]
                # Determine color based on packet loss
                if hop.loss_pct == 0:
                    color = "good"
                    symbol = "●"
                elif hop.loss_pct < 10:
                    color = "warning"
                    symbol = "●"
                else:
                    color = "bad"
                    symbol = "●"
                # Use html.escape for any user-provided data
                import html as html_module
                host_escaped = html_module.escape(hop.host)
                title = f"{host_escaped}: {hop.loss_pct:.0f}% loss, {hop.avg_ms:.1f}ms"
                cells += f'<td class="{color}" title="{title}" style="text-align:center;font-size:1.2em;cursor:help;">{symbol}</td>'
            else:
                cells += '<td style="text-align:center;">-</td>'

        rows += f"<tr>{cells}</tr>"

    return f"""
        <div class="section">
            <h2>Route Health Overview</h2>
            <p class="dim">● Green = 0% loss | ● Yellow = &lt;10% loss | ● Red = ≥10% loss (hover for details)</p>
            <table>
                <thead><tr>{header_cells}</tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    """
```

**Step 2: Call the heatmap builder in generate_html**

After `mtr_sections = _build_mtr_sections(...)` (around line 91), add:

```python
    # Build route heatmap
    route_heatmap = _build_route_heatmap(mtr_results, thresholds)
```

**Step 3: Add route_heatmap to template kwargs**

Add `route_heatmap=route_heatmap` to the `_generate_html_template` call.

**Step 4: Insert heatmap in template**

In `_generate_html_template`, add `{kwargs['route_heatmap']}` after the MTR sections and before the charts grid.

**Step 5: Commit**

```bash
git add scripts/nettest/output/html.py
git commit -m "feat(html): add route health heatmap for quick visual comparison

Color-coded grid showing packet loss at each hop across all routes."
```

---

## Task 7: Add Executive Summary with Health Score

**Files:**
- Modify: `scripts/nettest/output/html.py`

**Step 1: Add CSS for gauge and summary cards**

Add to the style section in `_generate_html_template` - CSS for:
- `.executive-summary` container
- `.summary-grid` layout (gauge left, details right)
- `.health-gauge` circular gauge using CSS conic-gradient
- `.gauge-circle`, `.gauge-inner` for the donut effect
- `.gauge-score`, `.gauge-label`, `.gauge-grade` for text
- `.metric-row` and `.metric-pill` for the metric cards

**Step 2: Add helper function to build executive summary**

Add to `html.py`:

```python
def _build_executive_summary(
    connection_score: Optional['ConnectionScore'],
    speedtest_result: SpeedTestResult,
    ping_results: List[PingResult],
    expected_speed: float,
) -> str:
    """Build the executive summary section with health gauge."""
    if connection_score is None:
        return ""

    # Determine gauge color based on score
    if connection_score.overall >= 80:
        gauge_color = "var(--good)"
    elif connection_score.overall >= 60:
        gauge_color = "var(--warning)"
    else:
        gauge_color = "var(--bad)"

    # Calculate metrics for pills
    speed_pct = int((speedtest_result.download_mbps / expected_speed) * 100) if expected_speed > 0 and speedtest_result.success else 0

    avg_latency = 0
    avg_loss = 0
    successful_pings = [p for p in ping_results if p.success]
    if successful_pings:
        avg_latency = sum(p.avg_ms for p in successful_pings) / len(successful_pings)
        avg_loss = sum(p.packet_loss for p in successful_pings) / len(successful_pings)

    # Determine color classes for metrics
    speed_class = "good" if speed_pct >= 80 else ("warning" if speed_pct >= 50 else "bad")
    latency_class = "good" if avg_latency < 50 else ("warning" if avg_latency < 100 else "bad")
    loss_class = "good" if avg_loss == 0 else ("warning" if avg_loss < 5 else "bad")

    # Return HTML with gauge and metric pills
    # (full HTML template with proper escaping)
```

**Step 3: Update generate_html signature and call**

Add `connection_score: Optional[ConnectionScore] = None` parameter to `generate_html()`.

Add import at top of file:
```python
from ..models import (
    PingResult, SpeedTestResult, DnsResult,
    MtrResult, DiagnosticResult, ConnectionScore
)
```

Build executive summary in `generate_html`:
```python
    # Build executive summary
    executive_summary = _build_executive_summary(
        connection_score, speedtest_result, ping_results, expected_speed
    )
```

Add to template kwargs: `executive_summary=executive_summary`

**Step 4: Insert executive summary in template**

In `_generate_html_template`, add `{kwargs.get('executive_summary', '')}` right after the header div and before the diagnostic section.

**Step 5: Commit**

```bash
git add scripts/nettest/output/html.py
git commit -m "feat(html): add executive summary with health score gauge

Large circular gauge showing 0-100 health score with letter grade.
Metric pills below showing speed%, latency, loss, and component scores."
```

---

## Task 8: Integrate Health Score in CLI

**Files:**
- Modify: `scripts/nettest/cli.py`

**Step 1: Import the scoring function**

Add to imports:
```python
from .tests import calculate_connection_score
from .models import ConnectionScore
```

**Step 2: Calculate score before generating HTML**

In the `main()` function, after running diagnostics and before generating HTML (around line 418-425), add:

```python
    # Calculate connection health score
    connection_score = calculate_connection_score(
        ping_results=ping_results,
        speedtest_result=speedtest_result,
        expected_speed=expected_speed,
    )
```

**Step 3: Pass score to generate_html**

Update the `generate_html` call to include `connection_score=connection_score`.

**Step 4: Commit**

```bash
git add scripts/nettest/cli.py
git commit -m "feat(cli): integrate connection health scoring into report generation"
```

---

## Task 9: Test the Full Implementation

**Step 1: Run a full test**

```bash
cd /mnt/local_disk_g/docker/scripts
python3 -m nettest --profile full --no-browser
```

**Step 2: Verify the HTML report**

Open the generated HTML file and verify:
- [ ] Executive summary with gauge appears at top
- [ ] Health score displays correctly
- [ ] Route tabs appear and switch between routes
- [ ] All MTR routes are chartable
- [ ] Route heatmap shows color-coded loss
- [ ] No JavaScript errors in browser console

**Step 3: Test with different scenarios**

```bash
# Quick test (no speedtest)
python3 -m nettest --profile quick --no-browser

# Verify gauge still works without speed data
```

**Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address any issues found during testing"
```

---

## Task 10: Push All Changes

**Step 1: Review commits**

```bash
git log --oneline -10
```

**Step 2: Push to remote**

```bash
git push
```

---

## Summary of Files Changed

| File | Action | Description |
|------|--------|-------------|
| `models.py` | Modify | Add ConnectionScore dataclass |
| `__init__.py` | Modify | Export ConnectionScore |
| `tests/stability.py` | Create | Health scoring algorithm |
| `tests/__init__.py` | Modify | Export calculate_connection_score |
| `output/html.py` | Modify | MTR tabs, heatmap, executive summary |
| `cli.py` | Modify | Integrate scoring |

## Expected Outcome

After completing all tasks:
1. HTML report shows health score gauge (0-100) prominently at top
2. Tabbed interface allows switching between all MTR routes
3. Route heatmap provides quick visual comparison of packet loss
4. Cloudflare and Teams routes with packet loss are now visible in charts
5. All existing functionality continues to work
