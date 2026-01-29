"""Continuous monitoring mode with live dashboard."""

import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich import box

from ..models import PingResult
from ..tests.ping import run_ping_test
from ..output.terminal import evaluate_metric


def run_monitor_mode(
    targets: Dict[str, str],
    interval: int,
    ping_count: int = 3,
    thresholds: Dict[str, Any] = None,
    interface: Optional[str] = None,
    ip_version: Optional[int] = None,
    console: Console = None,
    json_logger: Any = None,
) -> None:
    """
    Run continuous monitoring mode with live-updating dashboard.

    Uses Rich Live to display real-time ping statistics that refresh
    on each interval.

    Args:
        targets: Dict of target_name -> hostname/IP to monitor
        interval: Seconds between test rounds
        ping_count: Number of ping packets per target
        thresholds: Threshold configuration
        interface: Network interface to use (optional)
        ip_version: Force IPv4 (4) or IPv6 (6), or None for auto
        console: Rich console for output
        json_logger: JsonLogger instance for structured logging
    """
    if console is None:
        console = Console()

    if thresholds is None:
        thresholds = {
            "latency": {"good": 50, "warning": 100},
            "jitter": {"good": 15, "warning": 30},
            "packet_loss": {"good": 0, "warning": 2},
        }

    # Track historical data for each target (last 10 readings)
    history: Dict[str, List[float]] = {name: [] for name in targets.keys()}
    max_history = 10

    def generate_dashboard(results: List[PingResult], round_num: int) -> Table:
        """Generate the monitoring dashboard table."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Main table
        table = Table(
            title=f"[bold blue]Network Monitor[/bold blue] - Round {round_num}",
            caption=f"Last update: {now} | Interval: {interval}s | Ctrl+C to stop",
            box=box.ROUNDED,
            header_style="bold cyan",
            show_lines=True
        )

        table.add_column("Target", style="white", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Latency", justify="right")
        table.add_column("Jitter", justify="right")
        table.add_column("Loss", justify="right")
        table.add_column("Trend", justify="center")
        table.add_column("Min/Max", justify="right")

        for result in results:
            # Update history
            if result.success:
                history[result.target_name].append(result.avg_ms)
                if len(history[result.target_name]) > max_history:
                    history[result.target_name].pop(0)

            # Determine status emoji and colors
            if not result.success:
                status = "[red]● DOWN[/red]"
                latency_str = f"[red]{result.error or 'Unreachable'}[/red]"
                jitter_str = "-"
                loss_str = "[red]100%[/red]"
                trend_str = "⬇"
                minmax_str = "-"
            else:
                # Evaluate metrics
                lat_status, lat_color = evaluate_metric(result.avg_ms, "latency", thresholds)
                jit_status, jit_color = evaluate_metric(result.jitter_ms, "jitter", thresholds)
                loss_status, loss_color = evaluate_metric(result.packet_loss, "packet_loss", thresholds)

                # Overall status
                if lat_status == "bad" or loss_status == "bad":
                    status = "[red]● WARN[/red]"
                elif lat_status == "warning" or loss_status == "warning":
                    status = "[yellow]● FAIR[/yellow]"
                else:
                    status = "[green]● GOOD[/green]"

                latency_str = f"[{lat_color}]{result.avg_ms:.1f}ms[/{lat_color}]"
                jitter_str = f"[{jit_color}]{result.jitter_ms:.1f}ms[/{jit_color}]"
                loss_str = f"[{loss_color}]{result.packet_loss:.1f}%[/{loss_color}]"
                minmax_str = f"{result.min_ms:.0f}/{result.max_ms:.0f}ms"

                # Calculate trend from history
                hist = history[result.target_name]
                if len(hist) >= 2:
                    recent_avg = sum(hist[-3:]) / len(hist[-3:])
                    older_avg = sum(hist[:-3]) / max(len(hist[:-3]), 1) if len(hist) > 3 else recent_avg
                    if recent_avg > older_avg * 1.2:
                        trend_str = "[red]↗[/red]"  # Getting worse
                    elif recent_avg < older_avg * 0.8:
                        trend_str = "[green]↘[/green]"  # Getting better
                    else:
                        trend_str = "→"  # Stable
                else:
                    trend_str = "-"

            table.add_row(
                result.target_name,
                status,
                latency_str,
                jitter_str,
                loss_str,
                trend_str,
                minmax_str
            )

        return table

    console.print()
    console.print(Panel.fit(
        "[bold blue]Network Monitor[/bold blue]\n"
        f"[dim]Monitoring {len(targets)} targets every {interval}s[/dim]\n"
        "[dim]Press Ctrl+C to stop[/dim]",
        border_style="blue"
    ))
    console.print()

    round_num = 0
    try:
        with Live(console=console, refresh_per_second=1, transient=False) as live:
            while True:
                round_num += 1

                # Run ping tests
                results = []
                for name, target in targets.items():
                    result = run_ping_test(
                        target,
                        target_name=name,
                        count=ping_count,
                        ip_version=ip_version,
                        interface=interface
                    )
                    results.append(result)

                # Update the live display
                dashboard = generate_dashboard(results, round_num)
                live.update(dashboard)

                # Log results if logger is configured
                if json_logger:
                    for result in results:
                        json_logger.log_ping_result(result)

                # Wait for next interval
                time.sleep(interval)

    except KeyboardInterrupt:
        console.print()
        console.print(f"[dim]Monitoring stopped after {round_num} rounds.[/dim]")
