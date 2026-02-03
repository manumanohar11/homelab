"""HTML report generator with charts and styling."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from ..models import (
    PingResult, SpeedTestResult, DnsResult,
    MtrResult, DiagnosticResult, ConnectionScore, VoIPQuality, ISPEvidence,
    BufferbloatResult, VideoServiceResult
)


def get_status_class(value: float, metric: str, thresholds: Dict, reverse: bool = False) -> str:
    """Get CSS class based on threshold."""
    metric_thresholds = thresholds.get(metric, {"good": 50, "warning": 100})

    if reverse:
        if value >= metric_thresholds["good"]:
            return "good"
        elif value >= metric_thresholds["warning"]:
            return "warning"
        else:
            return "bad"
    else:
        if value <= metric_thresholds["good"]:
            return "good"
        elif value <= metric_thresholds["warning"]:
            return "warning"
        else:
            return "bad"


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


def _build_route_heatmap(mtr_results: List[MtrResult], thresholds: Dict) -> str:
    """Build HTML for route health heatmap grid."""
    import html as html_module

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

        cells = f"<td><strong>{html_module.escape(mtr.target_name)}</strong></td>"
        for i in range(max_hops):
            if i < len(mtr.hops):
                hop = mtr.hops[i]
                if hop.loss_pct == 0:
                    color = "good"
                elif hop.loss_pct < 10:
                    color = "warning"
                else:
                    color = "bad"
                host_escaped = html_module.escape(hop.host)
                title = f"{host_escaped}: {hop.loss_pct:.0f}% loss, {hop.avg_ms:.1f}ms"
                cells += f'<td class="{color}" title="{title}" style="text-align:center;font-size:1.2em;cursor:help;">●</td>'
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
    """
    Generate HTML report with charts.

    Args:
        ping_results: Ping test results
        speedtest_result: Speed test result
        dns_results: DNS test results
        mtr_results: MTR results
        expected_speed: Expected download speed in Mbps
        output_dir: Directory to save HTML file
        diagnostic: Diagnostic analysis result
        thresholds: Threshold configuration
        historical_data: Previous test results for comparison (optional)

    Returns:
        Path to generated HTML file
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Prepare data for charts
    ping_labels = json.dumps([pr.target_name for pr in ping_results if pr.success])
    ping_avg = json.dumps([pr.avg_ms for pr in ping_results if pr.success])
    ping_min = json.dumps([pr.min_ms for pr in ping_results if pr.success])
    ping_max = json.dumps([pr.max_ms for pr in ping_results if pr.success])
    ping_jitter = json.dumps([pr.jitter_ms for pr in ping_results if pr.success])
    ping_loss = json.dumps([pr.packet_loss for pr in ping_results if pr.success])

    # MTR data for all targets (not just first)
    mtr_chart_data = _prepare_mtr_chart_data(mtr_results)
    mtr_all_routes_json = json.dumps(mtr_chart_data)

    # Calculate download percentage
    dl_pct = (speedtest_result.download_mbps / expected_speed) * 100 if expected_speed > 0 and speedtest_result.success else 0

    # Build latency table rows
    latency_rows = _build_latency_rows(ping_results, thresholds)

    # Build DNS table rows
    dns_rows = _build_dns_rows(dns_results, thresholds)

    # Build MTR sections
    mtr_sections = _build_mtr_sections(mtr_results, thresholds)

    # Build route heatmap
    route_heatmap = _build_route_heatmap(mtr_results, thresholds)

    # Build diagnostic section
    diagnostic_section = _build_diagnostic_section(diagnostic)

    # Build speed test section
    speed_section = _build_speed_section(speedtest_result, expected_speed, dl_pct, thresholds)

    # Build historical comparison if available
    historical_section = ""
    if historical_data:
        historical_section = _build_historical_section(ping_results, speedtest_result, historical_data)

    # Build executive summary
    executive_summary = _build_executive_summary(
        connection_score, speedtest_result, ping_results, expected_speed
    )

    # Build VoIP quality section
    quality_section = _build_quality_section(voip_quality)

    # Build ISP evidence section
    evidence_section = _build_evidence_section(isp_evidence)

    # Build bufferbloat section
    bufferbloat_section = _build_bufferbloat_section(bufferbloat_result)

    # Build video services section
    video_services_section = _build_video_services_section(video_service_results)

    html = _generate_html_template(
        timestamp=timestamp,
        executive_summary=executive_summary,
        quality_section=quality_section,
        evidence_section=evidence_section,
        bufferbloat_section=bufferbloat_section,
        video_services_section=video_services_section,
        diagnostic_section=diagnostic_section,
        speed_section=speed_section,
        latency_rows=latency_rows,
        dns_rows=dns_rows,
        mtr_sections=mtr_sections,
        route_heatmap=route_heatmap,
        historical_section=historical_section,
        ping_labels=ping_labels,
        ping_min=ping_min,
        ping_avg=ping_avg,
        ping_max=ping_max,
        ping_jitter=ping_jitter,
        ping_loss=ping_loss,
        mtr_all_routes=mtr_all_routes_json,
    )

    # Write HTML file
    os.makedirs(output_dir, exist_ok=True)
    filename = f"nettest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w') as f:
        f.write(html)

    return filepath


