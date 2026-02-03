"""Terminal output formatter using Rich."""

from typing import List, Dict, Any, Tuple, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from ..models import (
    PingResult, SpeedTestResult, DnsResult,
    MtrResult, DiagnosticResult, PortResult, HttpResult, VideoServiceResult,
    ConnectionScore
)


def evaluate_metric(value: float, metric: str, thresholds: Dict, reverse: bool = False) -> Tuple[str, str]:
    """
    Evaluate a metric value against thresholds.

    Args:
        value: The metric value to evaluate
        metric: The metric name (key in thresholds)
        thresholds: Threshold dict with metric -> {good, warning} values
        reverse: If True, higher values are better

    Returns:
        tuple of (status, color)
    """
    metric_thresholds = thresholds.get(metric, {"good": 50, "warning": 100})

    if reverse:
        # Higher is better (e.g., download speed percentage)
        if value >= metric_thresholds["good"]:
            return ("good", "green")
        elif value >= metric_thresholds["warning"]:
            return ("warning", "yellow")
        else:
            return ("bad", "red")
    else:
        # Lower is better (e.g., latency, jitter, packet loss)
        if value <= metric_thresholds["good"]:
            return ("good", "green")
        elif value <= metric_thresholds["warning"]:
            return ("warning", "yellow")
        else:
            return ("bad", "red")


