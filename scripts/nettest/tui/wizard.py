"""Configuration wizard for guided setup."""

import os
from typing import Dict, Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich import box

from ..config import save_config, YAML_AVAILABLE


def run_wizard(config: Dict[str, Any], console: Console) -> Optional[str]:
    """
    Run the configuration wizard for step-by-step setup.

    Args:
        config: Current configuration dict
        console: Rich console for output

    Returns:
        Path to saved config file, or None if cancelled
    """
    console.print()
    console.print(Panel.fit(
        "[bold blue]Network Testing Tool[/bold blue]\n"
        "[bold]Configuration Wizard[/bold]\n\n"
        "[dim]This wizard will help you configure the network testing tool.\n"
        "Press Ctrl+C at any time to cancel.[/dim]",
        border_style="blue"
    ))
    console.print()

    try:
        # Step 1: Welcome and explain
        console.print("[bold cyan]Step 1: Test Targets[/bold cyan]")
        console.print("[dim]Configure which servers to test against.[/dim]")
        console.print()

        config = _configure_targets(config, console)

        # Step 2: Test parameters
        console.print()
        console.print("[bold cyan]Step 2: Test Parameters[/bold cyan]")
        console.print("[dim]Configure how tests are run.[/dim]")
        console.print()

        config = _configure_test_params(config, console)

        # Step 3: Thresholds
        console.print()
        console.print("[bold cyan]Step 3: Alert Thresholds[/bold cyan]")
        console.print("[dim]Define what's considered good, warning, or bad performance.[/dim]")
        console.print()

        config = _configure_thresholds(config, console)

        # Step 4: Output settings
        console.print()
        console.print("[bold cyan]Step 4: Output Settings[/bold cyan]")
        console.print("[dim]Configure where reports are saved.[/dim]")
        console.print()

        config = _configure_output(config, console)

        # Step 5: Logging
        console.print()
        console.print("[bold cyan]Step 5: Logging[/bold cyan]")
        console.print("[dim]Configure structured logging for Promtail/Loki.[/dim]")
        console.print()

        config = _configure_logging(config, console)

        # Step 6: Profiles
        console.print()
        console.print("[bold cyan]Step 6: Test Profiles[/bold cyan]")
        console.print("[dim]Create named configurations for different scenarios.[/dim]")
        console.print()

        config = _configure_profiles(config, console)

        # Step 7: Review and save
        console.print()
        console.print("[bold cyan]Step 7: Review & Save[/bold cyan]")
        console.print()

        _display_summary(config, console)

        if Confirm.ask("\nSave this configuration?", default=True):
            output_path = Prompt.ask(
                "Save config to",
                default="./nettest.yml"
            )

            if not YAML_AVAILABLE:
                console.print("[red]Error: pyyaml is required to save config files.[/red]")
                console.print("[dim]Install with: pip install pyyaml[/dim]")
                return None

            save_config(config, output_path)
            console.print(f"[green]Configuration saved to: {output_path}[/green]")
            console.print()
            console.print("[dim]Use this config with: nettest --config " + output_path + "[/dim]")
            return output_path
        else:
            console.print("[dim]Configuration not saved.[/dim]")
            return None

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Wizard cancelled.[/yellow]")
        return None


