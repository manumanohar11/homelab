"""Terminal output formatter using Rich."""

from typing import List, Dict, Any, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from ..models import (
    PingResult, SpeedTestResult, DnsResult,
    MtrResult, DiagnosticResult, PortResult, HttpResult, VideoServiceResult
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
