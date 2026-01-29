"""
History management for tracking test results over time.
"""

import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import PingResult, SpeedTestResult, DnsResult


def save_history(
    history_file: str,
    ping_results: List["PingResult"],
    speedtest_result: Optional["SpeedTestResult"],
    dns_results: List["DnsResult"],
    console: Optional[Any] = None
) -> None:
    """
    Save test results to history file for comparison.

    Args:
        history_file: Path to history JSON file
        ping_results: List of ping test results
        speedtest_result: Speed test result (optional)
        dns_results: List of DNS test results
        console: Rich console for warning output (optional)
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "ping": [
            {
                "target": r.target,
                "target_name": r.target_name,
                "avg_ms": r.avg_ms,
                "jitter_ms": r.jitter_ms,
                "packet_loss": r.packet_loss,
                "success": r.success,
            }
            for r in ping_results
        ],
        "speedtest": {
            "download_mbps": speedtest_result.download_mbps if speedtest_result else 0,
            "upload_mbps": speedtest_result.upload_mbps if speedtest_result else 0,
            "ping_ms": speedtest_result.ping_ms if speedtest_result else 0,
            "success": speedtest_result.success if speedtest_result else False,
        } if speedtest_result else None,
        "dns": [
            {
                "target": r.target,
                "resolution_time_ms": r.resolution_time_ms,
                "success": r.success,
            }
            for r in dns_results
        ],
    }

    # Load existing history or create new
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = []

    # Append new entry and keep last 100 entries
    history.append(entry)
    history = history[-100:]

    # Save
    try:
        os.makedirs(os.path.dirname(os.path.abspath(history_file)), exist_ok=True)
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
    except IOError as e:
        if console:
            console.print(f"[yellow]Warning: Could not save history: {e}[/yellow]")


def load_history(history_file: str) -> Optional[Dict[str, Any]]:
    """
    Load the most recent history entry for comparison.

    Args:
        history_file: Path to history JSON file

    Returns:
        Most recent history entry, or None if not found
    """
    if not os.path.exists(history_file):
        return None

    try:
        with open(history_file, 'r') as f:
            history = json.load(f)
            if history and len(history) > 0:
                return history[-1]  # Return most recent
    except (json.JSONDecodeError, IOError):
        pass
    return None


def format_change(
    current: float,
    previous: float,
    unit: str = "ms",
    lower_is_better: bool = True
) -> str:
    """
    Format a metric change with Rich color coding.

    Args:
        current: Current metric value
        previous: Previous metric value
        unit: Unit suffix (e.g., "ms", "Mbps")
        lower_is_better: Whether lower values are better

    Returns:
        Formatted string with color markup
    """
    if previous == 0:
        return f"{current:.1f}{unit}"

    diff = current - previous
    pct = (diff / previous) * 100 if previous != 0 else 0

    if abs(pct) < 5:
        # Negligible change
        return f"{current:.1f}{unit} [dim](→ stable)[/dim]"
    elif (diff < 0 and lower_is_better) or (diff > 0 and not lower_is_better):
        # Improved
        return f"{current:.1f}{unit} [green](↓ {abs(diff):.1f}{unit}, {abs(pct):.0f}% better)[/green]"
    else:
        # Degraded
        return f"{current:.1f}{unit} [red](↑ {abs(diff):.1f}{unit}, {abs(pct):.0f}% worse)[/red]"


def show_history_comparison(
    ping_results: List["PingResult"],
    speedtest_result: Optional["SpeedTestResult"],
    previous: Dict[str, Any],
    console: Any
) -> None:
    """
    Display comparison table between current and previous results.

    Args:
        ping_results: Current ping results
        speedtest_result: Current speed test result
        previous: Previous history entry
        console: Rich console for output
    """
    from rich.table import Table
    from rich import box

    console.print()
    console.print("[bold]Comparison with Previous Run[/bold]")
    console.print(f"[dim]Previous: {previous['timestamp']}[/dim]")

    table = Table(box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Current", justify="right")
    table.add_column("Previous", justify="right")
    table.add_column("Change", justify="right")

    # Build lookup for previous ping results
    prev_ping = {p["target_name"]: p for p in previous.get("ping", [])}

    for result in ping_results:
        if result.success:
            prev = prev_ping.get(result.target_name, {})
            prev_avg = prev.get("avg_ms", 0)
            prev_loss = prev.get("packet_loss", 0)

            # Latency row
            if prev_avg > 0:
                diff = result.avg_ms - prev_avg
                pct = (diff / prev_avg) * 100
                if abs(pct) < 5:
                    change = "[dim]→ stable[/dim]"
                elif diff < 0:
                    change = f"[green]↓ {abs(diff):.1f}ms ({abs(pct):.0f}%)[/green]"
                else:
                    change = f"[red]↑ {diff:.1f}ms ({pct:.0f}%)[/red]"
            else:
                change = "[dim]new[/dim]"

            table.add_row(
                f"{result.target_name} latency",
                f"{result.avg_ms:.1f}ms",
                f"{prev_avg:.1f}ms" if prev_avg > 0 else "-",
                change
            )

            # Packet loss row (only if there was loss)
            if result.packet_loss > 0 or prev_loss > 0:
                if prev_loss > 0:
                    diff = result.packet_loss - prev_loss
                    if abs(diff) < 0.1:
                        change = "[dim]→ stable[/dim]"
                    elif diff < 0:
                        change = f"[green]↓ {abs(diff):.1f}%[/green]"
                    else:
                        change = f"[red]↑ {diff:.1f}%[/red]"
                else:
                    change = "[red]new loss[/red]" if result.packet_loss > 0 else "[dim]new[/dim]"

                table.add_row(
                    f"{result.target_name} loss",
                    f"{result.packet_loss:.1f}%",
                    f"{prev_loss:.1f}%" if prev_loss > 0 else "0%",
                    change
                )

    # Speedtest comparison
    prev_speed = previous.get("speedtest", {})
    if speedtest_result and speedtest_result.success and prev_speed and prev_speed.get("success"):
        prev_dl = prev_speed.get("download_mbps", 0)
        prev_ul = prev_speed.get("upload_mbps", 0)

        if prev_dl > 0:
            diff = speedtest_result.download_mbps - prev_dl
            pct = (diff / prev_dl) * 100
            if abs(pct) < 5:
                change = "[dim]→ stable[/dim]"
            elif diff > 0:
                change = f"[green]↑ {diff:.1f}Mbps ({pct:.0f}%)[/green]"
            else:
                change = f"[red]↓ {abs(diff):.1f}Mbps ({abs(pct):.0f}%)[/red]"

            table.add_row(
                "Download speed",
                f"{speedtest_result.download_mbps:.1f}Mbps",
                f"{prev_dl:.1f}Mbps",
                change
            )

        if prev_ul > 0:
            diff = speedtest_result.upload_mbps - prev_ul
            pct = (diff / prev_ul) * 100
            if abs(pct) < 5:
                change = "[dim]→ stable[/dim]"
            elif diff > 0:
                change = f"[green]↑ {diff:.1f}Mbps ({pct:.0f}%)[/green]"
            else:
                change = f"[red]↓ {abs(diff):.1f}Mbps ({abs(pct):.0f}%)[/red]"

            table.add_row(
                "Upload speed",
                f"{speedtest_result.upload_mbps:.1f}Mbps",
                f"{prev_ul:.1f}Mbps",
                change
            )

    console.print(table)
    console.print()