def _configure_targets(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure test targets."""
    current_targets = config.get("targets", {})

    console.print("Current targets:")
    for name, addr in current_targets.items():
        console.print(f"  [cyan]{name}[/cyan]: {addr}")

    if Confirm.ask("\nModify targets?", default=False):
        new_targets = {}

        # Keep defaults?
        if Confirm.ask("Keep default DNS servers (Google, Cloudflare)?", default=True):
            new_targets["Google DNS"] = "8.8.8.8"
            new_targets["Cloudflare DNS"] = "1.1.1.1"

        # Add custom targets
        console.print("\nAdd custom targets (empty name to finish):")
        while True:
            name = Prompt.ask("Target name", default="")
            if not name:
                break
            addr = Prompt.ask(f"Address for {name}")
            new_targets[name] = addr

        if new_targets:
            config["targets"] = new_targets

    return config


def _configure_test_params(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure test parameters."""
    tests = config.get("tests", {})

    console.print(f"Current ping count: {tests.get('ping_count', 10)}")
    console.print(f"Current MTR count: {tests.get('mtr_count', 10)}")
    console.print(f"Current expected speed: {tests.get('expected_speed', 100)} Mbps")

    if Confirm.ask("\nModify test parameters?", default=False):
        tests["ping_count"] = IntPrompt.ask(
            "Ping packet count",
            default=tests.get("ping_count", 10)
        )
        tests["mtr_count"] = IntPrompt.ask(
            "MTR packet count",
            default=tests.get("mtr_count", 10)
        )
        tests["expected_speed"] = IntPrompt.ask(
            "Expected download speed (Mbps)",
            default=tests.get("expected_speed", 100)
        )
        config["tests"] = tests

    return config


def _configure_thresholds(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure alert thresholds."""
    thresholds = config.get("thresholds", {})

    table = Table(title="Current Thresholds", box=box.ROUNDED)
    table.add_column("Metric")
    table.add_column("Good", justify="right", style="green")
    table.add_column("Warning", justify="right", style="yellow")

    table.add_row(
        "Latency (ms)",
        f"≤ {thresholds.get('latency', {}).get('good', 50)}",
        f"≤ {thresholds.get('latency', {}).get('warning', 100)}"
    )
    table.add_row(
        "Jitter (ms)",
        f"≤ {thresholds.get('jitter', {}).get('good', 15)}",
        f"≤ {thresholds.get('jitter', {}).get('warning', 30)}"
    )
    table.add_row(
        "Packet Loss (%)",
        f"≤ {thresholds.get('packet_loss', {}).get('good', 0)}",
        f"≤ {thresholds.get('packet_loss', {}).get('warning', 2)}"
    )
    table.add_row(
        "Download (% expected)",
        f"≥ {thresholds.get('download_pct', {}).get('good', 80)}",
        f"≥ {thresholds.get('download_pct', {}).get('warning', 50)}"
    )

    console.print(table)

    if Confirm.ask("\nModify thresholds?", default=False):
        console.print("\n[dim]Enter thresholds (values at or below 'good' are green, at or below 'warning' are yellow)[/dim]")

        thresholds["latency"] = {
            "good": IntPrompt.ask("Latency good (ms)", default=thresholds.get("latency", {}).get("good", 50)),
            "warning": IntPrompt.ask("Latency warning (ms)", default=thresholds.get("latency", {}).get("warning", 100)),
        }
        thresholds["jitter"] = {
            "good": IntPrompt.ask("Jitter good (ms)", default=thresholds.get("jitter", {}).get("good", 15)),
            "warning": IntPrompt.ask("Jitter warning (ms)", default=thresholds.get("jitter", {}).get("warning", 30)),
        }
        thresholds["packet_loss"] = {
            "good": IntPrompt.ask("Packet loss good (%)", default=thresholds.get("packet_loss", {}).get("good", 0)),
            "warning": IntPrompt.ask("Packet loss warning (%)", default=thresholds.get("packet_loss", {}).get("warning", 2)),
        }

        config["thresholds"] = thresholds

    return config


def _configure_output(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure output settings."""
    output = config.get("output", {})

    console.print(f"Current output directory: {output.get('directory', '~/Downloads')}")
    console.print(f"Auto-open browser: {output.get('open_browser', True)}")

    if Confirm.ask("\nModify output settings?", default=False):
        output["directory"] = Prompt.ask(
            "Report output directory",
            default=output.get("directory", os.path.expanduser("~/Downloads"))
        )
        output["open_browser"] = Confirm.ask(
            "Auto-open report in browser?",
            default=output.get("open_browser", True)
        )
        config["output"] = output

    return config


def _configure_logging(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure JSON logging."""
    logging = config.get("logging", {})

    console.print(f"Logging enabled: {logging.get('enabled', False)}")
    console.print(f"Log file: {logging.get('file', '~/Downloads/nettest.log')}")

    if Confirm.ask("\nConfigure JSON logging for Promtail/Loki?", default=False):
        logging["enabled"] = Confirm.ask("Enable JSON logging?", default=True)
        if logging["enabled"]:
            logging["file"] = Prompt.ask(
                "Log file path",
                default=logging.get("file", os.path.expanduser("~/Downloads/nettest.log"))
            )
        config["logging"] = logging

    return config


def _configure_profiles(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure test profiles."""
    profiles = config.get("profiles", {})

    console.print("Current profiles:")
    for name, settings in profiles.items():
        desc = settings.get("description", "No description")
        console.print(f"  [cyan]{name}[/cyan]: {desc}")

    if Confirm.ask("\nAdd a custom profile?", default=False):
        name = Prompt.ask("Profile name")
        profile = {
            "description": Prompt.ask("Description"),
            "ping_count": IntPrompt.ask("Ping count", default=5),
            "skip_speedtest": not Confirm.ask("Include speed test?", default=True),
            "skip_dns": not Confirm.ask("Include DNS tests?", default=True),
            "skip_mtr": not Confirm.ask("Include MTR route analysis?", default=True),
        }

        # Custom targets for this profile?
        if Confirm.ask("Add custom targets for this profile?", default=False):
            targets = {}
            while True:
                target_name = Prompt.ask("Target name (empty to finish)", default="")
                if not target_name:
                    break
                target_addr = Prompt.ask(f"Address for {target_name}")
                targets[target_name] = target_addr
            if targets:
                profile["targets"] = targets

        # Custom thresholds?
        if Confirm.ask("Add custom thresholds for this profile?", default=False):
            profile["thresholds"] = {
                "latency": {
                    "good": IntPrompt.ask("Latency good (ms)", default=50),
                    "warning": IntPrompt.ask("Latency warning (ms)", default=100),
                }
            }

        profiles[name] = profile
        config["profiles"] = profiles

    return config


def _display_summary(config: Dict[str, Any], console: Console) -> None:
    """Display configuration summary."""
    console.print(Panel("[bold]Configuration Summary[/bold]", border_style="green"))

    # Targets
    console.print("\n[bold]Targets:[/bold]")
    for name, addr in config.get("targets", {}).items():
        console.print(f"  {name}: {addr}")

    # Test parameters
    tests = config.get("tests", {})
    console.print("\n[bold]Test Parameters:[/bold]")
    console.print(f"  Ping count: {tests.get('ping_count', 10)}")
    console.print(f"  MTR count: {tests.get('mtr_count', 10)}")
    console.print(f"  Expected speed: {tests.get('expected_speed', 100)} Mbps")

    # Output
    output = config.get("output", {})
    console.print("\n[bold]Output:[/bold]")
    console.print(f"  Directory: {output.get('directory', '~/Downloads')}")
    console.print(f"  Auto-open browser: {output.get('open_browser', True)}")

    # Logging
    logging = config.get("logging", {})
    console.print("\n[bold]Logging:[/bold]")
    console.print(f"  Enabled: {logging.get('enabled', False)}")
    if logging.get("enabled"):
        console.print(f"  File: {logging.get('file')}")

    # Profiles
    profiles = config.get("profiles", {})
    if profiles:
        console.print("\n[bold]Profiles:[/bold]")
        for name in profiles:
            console.print(f"  - {name}")
