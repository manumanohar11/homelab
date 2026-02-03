"""Mode handler functions for the CLI."""

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console


def run_wizard_mode(config: dict, console: "Console") -> None:
    """Run the configuration wizard.

    Args:
        config: Current configuration dictionary
        console: Rich console for output
    """
    from ..tui.wizard import run_wizard
    run_wizard(config, console)


def run_monitor_mode(
    targets: dict,
    interval: int,
    ping_count: int,
    thresholds: dict,
    interface: str | None,
    ip_version: int | None,
    console: "Console",
    json_logger,
) -> None:
    """Run continuous monitoring mode.

    Args:
        targets: Dictionary of target names to addresses
        interval: Monitoring interval in seconds
        ping_count: Number of ping packets per test
        thresholds: Threshold configuration
        interface: Network interface to use
        ip_version: IP version (4 or 6) or None for auto
        console: Rich console for output
        json_logger: JSON logger instance
    """
    from ..tui import run_monitor_mode as _run_monitor

    _run_monitor(
        targets=targets,
        interval=interval,
        ping_count=min(ping_count, 3),
        thresholds=thresholds,
        interface=interface,
        ip_version=ip_version,
        console=console,
        json_logger=json_logger,
    )


def run_interactive_mode(config: dict, console: "Console") -> dict | None:
    """Run interactive menu mode.

    Args:
        config: Configuration dictionary
        console: Rich console for output

    Returns:
        Dictionary of interactive settings, or None if cancelled
    """
    from ..tui import run_interactive_mode as _run_interactive
    return _run_interactive(config, console)


def list_network_interfaces(console: "Console") -> None:
    """List available network interfaces.

    Args:
        console: Rich console for output
    """
    try:
        from ..utils.network import list_interfaces
        interfaces = list_interfaces()

        console.print("[bold]Available network interfaces:[/bold]")
        for iface in interfaces:
            status = "[green]UP[/green]" if iface.get("up") else "[red]DOWN[/red]"
            addrs = ", ".join(iface.get("addresses", [])) or "no address"
            console.print(f"  [cyan]{iface['name']}[/cyan] ({status}) - {addrs}")
    except ImportError:
        console.print("[yellow]Interface listing requires netifaces package.[/yellow]")
        console.print("[dim]Install with: pip install netifaces[/dim]")
        console.print()
        # Fallback to basic listing
        if os.path.exists("/sys/class/net"):
            console.print("[bold]Detected interfaces:[/bold]")
            for iface in os.listdir("/sys/class/net"):
                console.print(f"  [cyan]{iface}[/cyan]")