def _build_latency_rows(ping_results: List[PingResult], thresholds: Dict) -> str:
    """Build HTML rows for latency table."""
    rows = ""
    for pr in ping_results:
        if pr.success:
            avg_class = get_status_class(pr.avg_ms, "latency", thresholds)
            jitter_class = get_status_class(pr.jitter_ms, "jitter", thresholds)
            loss_class = get_status_class(pr.packet_loss, "packet_loss", thresholds)
            rows += f"""
                <tr>
                    <td>{pr.target_name}</td>
                    <td>{pr.min_ms:.1f} ms</td>
                    <td class="{avg_class}">{pr.avg_ms:.1f} ms</td>
                    <td>{pr.max_ms:.1f} ms</td>
                    <td class="{jitter_class}">{pr.jitter_ms:.1f} ms</td>
                    <td class="{loss_class}">{pr.packet_loss:.1f}%</td>
                </tr>
            """
        else:
            rows += f"""
                <tr>
                    <td>{pr.target_name}</td>
                    <td colspan="5" class="bad">Error: {pr.error}</td>
                </tr>
            """
    return rows


def _build_dns_rows(dns_results: List[DnsResult], thresholds: Dict) -> str:
    """Build HTML rows for DNS table."""
    rows = ""
    for dr in dns_results:
        if dr.success:
            time_class = get_status_class(dr.resolution_time_ms, "latency", thresholds) if dr.resolution_time_ms > 0 else ""
            time_str = f"{dr.resolution_time_ms:.0f} ms" if dr.resolution_time_ms > 0 else "N/A (IP)"
            rows += f"""
                <tr>
                    <td>{dr.target}</td>
                    <td>{dr.resolved_ip or '-'}</td>
                    <td class="{time_class}">{time_str}</td>
                </tr>
            """
        else:
            rows += f"""
                <tr>
                    <td>{dr.target}</td>
                    <td colspan="2" class="bad">{dr.error}</td>
                </tr>
            """
    return rows


def _build_mtr_sections(mtr_results: List[MtrResult], thresholds: Dict) -> str:
    """Build HTML sections for MTR results."""
    sections = ""
    for mtr in mtr_results:
        if mtr.success and mtr.hops:
            hop_rows = ""
            for hop in mtr.hops:
                loss_class = get_status_class(hop.loss_pct, "packet_loss", thresholds)
                avg_class = get_status_class(hop.avg_ms, "latency", thresholds)
                hop_rows += f"""
                    <tr>
                        <td>{hop.hop_number}</td>
                        <td>{hop.host}</td>
                        <td class="{loss_class}">{hop.loss_pct:.1f}%</td>
                        <td class="{avg_class}">{hop.avg_ms:.1f} ms</td>
                        <td>{hop.best_ms:.1f} ms</td>
                        <td>{hop.worst_ms:.1f} ms</td>
                    </tr>
                """
            sections += f"""
                <div class="section">
                    <h2>Route to {mtr.target_name}</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Hop</th>
                                <th>Host</th>
                                <th>Loss</th>
                                <th>Avg</th>
                                <th>Best</th>
                                <th>Worst</th>
                            </tr>
                        </thead>
                        <tbody>
                            {hop_rows}
                        </tbody>
                    </table>
                </div>
            """
        else:
            sections += f"""
                <div class="section">
                    <h2>Route to {mtr.target_name}</h2>
                    <p class="bad">{mtr.error}</p>
                </div>
            """
    return sections