def get_status_color(value: float, metric: str, thresholds: Dict, reverse: bool = False) -> str:
    """Get color based on threshold."""
    _, color = evaluate_metric(value, metric, thresholds, reverse)
    return color


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
    """
    Display results in terminal using rich.

    Args:
        ping_results: Ping test results
        speedtest_result: Speed test result
        dns_results: DNS test results
        mtr_results: MTR results
        expected_speed: Expected download speed in Mbps
        diagnostic: Diagnostic analysis result
        thresholds: Threshold configuration
        console: Rich console instance
        port_results: TCP port test results (optional)
        http_results: HTTP latency test results (optional)
    """
    from datetime import datetime

    console.print()
    console.print(Panel.fit(
        "[bold blue]Network Test Results[/bold blue]",
        subtitle=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    console.print()

    # Display Diagnostic Summary First
    _display_diagnostic(diagnostic, console)

    # Speed Test Results
    _display_speedtest(speedtest_result, expected_speed, thresholds, console)

    # Latency Results
    _display_latency(ping_results, thresholds, console)

    # DNS Results
    _display_dns(dns_results, thresholds, console)

    # MTR Results
    _display_mtr(mtr_results, thresholds, console)

    # Port Results (if any)
    if port_results:
        _display_ports(port_results, console)

    # HTTP Results (if any)
    if http_results:
        _display_http(http_results, console)

    # Video Service Results (if any)
    if video_service_results:
        _display_video_services(video_service_results, console)


def _display_diagnostic(diagnostic: DiagnosticResult, console: Console) -> None:
    """Display diagnostic summary panel."""
    category_colors = {
        "none": "green",
        "local": "red",
        "isp": "red",
        "internet": "yellow",
        "target": "yellow",
    }
    category_icons = {
        "none": "[green]OK[/green]",
        "local": "[red]LOCAL[/red]",
        "isp": "[red]ISP[/red]",
        "internet": "[yellow]INTERNET[/yellow]",
        "target": "[yellow]TARGET[/yellow]",
    }
    color = category_colors.get(diagnostic.category, "white")

    diag_text = Text()
    diag_text.append(f"\n{diagnostic.summary}\n\n", style=f"bold {color}")

    if diagnostic.details:
        diag_text.append("Issues Found:\n", style="bold")
        for detail in diagnostic.details:
            diag_text.append(f"  - {detail}\n", style=color)
        diag_text.append("\n")

    if diagnostic.recommendations:
        diag_text.append("Recommendations:\n", style="bold")
        for rec in diagnostic.recommendations:
            diag_text.append(f"  - {rec}\n", style="dim")

    panel_title = f"Diagnosis: {category_icons.get(diagnostic.category, 'UNKNOWN')} ({diagnostic.confidence} confidence)"
    console.print(Panel(diag_text, title=panel_title, border_style=color))
    console.print()


def _display_speedtest(
    speedtest_result: SpeedTestResult,
    expected_speed: float,
    thresholds: Dict,
    console: Console
) -> None:
    """Display speed test results."""
    console.print("[bold]Speed Test[/bold]")
    if speedtest_result.success:
        speed_table = Table(box=box.ROUNDED)
        speed_table.add_column("Metric", style="cyan")
        speed_table.add_column("Value", justify="right")
        speed_table.add_column("Status", justify="center")

        dl_pct = (speedtest_result.download_mbps / expected_speed) * 100 if expected_speed > 0 else 100
        dl_color = get_status_color(dl_pct, "download_pct", thresholds, reverse=True)

        speed_table.add_row(
            "Download",
            f"{speedtest_result.download_mbps:.1f} Mbps",
            f"[{dl_color}]●[/{dl_color}] {dl_pct:.0f}% of expected"
        )
        speed_table.add_row(
            "Upload",
            f"{speedtest_result.upload_mbps:.1f} Mbps",
            ""
        )

        ping_color = get_status_color(speedtest_result.ping_ms, "latency", thresholds)
        speed_table.add_row(
            "Ping",
            f"{speedtest_result.ping_ms:.1f} ms",
            f"[{ping_color}]●[/{ping_color}]"
        )
        speed_table.add_row("Server", speedtest_result.server, "")

        console.print(speed_table)
    else:
        console.print(f"[red]  {speedtest_result.error}[/red]")
    console.print()


def _display_latency(
    ping_results: List[PingResult],
    thresholds: Dict,
    console: Console
) -> None:
    """Display ping latency results."""
    console.print("[bold]Latency Tests[/bold]")
    latency_table = Table(box=box.ROUNDED)
    latency_table.add_column("Target", style="cyan")
    latency_table.add_column("Min", justify="right")
    latency_table.add_column("Avg", justify="right")
    latency_table.add_column("Max", justify="right")
    latency_table.add_column("Jitter", justify="right")
    latency_table.add_column("Loss", justify="right")

    for pr in ping_results:
        if pr.success:
            avg_color = get_status_color(pr.avg_ms, "latency", thresholds)
            jitter_color = get_status_color(pr.jitter_ms, "jitter", thresholds)
            loss_color = get_status_color(pr.packet_loss, "packet_loss", thresholds)

            latency_table.add_row(
                pr.target_name,
                f"{pr.min_ms:.1f} ms",
                f"[{avg_color}]{pr.avg_ms:.1f} ms[/{avg_color}]",
                f"{pr.max_ms:.1f} ms",
                f"[{jitter_color}]{pr.jitter_ms:.1f} ms[/{jitter_color}]",
                f"[{loss_color}]{pr.packet_loss:.1f}%[/{loss_color}]",
            )
        else:
            latency_table.add_row(
                pr.target_name,
                "[red]Error[/red]",
                "[red]-[/red]",
                "[red]-[/red]",
                "[red]-[/red]",
                f"[red]{pr.error}[/red]",
            )

    console.print(latency_table)
    console.print()


def _display_dns(
    dns_results: List[DnsResult],
    thresholds: Dict,
    console: Console
) -> None:
    """Display DNS resolution results."""
    console.print("[bold]DNS Resolution[/bold]")
    dns_table = Table(box=box.ROUNDED)
    dns_table.add_column("Target", style="cyan")
    dns_table.add_column("Resolved IP")
    dns_table.add_column("Time", justify="right")

    for dr in dns_results:
        if dr.success:
            time_color = get_status_color(dr.resolution_time_ms, "latency", thresholds)
            dns_table.add_row(
                dr.target,
                dr.resolved_ip or "-",
                f"[{time_color}]{dr.resolution_time_ms:.0f} ms[/{time_color}]" if dr.resolution_time_ms > 0 else "N/A (IP)"
            )
        else:
            dns_table.add_row(dr.target, "[red]Failed[/red]", dr.error)

    console.print(dns_table)
    console.print()


def _display_mtr(
    mtr_results: List[MtrResult],
    thresholds: Dict,
    console: Console
) -> None:
    """Display MTR route analysis results."""
    for mtr in mtr_results:
        console.print(f"[bold]Route to {mtr.target_name}[/bold]")
        if mtr.success and mtr.hops:
            mtr_table = Table(box=box.ROUNDED)
            mtr_table.add_column("Hop", justify="right", style="dim")
            mtr_table.add_column("Host")
            mtr_table.add_column("Loss", justify="right")
            mtr_table.add_column("Avg", justify="right")
            mtr_table.add_column("Best", justify="right")
            mtr_table.add_column("Worst", justify="right")

            for hop in mtr.hops:
                loss_color = get_status_color(hop.loss_pct, "packet_loss", thresholds)
                avg_color = get_status_color(hop.avg_ms, "latency", thresholds)

                mtr_table.add_row(
                    str(hop.hop_number),
                    hop.host,
                    f"[{loss_color}]{hop.loss_pct:.1f}%[/{loss_color}]",
                    f"[{avg_color}]{hop.avg_ms:.1f} ms[/{avg_color}]",
                    f"{hop.best_ms:.1f} ms",
                    f"{hop.worst_ms:.1f} ms",
                )

            console.print(mtr_table)
        else:
            console.print(f"[red]  {mtr.error}[/red]")
        console.print()


def _display_ports(port_results: List[PortResult], console: Console) -> None:
    """Display TCP port test results."""
    console.print("[bold]TCP Port Tests[/bold]")
    port_table = Table(box=box.ROUNDED)
    port_table.add_column("Host", style="cyan")
    port_table.add_column("Port", justify="right")
    port_table.add_column("Status", justify="center")
    port_table.add_column("Response Time", justify="right")

    for pr in port_results:
        status = "[green]Open[/green]" if pr.open else "[red]Closed[/red]"
        time_str = f"{pr.response_time_ms:.1f} ms" if pr.open else pr.error
        port_table.add_row(pr.host, str(pr.port), status, time_str)

    console.print(port_table)
    console.print()


def _display_http(http_results: List[HttpResult], console: Console) -> None:
    """Display HTTP latency test results."""
    console.print("[bold]HTTP Latency Tests[/bold]")
    http_table = Table(box=box.ROUNDED)
    http_table.add_column("URL", style="cyan")
    http_table.add_column("Status", justify="center")
    http_table.add_column("Response Time", justify="right")

    for hr in http_results:
        if hr.success:
            status = f"[green]{hr.status_code}[/green]"
            time_str = f"{hr.response_time_ms:.1f} ms"
        else:
            status = f"[red]{hr.status_code or 'Failed'}[/red]"
            time_str = hr.error
        http_table.add_row(hr.url, status, time_str)

    console.print(http_table)
    console.print()


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


def simple_display(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    diagnostic: DiagnosticResult,
    connection_score: Optional[ConnectionScore],
    console: Console,
) -> None:
    """
    Display results in simple, non-technical format for everyday users.

    Shows maximum 5-7 lines with plain English descriptions.
    No jargon like jitter, packet loss percentage, or MOS score.

    Args:
        ping_results: Ping test results
        speedtest_result: Speed test result
        diagnostic: Diagnostic analysis result
        connection_score: Connection health score (optional)
        console: Rich console instance
    """
    console.print()

    # Determine overall grade and quality description
    grade, stars, quality_desc, color = _calculate_simple_grade(
        ping_results, speedtest_result, diagnostic, connection_score
    )

    # Line 1: Overall grade with stars
    console.print(
        f"[bold {color}]Your Internet: {grade} {stars}[/bold {color}]"
    )

    # Line 2: One-line quality summary
    console.print(f"[{color}]Your connection is {quality_desc}[/{color}]")

    console.print()

    # Line 3: Speed summary
    if speedtest_result and speedtest_result.success:
        dl = speedtest_result.download_mbps
        ul = speedtest_result.upload_mbps
        dl_desc = _speed_to_description(dl)
        console.print(
            f"[cyan]Speed:[/cyan] {dl_desc} ({dl:.0f} Mbps down | {ul:.0f} Mbps up)"
        )
    else:
        console.print("[cyan]Speed:[/cyan] Could not test")

    # Line 4: Responsiveness (latency in plain terms)
    avg_latency = _get_average_latency(ping_results)
    if avg_latency is not None:
        latency_desc, latency_color = _latency_to_description(avg_latency)
        console.print(
            f"[cyan]Responsiveness:[/cyan] [{latency_color}]{latency_desc}[/{latency_color}] ({avg_latency:.0f}ms)"
        )

    # Line 5: Actionable tip if there are issues
    tip = _generate_actionable_tip(ping_results, speedtest_result, diagnostic)
    if tip:
        console.print()
        console.print(f"[yellow]Tip: {tip}[/yellow]")

    console.print()


def _calculate_simple_grade(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    diagnostic: DiagnosticResult,
    connection_score: Optional[ConnectionScore],
) -> Tuple[str, str, str, str]:
    """
    Calculate a simple letter grade with stars.

    Returns:
        Tuple of (grade, stars, quality_description, color)
    """
    # If we have a connection score, use it
    if connection_score:
        grade = connection_score.grade
        overall = connection_score.overall
    else:
        # Calculate a basic score from available data
        score = 100

        # Deduct for latency issues
        avg_latency = _get_average_latency(ping_results)
        if avg_latency is not None:
            if avg_latency > 150:
                score -= 40
            elif avg_latency > 100:
                score -= 25
            elif avg_latency > 50:
                score -= 10

        # Deduct for packet loss
        avg_loss = _get_average_packet_loss(ping_results)
        if avg_loss is not None and avg_loss > 0:
            if avg_loss > 5:
                score -= 30
            elif avg_loss > 2:
                score -= 20
            elif avg_loss > 0.5:
                score -= 10

        # Deduct for speed issues
        if speedtest_result and speedtest_result.success:
            if speedtest_result.download_mbps < 5:
                score -= 30
            elif speedtest_result.download_mbps < 25:
                score -= 15

        # Deduct for diagnostic issues
        if diagnostic.category != "none":
            if diagnostic.confidence == "high":
                score -= 20
            elif diagnostic.confidence == "medium":
                score -= 10

        overall = max(0, min(100, score))
        grade = _score_to_grade(overall)

    # Map grade to stars and description
    grade_info = {
        "A+": ("*****", "Excellent", "green"),
        "A":  ("****-", "Very Good", "green"),
        "B+": ("***--", "Good", "green"),
        "B":  ("***--", "Good", "yellow"),
        "C":  ("**---", "Fair", "yellow"),
        "D":  ("*----", "Poor", "red"),
        "F":  ("-----", "Very Poor", "red"),
    }

    stars, desc, color = grade_info.get(grade, ("**---", "Fair", "yellow"))
    return grade, stars, desc, color


def _score_to_grade(score: int) -> str:
    """Convert numeric score to letter grade."""
    if score >= 95:
        return "A+"
    elif score >= 85:
        return "A"
    elif score >= 75:
        return "B+"
    elif score >= 65:
        return "B"
    elif score >= 50:
        return "C"
    elif score >= 35:
        return "D"
    else:
        return "F"


def _get_average_latency(ping_results: List[PingResult]) -> Optional[float]:
    """Get average latency from ping results."""
    successful = [p for p in ping_results if p.success]
    if not successful:
        return None
    return sum(p.avg_ms for p in successful) / len(successful)


def _get_average_packet_loss(ping_results: List[PingResult]) -> Optional[float]:
    """Get average packet loss from ping results."""
    successful = [p for p in ping_results if p.success]
    if not successful:
        return None
    return sum(p.packet_loss for p in successful) / len(successful)


def _speed_to_description(download_mbps: float) -> str:
    """Convert download speed to user-friendly description."""
    if download_mbps >= 100:
        return "Very Fast"
    elif download_mbps >= 50:
        return "Fast"
    elif download_mbps >= 25:
        return "Good"
    elif download_mbps >= 10:
        return "Moderate"
    elif download_mbps >= 5:
        return "Slow"
    else:
        return "Very Slow"


def _latency_to_description(latency_ms: float) -> Tuple[str, str]:
    """Convert latency to user-friendly description and color."""
    if latency_ms <= 20:
        return "Excellent", "green"
    elif latency_ms <= 50:
        return "Fast", "green"
    elif latency_ms <= 100:
        return "Good", "yellow"
    elif latency_ms <= 150:
        return "Slow", "yellow"
    else:
        return "Very Slow", "red"


def _generate_actionable_tip(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    diagnostic: DiagnosticResult,
) -> Optional[str]:
    """
    Generate one actionable tip for the user based on detected issues.

    Returns the most important tip, or None if no issues.
    """
    # Check for packet loss (connection stability issues)
    avg_loss = _get_average_packet_loss(ping_results)
    if avg_loss is not None and avg_loss > 2:
        return "Your connection is dropping data. Try restarting your router."

    # Check for high latency
    avg_latency = _get_average_latency(ping_results)
    if avg_latency is not None and avg_latency > 100:
        return "Your connection is slow to respond. Try moving closer to your router or using a wired connection."

    # Check for slow speeds
    if speedtest_result and speedtest_result.success:
        if speedtest_result.download_mbps < 10:
            return "Your download speed is low. Check if others are using the network or contact your provider."

    # Check diagnostic category
    if diagnostic.category == "local":
        return "There may be an issue with your device or router. Try restarting both."
    elif diagnostic.category == "isp":
        return "Your internet provider may be having issues. Consider contacting them if problems persist."
    elif diagnostic.category == "internet" or diagnostic.category == "target":
        return "Some websites may be slow right now. This is usually temporary."

    return None