def _build_diagnostic_section(diagnostic: DiagnosticResult) -> str:
    """Build HTML section for diagnostic summary."""
    diag_colors = {
        "none": "#22c55e",
        "local": "#ef4444",
        "isp": "#ef4444",
        "internet": "#eab308",
        "target": "#eab308",
    }
    diag_labels = {
        "none": "No Issues",
        "local": "Local Network Issue",
        "isp": "ISP Issue",
        "internet": "Internet Backbone Issue",
        "target": "Target-Specific Issue",
    }
    diag_color = diag_colors.get(diagnostic.category, "#94a3b8")
    diag_label = diag_labels.get(diagnostic.category, "Unknown")

    details_html = ""
    if diagnostic.details:
        details_html = "<ul>" + "".join(f"<li>{d}</li>" for d in diagnostic.details) + "</ul>"

    recommendations_html = ""
    if diagnostic.recommendations:
        recommendations_html = "<h4>Recommendations</h4><ul>" + "".join(f"<li>{r}</li>" for r in diagnostic.recommendations) + "</ul>"

    return f"""
        <div class="section diagnostic" style="border-left: 4px solid {diag_color};">
            <div class="diag-header">
                <span class="diag-badge" style="background: {diag_color};">{diag_label}</span>
                <span class="diag-confidence">Confidence: {diagnostic.confidence}</span>
            </div>
            <h2 style="color: {diag_color};">{diagnostic.summary}</h2>
            {details_html}
            {recommendations_html}
        </div>
    """


def _build_speed_section(
    speedtest_result: SpeedTestResult,
    expected_speed: float,
    dl_pct: float,
    thresholds: Dict
) -> str:
    """Build HTML section for speed test results."""
    if speedtest_result.success:
        dl_class = get_status_class(dl_pct, "download_pct", thresholds, reverse=True)
        ping_class = get_status_class(speedtest_result.ping_ms, "latency", thresholds)
        return f"""
            <div class="cards">
                <div class="card">
                    <div class="card-title">Download</div>
                    <div class="card-value {dl_class}">{speedtest_result.download_mbps:.1f} Mbps</div>
                    <div class="card-subtitle">{dl_pct:.0f}% of {expected_speed} Mbps expected</div>
                </div>
                <div class="card">
                    <div class="card-title">Upload</div>
                    <div class="card-value">{speedtest_result.upload_mbps:.1f} Mbps</div>
                </div>
                <div class="card">
                    <div class="card-title">Ping</div>
                    <div class="card-value {ping_class}">{speedtest_result.ping_ms:.1f} ms</div>
                </div>
                <div class="card">
                    <div class="card-title">Server</div>
                    <div class="card-value small">{speedtest_result.server}</div>
                </div>
            </div>
        """
    else:
        return f'<p class="bad">{speedtest_result.error}</p>'


def _build_historical_section(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    historical: Dict
) -> str:
    """Build HTML section for historical comparison."""
    prev_ping = {p["target_name"]: p for p in historical.get("ping", [])}
    prev_speed = historical.get("speedtest", {})

    rows = ""
    for result in ping_results:
        if result.success:
            prev = prev_ping.get(result.target_name, {})
            prev_avg = prev.get("avg_ms", 0)
            if prev_avg > 0:
                diff = result.avg_ms - prev_avg
                pct = (diff / prev_avg) * 100
                if abs(pct) < 5:
                    change_class = ""
                    change_text = "stable"
                elif diff < 0:
                    change_class = "good"
                    change_text = f"↓ {abs(diff):.1f}ms ({abs(pct):.0f}%)"
                else:
                    change_class = "bad"
                    change_text = f"↑ {diff:.1f}ms ({pct:.0f}%)"

                rows += f"""
                    <tr>
                        <td>{result.target_name}</td>
                        <td>{result.avg_ms:.1f}ms</td>
                        <td>{prev_avg:.1f}ms</td>
                        <td class="{change_class}">{change_text}</td>
                    </tr>
                """

    if speedtest_result.success and prev_speed.get("success"):
        prev_dl = prev_speed.get("download_mbps", 0)
        if prev_dl > 0:
            diff = speedtest_result.download_mbps - prev_dl
            pct = (diff / prev_dl) * 100
            if abs(pct) < 5:
                change_class = ""
                change_text = "stable"
            elif diff > 0:
                change_class = "good"
                change_text = f"↑ {diff:.1f}Mbps ({pct:.0f}%)"
            else:
                change_class = "bad"
                change_text = f"↓ {abs(diff):.1f}Mbps ({abs(pct):.0f}%)"

            rows += f"""
                <tr>
                    <td>Download Speed</td>
                    <td>{speedtest_result.download_mbps:.1f}Mbps</td>
                    <td>{prev_dl:.1f}Mbps</td>
                    <td class="{change_class}">{change_text}</td>
                </tr>
            """

    if not rows:
        return ""

    return f"""
        <div class="section">
            <h2>Comparison with Previous Run</h2>
            <p class="dim">Previous: {historical.get('timestamp', 'Unknown')}</p>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Current</th>
                        <th>Previous</th>
                        <th>Change</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
    """


def _build_executive_summary(
    connection_score: Optional[ConnectionScore],
    speedtest_result: SpeedTestResult,
    ping_results: List[PingResult],
    expected_speed: float,
) -> str:
    """Build the executive summary section with health gauge."""
    if connection_score is None:
        return ""

    # Determine gauge color
    if connection_score.overall >= 80:
        gauge_color = "var(--good)"
    elif connection_score.overall >= 60:
        gauge_color = "var(--warning)"
    else:
        gauge_color = "var(--bad)"

    # Calculate metrics
    speed_pct = int((speedtest_result.download_mbps / expected_speed) * 100) if expected_speed > 0 and speedtest_result.success else 0

    avg_latency = 0
    avg_loss = 0
    successful_pings = [p for p in ping_results if p.success]
    if successful_pings:
        avg_latency = sum(p.avg_ms for p in successful_pings) / len(successful_pings)
        avg_loss = sum(p.packet_loss for p in successful_pings) / len(successful_pings)

    # Color classes
    speed_class = "good" if speed_pct >= 80 else ("warning" if speed_pct >= 50 else "bad")
    latency_class = "good" if avg_latency < 50 else ("warning" if avg_latency < 100 else "bad")
    loss_class = "good" if avg_loss == 0 else ("warning" if avg_loss < 5 else "bad")

    return f"""
        <div class="section executive-summary">
            <div class="summary-grid">
                <div class="health-gauge" style="--gauge-value: {connection_score.overall}; --gauge-color: {gauge_color};">
                    <div class="gauge-circle">
                        <div class="gauge-inner">
                            <span class="gauge-score" style="color: {gauge_color};">{connection_score.overall}</span>
                            <span class="gauge-label">Health</span>
                            <span class="gauge-grade" style="color: {gauge_color};">{connection_score.grade}</span>
                        </div>
                    </div>
                </div>
                <div class="summary-details">
                    <div>
                        <div class="summary-title">Connection Health</div>
                        <div class="summary-subtitle">{connection_score.summary}</div>
                    </div>
                    <div class="metric-row">
                        <div class="metric-pill">
                            <span class="metric-value {speed_class}">{speed_pct}%</span>
                            <span class="metric-label">Speed</span>
                        </div>
                        <div class="metric-pill">
                            <span class="metric-value {latency_class}">{avg_latency:.0f}ms</span>
                            <span class="metric-label">Latency</span>
                        </div>
                        <div class="metric-pill">
                            <span class="metric-value {loss_class}">{avg_loss:.1f}%</span>
                            <span class="metric-label">Loss</span>
                        </div>
                        <div class="metric-pill">
                            <span class="metric-value">{connection_score.speed_score}</span>
                            <span class="metric-label">Speed Score</span>
                        </div>
                        <div class="metric-pill">
                            <span class="metric-value">{connection_score.latency_score}</span>
                            <span class="metric-label">Latency Score</span>
                        </div>
                        <div class="metric-pill">
                            <span class="metric-value">{connection_score.stability_score}</span>
                            <span class="metric-label">Stability</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    """


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


def _build_bufferbloat_section(bufferbloat: Optional[BufferbloatResult]) -> str:
    """Build bufferbloat test results section."""
    if bufferbloat is None or not bufferbloat.success:
        return ""

    # Determine grade color
    grade_colors = {
        "A": "good",
        "B": "good",
        "C": "warning",
        "D": "bad",
        "F": "bad",
    }
    grade_class = grade_colors.get(bufferbloat.bloat_grade, "")

    return f"""
        <div class="section">
            <h2>Bufferbloat Test</h2>
            <div class="cards">
                <div class="card">
                    <div class="card-title">Grade</div>
                    <div class="card-value {grade_class}">{bufferbloat.bloat_grade}</div>
                    <div class="card-subtitle">DSLReports scale</div>
                </div>
                <div class="card">
                    <div class="card-title">Idle Latency</div>
                    <div class="card-value">{bufferbloat.idle_latency_ms:.1f} ms</div>
                    <div class="card-subtitle">baseline</div>
                </div>
                <div class="card">
                    <div class="card-title">Loaded Latency</div>
                    <div class="card-value">{bufferbloat.loaded_latency_ms:.1f} ms</div>
                    <div class="card-subtitle">under load</div>
                </div>
                <div class="card">
                    <div class="card-title">Bloat</div>
                    <div class="card-value">{bufferbloat.bloat_ms:.1f} ms</div>
                    <div class="card-subtitle">increase</div>
                </div>
            </div>
            <p class="dim" style="margin-top: 1rem;">
                Grade scale: A (&lt;5ms) | B (5-30ms) | C (30-60ms) | D (60-200ms) | F (&gt;200ms)
            </p>
        </div>
    """


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


def _generate_html_template(**kwargs) -> str:
    """Generate the full HTML template with all sections."""
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Network Test Report - {kwargs['timestamp']}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>
    <style>
        :root {{
            --good: #22c55e;
            --warning: #eab308;
            --bad: #ef4444;
            --bg: #0f172a;
            --bg-card: #1e293b;
            --text: #f1f5f9;
            --text-dim: #94a3b8;
            --border: #334155;
        }}

        [data-theme="light"] {{
            --bg: #f8fafc;
            --bg-card: #ffffff;
            --text: #0f172a;
            --text-dim: #64748b;
            --border: #e2e8f0;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
            transition: background-color 0.3s, color 0.3s;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
        }}

        h1 {{
            color: var(--text);
        }}

        .timestamp {{
            color: var(--text-dim);
        }}

        .theme-toggle {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.5rem 1rem;
            color: var(--text);
            cursor: pointer;
            font-size: 0.875rem;
        }}

        .theme-toggle:hover {{
            border-color: var(--text-dim);
        }}

        .section {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border);
        }}

        .section h2 {{
            margin-bottom: 1rem;
            color: var(--text);
            font-size: 1.25rem;
        }}

        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }}

        .card {{
            background: var(--bg);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
            border: 1px solid var(--border);
        }}

        .card-title {{
            color: var(--text-dim);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .card-value {{
            font-size: 2rem;
            font-weight: bold;
            margin: 0.5rem 0;
        }}

        .card-value.small {{
            font-size: 1rem;
        }}

        .card-subtitle {{
            color: var(--text-dim);
            font-size: 0.875rem;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}

        th {{
            color: var(--text-dim);
            font-weight: 500;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }}

        .good {{ color: var(--good); }}
        .warning {{ color: var(--warning); }}
        .bad {{ color: var(--bad); }}
        .dim {{ color: var(--text-dim); }}

        .chart-container {{
            position: relative;
            height: 300px;
            margin-top: 1rem;
        }}

        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 1.5rem;
        }}

        .diagnostic {{
            margin-bottom: 2rem;
        }}

        .diag-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }}

        .diag-badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--bg);
        }}

        .diag-confidence {{
            color: var(--text-dim);
            font-size: 0.875rem;
        }}

        .diagnostic ul {{
            list-style: none;
            padding: 0;
            margin: 0.5rem 0;
        }}

        .diagnostic li {{
            padding: 0.25rem 0;
            padding-left: 1.5rem;
            position: relative;
        }}

        .diagnostic li::before {{
            content: "-";
            position: absolute;
            left: 0.5rem;
            color: var(--text-dim);
        }}

        .diagnostic h4 {{
            margin-top: 1rem;
            margin-bottom: 0.5rem;
            color: var(--text-dim);
            font-size: 0.875rem;
            text-transform: uppercase;
        }}

        .export-buttons {{
            display: flex;
            gap: 0.5rem;
            margin-top: 1rem;
        }}

        .export-btn {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.5rem 1rem;
            color: var(--text);
            cursor: pointer;
            font-size: 0.75rem;
        }}

        .export-btn:hover {{
            border-color: var(--text-dim);
        }}

        .tab-container {{
            margin-bottom: 1rem;
        }}

        .tab-buttons {{
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }}

        .tab-btn {{
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.5rem 1rem;
            color: var(--text);
            cursor: pointer;
            font-size: 0.875rem;
            transition: all 0.2s;
        }}

        .tab-btn:hover {{
            border-color: var(--text-dim);
        }}

        .tab-btn.active {{
            background: var(--good);
            color: var(--bg);
            border-color: var(--good);
        }}

        .executive-summary {{
            margin-bottom: 2rem;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 2rem;
            align-items: center;
        }}

        .health-gauge {{
            position: relative;
            width: 180px;
            height: 180px;
        }}

        .gauge-circle {{
            width: 100%;
            height: 100%;
            border-radius: 50%;
            background: conic-gradient(
                var(--gauge-color) calc(var(--gauge-value) * 3.6deg),
                var(--border) calc(var(--gauge-value) * 3.6deg)
            );
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .gauge-inner {{
            width: 140px;
            height: 140px;
            border-radius: 50%;
            background: var(--bg-card);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}

        .gauge-score {{
            font-size: 3rem;
            font-weight: bold;
            line-height: 1;
        }}

        .gauge-label {{
            font-size: 0.875rem;
            color: var(--text-dim);
            text-transform: uppercase;
        }}

        .gauge-grade {{
            font-size: 1.25rem;
            font-weight: 600;
            margin-top: 0.25rem;
        }}

        .summary-details {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}

        .summary-title {{
            font-size: 1.5rem;
            font-weight: 600;
        }}

        .summary-subtitle {{
            color: var(--text-dim);
            font-size: 1rem;
        }}

        .metric-row {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }}

        .metric-pill {{
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 80px;
        }}

        .metric-value {{
            font-size: 1.25rem;
            font-weight: 600;
        }}

        .metric-label {{
            font-size: 0.75rem;
            color: var(--text-dim);
            text-transform: uppercase;
        }}

        @media (max-width: 600px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}

            body {{
                padding: 1rem;
            }}

            .header {{
                flex-direction: column;
                gap: 1rem;
                text-align: center;
            }}

            .summary-grid {{
                grid-template-columns: 1fr;
                justify-items: center;
                text-align: center;
            }}
        }}

        @media print {{
            body {{
                background: white;
                color: black;
            }}
            .theme-toggle, .export-buttons {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>Network Test Report</h1>
                <p class="timestamp">{kwargs['timestamp']}</p>
            </div>
            <button class="theme-toggle" onclick="toggleTheme()">Toggle Theme</button>
        </div>

        {kwargs.get('executive_summary', '')}

        {kwargs.get('quality_section', '')}

        {kwargs.get('evidence_section', '')}

        {kwargs.get('bufferbloat_section', '')}

        {kwargs.get('video_services_section', '')}

        {kwargs['diagnostic_section']}

        <div class="section">
            <h2>Speed Test</h2>
            {kwargs['speed_section']}
        </div>

        <div class="section">
            <h2>Latency Tests</h2>
            <table>
                <thead>
                    <tr>
                        <th>Target</th>
                        <th>Min</th>
                        <th>Avg</th>
                        <th>Max</th>
                        <th>Jitter</th>
                        <th>Loss</th>
                    </tr>
                </thead>
                <tbody>
                    {kwargs['latency_rows']}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>DNS Resolution</h2>
            <table>
                <thead>
                    <tr>
                        <th>Target</th>
                        <th>Resolved IP</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody>
                    {kwargs['dns_rows']}
                </tbody>
            </table>
        </div>

        {kwargs['mtr_sections']}

        {kwargs.get('route_heatmap', '')}

        {kwargs['historical_section']}

        <div class="charts-grid">
            <div class="section">
                <h2>Latency Comparison</h2>
                <div class="chart-container">
                    <canvas id="latencyChart"></canvas>
                </div>
            </div>

            <div class="section">
                <h2>Jitter & Packet Loss</h2>
                <div class="chart-container">
                    <canvas id="jitterChart"></canvas>
                </div>
            </div>

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
        </div>

        <div class="export-buttons">
            <button class="export-btn" onclick="copyJSON()">Copy as JSON</button>
            <button class="export-btn" onclick="window.print()">Print Report</button>
        </div>
    </div>

    <script>
        // Theme toggle
        function toggleTheme() {{
            const html = document.documentElement;
            const current = html.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
        }}

        // Load saved theme
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {{
            document.documentElement.setAttribute('data-theme', savedTheme);
        }}

        // Copy results as JSON
        function copyJSON() {{
            const data = {{
                timestamp: '{kwargs['timestamp']}',
                ping: {kwargs['ping_avg']},
                labels: {kwargs['ping_labels']}
            }};
            navigator.clipboard.writeText(JSON.stringify(data, null, 2))
                .then(() => alert('Copied to clipboard!'))
                .catch(err => console.error('Failed to copy:', err));
        }}

        function copyEvidence() {{
            const evidenceEl = document.querySelector('.section[style*="border-left: 4px solid var(--bad)"]');
            if (evidenceEl) {{
                const text = evidenceEl.innerText;
                navigator.clipboard.writeText(text)
                    .then(() => alert('Evidence copied to clipboard!'))
                    .catch(err => console.error('Failed to copy:', err));
            }}
        }}

        const chartColors = {{
            good: '#22c55e',
            warning: '#eab308',
            bad: '#ef4444',
            blue: '#3b82f6',
            purple: '#8b5cf6',
            cyan: '#06b6d4',
        }};

        const zoomOptions = {{
            zoom: {{
                wheel: {{ enabled: true }},
                pinch: {{ enabled: true }},
                mode: 'xy',
            }},
            pan: {{
                enabled: true,
                mode: 'xy',
            }}
        }};

        // Latency Chart
        new Chart(document.getElementById('latencyChart'), {{
            type: 'bar',
            data: {{
                labels: {kwargs['ping_labels']},
                datasets: [
                    {{
                        label: 'Min',
                        data: {kwargs['ping_min']},
                        backgroundColor: chartColors.good,
                    }},
                    {{
                        label: 'Avg',
                        data: {kwargs['ping_avg']},
                        backgroundColor: chartColors.blue,
                    }},
                    {{
                        label: 'Max',
                        data: {kwargs['ping_max']},
                        backgroundColor: chartColors.warning,
                    }},
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        labels: {{ color: '#f1f5f9' }}
                    }},
                    zoom: zoomOptions
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#94a3b8' }},
                        grid: {{ color: '#334155' }}
                    }},
                    y: {{
                        ticks: {{ color: '#94a3b8' }},
                        grid: {{ color: '#334155' }},
                        title: {{
                            display: true,
                            text: 'Latency (ms)',
                            color: '#94a3b8'
                        }}
                    }}
                }}
            }}
        }});

        // Jitter & Loss Chart
        new Chart(document.getElementById('jitterChart'), {{
            type: 'bar',
            data: {{
                labels: {kwargs['ping_labels']},
                datasets: [
                    {{
                        label: 'Jitter (ms)',
                        data: {kwargs['ping_jitter']},
                        backgroundColor: chartColors.purple,
                        yAxisID: 'y',
                    }},
                    {{
                        label: 'Packet Loss (%)',
                        data: {kwargs['ping_loss']},
                        backgroundColor: chartColors.bad,
                        yAxisID: 'y1',
                    }},
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        labels: {{ color: '#f1f5f9' }}
                    }},
                    zoom: zoomOptions
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#94a3b8' }},
                        grid: {{ color: '#334155' }}
                    }},
                    y: {{
                        type: 'linear',
                        position: 'left',
                        ticks: {{ color: '#94a3b8' }},
                        grid: {{ color: '#334155' }},
                        title: {{
                            display: true,
                            text: 'Jitter (ms)',
                            color: '#94a3b8'
                        }}
                    }},
                    y1: {{
                        type: 'linear',
                        position: 'right',
                        ticks: {{ color: '#94a3b8' }},
                        grid: {{ drawOnChartArea: false }},
                        title: {{
                            display: true,
                            text: 'Packet Loss (%)',
                            color: '#94a3b8'
                        }}
                    }}
                }}
            }}
        }});

        // MTR Chart with route selector
        const mtrData = {kwargs['mtr_all_routes']};
        let currentMtrChart = null;

        function createMtrTabs() {{
            const tabContainer = document.getElementById('mtrTabs');
            if (!mtrData.target_names || mtrData.target_names.length === 0) {{
                tabContainer.textContent = 'No route data available';
                tabContainer.className = 'dim';
                return;
            }}

            mtrData.target_names.forEach((name, index) => {{
                const btn = document.createElement('button');
                btn.className = 'tab-btn' + (index === 0 ? ' active' : '');
                btn.textContent = name;
                btn.onclick = () => selectMtrRoute(index);
                tabContainer.appendChild(btn);
            }});

            if (mtrData.routes.length > 0) {{
                renderMtrChart(0);
            }}
        }}

        function selectMtrRoute(index) {{
            document.querySelectorAll('#mtrTabs .tab-btn').forEach((btn, i) => {{
                btn.classList.toggle('active', i === index);
            }});
            renderMtrChart(index);
        }}

        function renderMtrChart(routeIndex) {{
            const route = mtrData.routes[routeIndex];
            if (!route) return;

            if (currentMtrChart) {{
                currentMtrChart.destroy();
            }}

            const ctx = document.getElementById('mtrChart').getContext('2d');
            currentMtrChart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: route.labels,
                    datasets: [
                        {{
                            label: 'Latency (ms)',
                            data: route.latency,
                            borderColor: chartColors.cyan,
                            backgroundColor: 'rgba(6, 182, 212, 0.1)',
                            fill: true,
                            tension: 0.3,
                            yAxisID: 'y',
                        }},
                        {{
                            label: 'Packet Loss (%)',
                            data: route.loss,
                            borderColor: chartColors.bad,
                            backgroundColor: 'transparent',
                            borderDash: [5, 5],
                            yAxisID: 'y1',
                        }},
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            labels: {{ color: '#f1f5f9' }}
                        }},
                        tooltip: {{
                            callbacks: {{
                                afterLabel: function(context) {{
                                    const hopIndex = context.dataIndex;
                                    return 'Host: ' + route.hosts[hopIndex];
                                }}
                            }}
                        }},
                        zoom: zoomOptions
                    }},
                    scales: {{
                        x: {{
                            ticks: {{ color: '#94a3b8' }},
                            grid: {{ color: '#334155' }}
                        }},
                        y: {{
                            type: 'linear',
                            position: 'left',
                            ticks: {{ color: '#94a3b8' }},
                            grid: {{ color: '#334155' }},
                            title: {{
                                display: true,
                                text: 'Latency (ms)',
                                color: '#94a3b8'
                            }}
                        }},
                        y1: {{
                            type: 'linear',
                            position: 'right',
                            min: 0,
                            max: 100,
                            ticks: {{ color: '#94a3b8' }},
                            grid: {{ drawOnChartArea: false }},
                            title: {{
                                display: true,
                                text: 'Packet Loss (%)',
                                color: '#94a3b8'
                            }}
                        }}
                    }}
                }}
            }});
        }}

        createMtrTabs();
    </script>
</body>
</html>
"""
