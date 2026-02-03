"""Configuration wizard for guided setup."""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, Tuple, List

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt, FloatPrompt
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from ..config import save_config, YAML_AVAILABLE


def _quick_ping(target: str, timeout: int = 2) -> Tuple[str, bool, Optional[float]]:
    """
    Perform a quick single-packet ping to verify target reachability.

    Args:
        target: IP address or hostname to ping
        timeout: Timeout in seconds

    Returns:
        Tuple of (target, is_reachable, latency_ms)
    """
    cmd = ["ping", "-c", "1", "-W", str(timeout), target]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 2
        )
        if result.returncode == 0:
            # Extract latency from ping output
            import re
            time_match = re.search(r"time[=<](\d+\.?\d*)\s*ms", result.stdout)
            latency = float(time_match.group(1)) if time_match else None
            return (target, True, latency)
        return (target, False, None)
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return (target, False, None)


def _validate_targets_concurrent(
    targets: Dict[str, str],
    console: Console
) -> Dict[str, Tuple[bool, Optional[float]]]:
    """
    Validate multiple targets concurrently using threading.

    Args:
        targets: Dict of name -> address
        console: Rich console for output

    Returns:
        Dict of address -> (is_reachable, latency_ms)
    """
    results: Dict[str, Tuple[bool, Optional[float]]] = {}

    if not targets:
        return results

    addresses = list(targets.values())

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Testing target reachability...", total=len(addresses))

        with ThreadPoolExecutor(max_workers=min(10, len(addresses))) as executor:
            futures = {executor.submit(_quick_ping, addr): addr for addr in addresses}

            for future in as_completed(futures):
                addr, reachable, latency = future.result()
                results[addr] = (reachable, latency)
                progress.advance(task)

    return results


def _display_reachability_results(
    targets: Dict[str, str],
    results: Dict[str, Tuple[bool, Optional[float]]],
    console: Console
) -> None:
    """Display reachability test results in a table."""
    table = Table(title="Target Reachability", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Address")
    table.add_column("Status", justify="center")
    table.add_column("Latency", justify="right")

    for name, addr in targets.items():
        reachable, latency = results.get(addr, (False, None))
        if reachable:
            status = "[green]Reachable[/green]"
            latency_str = f"{latency:.1f} ms" if latency else "-"
        else:
            status = "[yellow]Unreachable[/yellow]"
            latency_str = "-"
        table.add_row(name, addr, status, latency_str)

    console.print(table)


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
    console.print(Panel(
        "[bold blue]Network Testing Tool[/bold blue]\n"
        "[bold]Configuration Wizard[/bold]\n\n"
        "[dim]This wizard will help you configure the network testing tool.\n"
        "Press Ctrl+C at any time to cancel.[/dim]",
        border_style="blue",
        padding=(1, 2)
    ))
    console.print()

    try:
        # Step 1: ISP Speed
        console.print(Panel("[bold cyan]Step 1: ISP Information[/bold cyan]", box=box.ROUNDED))
        console.print("[dim]Configure your expected internet speed for accurate scoring.[/dim]")
        console.print()

        config = _configure_isp_speed(config, console)

        # Step 2: Test Targets
        console.print()
        console.print(Panel("[bold cyan]Step 2: Test Targets[/bold cyan]", box=box.ROUNDED))
        console.print("[dim]Configure which servers to test against.[/dim]")
        console.print()

        config = _configure_targets(config, console)

        # Step 3: Test parameters
        console.print()
        console.print(Panel("[bold cyan]Step 3: Test Parameters[/bold cyan]", box=box.ROUNDED))
        console.print("[dim]Configure how tests are run.[/dim]")
        console.print()

        config = _configure_test_params(config, console)

        # Step 4: Thresholds
        console.print()
        console.print(Panel("[bold cyan]Step 4: Alert Thresholds[/bold cyan]", box=box.ROUNDED))
        console.print("[dim]Define what's considered good, warning, or bad performance.[/dim]")
        console.print()

        config = _configure_thresholds(config, console)

        # Step 5: Output settings
        console.print()
        console.print(Panel("[bold cyan]Step 5: Output Settings[/bold cyan]", box=box.ROUNDED))
        console.print("[dim]Configure where reports are saved.[/dim]")
        console.print()

        config = _configure_output(config, console)

        # Step 6: Logging
        console.print()
        console.print(Panel("[bold cyan]Step 6: Logging[/bold cyan]", box=box.ROUNDED))
        console.print("[dim]Configure structured logging for Promtail/Loki.[/dim]")
        console.print()

        config = _configure_logging(config, console)

        # Step 7: Quality Tests
        console.print()
        console.print(Panel("[bold cyan]Step 7: Quality Tests[/bold cyan]", box=box.ROUNDED))
        console.print("[dim]Configure bufferbloat and VoIP quality testing.[/dim]")
        console.print()

        config = _configure_quality_tests(config, console)

        # Step 8: Export Options
        console.print()
        console.print(Panel("[bold cyan]Step 8: Export Options[/bold cyan]", box=box.ROUNDED))
        console.print("[dim]Configure default export formats.[/dim]")
        console.print()

        config = _configure_exports(config, console)

        # Step 9: Profiles
        console.print()
        console.print(Panel("[bold cyan]Step 9: Test Profiles[/bold cyan]", box=box.ROUNDED))
        console.print("[dim]Create named configurations for different scenarios.[/dim]")
        console.print()

        config = _configure_profiles(config, console)

        # Step 10: Review and save
        console.print()
        console.print(Panel("[bold cyan]Step 10: Review & Save[/bold cyan]", box=box.ROUNDED))
        console.print()

        _display_summary(config, console)

        if Confirm.ask("\nSave this configuration?", default=True):
            return _save_config_with_options(config, console)
        else:
            console.print("[dim]Configuration not saved.[/dim]")
            return None

    except KeyboardInterrupt:
        console.print()
        console.print(Panel(
            "[yellow]Wizard cancelled.[/yellow]\n\n"
            "[dim]Your configuration was not saved.[/dim]",
            border_style="yellow"
        ))
        return None


def _configure_isp_speed(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure ISP expected speed."""
    tests = config.get("tests", {})
    current_speed = tests.get("expected_speed", 100)

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    table.add_column("Setting", style="bold")
    table.add_column("Value", style="cyan")
    table.add_row("Current expected download speed", f"{current_speed} Mbps")
    console.print(table)
    console.print()

    console.print("[dim]This value is used to score your speed test results.[/dim]")
    console.print("[dim]Common values: 25 (basic), 100 (standard), 500 (fast), 1000 (gigabit)[/dim]")
    console.print()

    if Confirm.ask("Set your ISP's expected download speed?", default=True):
        speed = FloatPrompt.ask(
            "What is your expected download speed from your ISP? (in Mbps)",
            default=float(current_speed)
        )
        if speed <= 0:
            console.print("[yellow]Speed must be greater than 0. Using default of 100 Mbps.[/yellow]")
            speed = 100.0
        tests["expected_speed"] = speed
        config["tests"] = tests
        console.print(f"[green]Expected speed set to {speed} Mbps[/green]")

    return config


def _configure_targets(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure test targets with reachability validation."""
    current_targets = config.get("targets", {})

    table = Table(title="Current Targets", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Address")
    for name, addr in current_targets.items():
        table.add_row(name, addr)
    console.print(table)
    console.print()

    if Confirm.ask("Modify targets?", default=False):
        new_targets: Dict[str, str] = {}

        # Keep defaults?
        if Confirm.ask("Keep default DNS servers (Google, Cloudflare)?", default=True):
            new_targets["Google DNS"] = "8.8.8.8"
            new_targets["Cloudflare DNS"] = "1.1.1.1"

        # Add custom targets
        console.print()
        console.print(Panel(
            "[bold]Add Custom Targets[/bold]\n\n"
            "[dim]Enter target name and address. Leave name empty to finish.\n"
            "Each target will be validated for reachability.[/dim]",
            box=box.ROUNDED
        ))

        custom_targets: Dict[str, str] = {}
        while True:
            name = Prompt.ask("Target name (empty to finish)", default="")
            if not name:
                break

            addr = Prompt.ask(f"Address for '{name}'")
            if not addr:
                console.print("[yellow]Address cannot be empty. Skipping this target.[/yellow]")
                continue

            custom_targets[name] = addr

        # Validate custom targets if any were added
        if custom_targets:
            console.print()
            results = _validate_targets_concurrent(custom_targets, console)
            _display_reachability_results(custom_targets, results, console)

            # Check for unreachable targets
            unreachable = [name for name, addr in custom_targets.items()
                          if not results.get(addr, (False, None))[0]]

            if unreachable:
                console.print()
                console.print(Panel(
                    f"[yellow]Warning: {len(unreachable)} target(s) are unreachable:[/yellow]\n" +
                    "\n".join(f"  - {name}" for name in unreachable) +
                    "\n\n[dim]This could be due to ICMP being blocked or the host being down.\n"
                    "You can still add these targets to your configuration.[/dim]",
                    border_style="yellow"
                ))

            if Confirm.ask("Add these custom targets to configuration?", default=True):
                new_targets.update(custom_targets)

        if new_targets:
            config["targets"] = new_targets
        else:
            console.print("[yellow]No targets configured. Keeping current targets.[/yellow]")

    return config


def _configure_test_params(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure test parameters."""
    tests = config.get("tests", {})

    table = Table(title="Current Test Parameters", box=box.ROUNDED)
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("Ping packet count", str(tests.get("ping_count", 10)))
    table.add_row("MTR packet count", str(tests.get("mtr_count", 10)))
    table.add_row("Expected download speed", f"{tests.get('expected_speed', 100)} Mbps")
    console.print(table)
    console.print()

    if Confirm.ask("Modify test parameters?", default=False):
        ping_count = IntPrompt.ask(
            "Ping packet count (3-100)",
            default=tests.get("ping_count", 10)
        )
        if ping_count < 3:
            console.print("[yellow]Ping count must be at least 3. Using 3.[/yellow]")
            ping_count = 3
        elif ping_count > 100:
            console.print("[yellow]Ping count capped at 100.[/yellow]")
            ping_count = 100
        tests["ping_count"] = ping_count

        mtr_count = IntPrompt.ask(
            "MTR packet count (3-100)",
            default=tests.get("mtr_count", 10)
        )
        if mtr_count < 3:
            console.print("[yellow]MTR count must be at least 3. Using 3.[/yellow]")
            mtr_count = 3
        elif mtr_count > 100:
            console.print("[yellow]MTR count capped at 100.[/yellow]")
            mtr_count = 100
        tests["mtr_count"] = mtr_count

        config["tests"] = tests

    return config


def _configure_thresholds(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure alert thresholds."""
    thresholds = config.get("thresholds", {})

    table = Table(title="Current Thresholds", box=box.ROUNDED)
    table.add_column("Metric")
    table.add_column("Good", justify="right", style="green")
    table.add_column("Warning", justify="right", style="yellow")
    table.add_column("Above Warning", justify="center", style="red")

    table.add_row(
        "Latency (ms)",
        f"<= {thresholds.get('latency', {}).get('good', 50)}",
        f"<= {thresholds.get('latency', {}).get('warning', 100)}",
        "Bad"
    )
    table.add_row(
        "Jitter (ms)",
        f"<= {thresholds.get('jitter', {}).get('good', 15)}",
        f"<= {thresholds.get('jitter', {}).get('warning', 30)}",
        "Bad"
    )
    table.add_row(
        "Packet Loss (%)",
        f"<= {thresholds.get('packet_loss', {}).get('good', 0)}",
        f"<= {thresholds.get('packet_loss', {}).get('warning', 2)}",
        "Bad"
    )
    table.add_row(
        "Download (% expected)",
        f">= {thresholds.get('download_pct', {}).get('good', 80)}",
        f">= {thresholds.get('download_pct', {}).get('warning', 50)}",
        "Bad"
    )

    console.print(table)
    console.print()

    if Confirm.ask("Modify thresholds?", default=False):
        console.print()
        console.print(Panel(
            "[bold]Threshold Configuration[/bold]\n\n"
            "[dim]Values at or below 'good' are shown in green.\n"
            "Values at or below 'warning' are shown in yellow.\n"
            "Values above 'warning' are shown in red.[/dim]",
            box=box.ROUNDED
        ))
        console.print()

        latency_good = IntPrompt.ask(
            "Latency good threshold (ms)",
            default=thresholds.get("latency", {}).get("good", 50)
        )
        latency_warning = IntPrompt.ask(
            "Latency warning threshold (ms)",
            default=thresholds.get("latency", {}).get("warning", 100)
        )
        if latency_warning <= latency_good:
            console.print("[yellow]Warning must be greater than good. Adjusting.[/yellow]")
            latency_warning = latency_good + 50

        thresholds["latency"] = {"good": latency_good, "warning": latency_warning}

        jitter_good = IntPrompt.ask(
            "Jitter good threshold (ms)",
            default=thresholds.get("jitter", {}).get("good", 15)
        )
        jitter_warning = IntPrompt.ask(
            "Jitter warning threshold (ms)",
            default=thresholds.get("jitter", {}).get("warning", 30)
        )
        if jitter_warning <= jitter_good:
            console.print("[yellow]Warning must be greater than good. Adjusting.[/yellow]")
            jitter_warning = jitter_good + 15

        thresholds["jitter"] = {"good": jitter_good, "warning": jitter_warning}

        loss_good = IntPrompt.ask(
            "Packet loss good threshold (%)",
            default=thresholds.get("packet_loss", {}).get("good", 0)
        )
        loss_warning = IntPrompt.ask(
            "Packet loss warning threshold (%)",
            default=thresholds.get("packet_loss", {}).get("warning", 2)
        )
        if loss_warning <= loss_good:
            console.print("[yellow]Warning must be greater than good. Adjusting.[/yellow]")
            loss_warning = loss_good + 2

        thresholds["packet_loss"] = {"good": loss_good, "warning": loss_warning}

        config["thresholds"] = thresholds

    return config


def _configure_output(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure output settings."""
    output = config.get("output", {})

    table = Table(title="Current Output Settings", box=box.ROUNDED)
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_row("Output directory", output.get("directory", "~/Downloads"))
    table.add_row("Auto-open browser", str(output.get("open_browser", True)))
    console.print(table)
    console.print()

    if Confirm.ask("Modify output settings?", default=False):
        directory = Prompt.ask(
            "Report output directory",
            default=output.get("directory", os.path.expanduser("~/Downloads"))
        )
        # Expand user path
        directory = os.path.expanduser(directory)
        output["directory"] = directory

        output["open_browser"] = Confirm.ask(
            "Auto-open report in browser?",
            default=output.get("open_browser", True)
        )
        config["output"] = output

    return config


def _configure_logging(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure JSON logging."""
    logging = config.get("logging", {})

    table = Table(title="Current Logging Settings", box=box.ROUNDED)
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_row("Logging enabled", str(logging.get("enabled", False)))
    table.add_row("Log file", logging.get("file", "~/Downloads/nettest.log"))
    console.print(table)
    console.print()

    if Confirm.ask("Configure JSON logging for Promtail/Loki?", default=False):
        logging["enabled"] = Confirm.ask("Enable JSON logging?", default=True)
        if logging["enabled"]:
            log_file = Prompt.ask(
                "Log file path",
                default=logging.get("file", os.path.expanduser("~/Downloads/nettest.log"))
            )
            logging["file"] = os.path.expanduser(log_file)
        config["logging"] = logging

    return config


def _configure_quality_tests(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure quality test settings."""
    quality = config.get("quality_tests", {})

    table = Table(title="Current Quality Test Settings", box=box.ROUNDED)
    table.add_column("Test", style="cyan")
    table.add_column("Enabled", justify="center")
    table.add_column("Description", style="dim")
    table.add_row(
        "Bufferbloat detection",
        "[green]Yes[/green]" if quality.get("bufferbloat", False) else "[red]No[/red]",
        "Detects latency spikes under load"
    )
    table.add_row(
        "VoIP quality (MOS)",
        "[green]Yes[/green]" if quality.get("voip_quality", True) else "[red]No[/red]",
        "Mean Opinion Score for call quality"
    )
    console.print(table)
    console.print()

    if Confirm.ask("Configure quality tests?", default=False):
        quality["bufferbloat"] = Confirm.ask(
            "Enable bufferbloat detection?",
            default=quality.get("bufferbloat", False)
        )
        quality["voip_quality"] = Confirm.ask(
            "Enable VoIP quality calculation (MOS score)?",
            default=quality.get("voip_quality", True)
        )
        config["quality_tests"] = quality

    return config


def _configure_exports(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure export options."""
    exports = config.get("exports", {})

    table = Table(title="Current Export Settings", box=box.ROUNDED)
    table.add_column("Export", style="cyan")
    table.add_column("Enabled", justify="center")
    table.add_row(
        "CSV export",
        "[green]Yes[/green]" if exports.get("csv", False) else "[red]No[/red]"
    )
    table.add_row(
        "Auto-generate ISP evidence",
        "[green]Yes[/green]" if exports.get("isp_evidence", True) else "[red]No[/red]"
    )
    console.print(table)
    console.print()

    if Confirm.ask("Configure export options?", default=False):
        exports["csv"] = Confirm.ask(
            "Enable CSV export by default?",
            default=exports.get("csv", False)
        )
        exports["isp_evidence"] = Confirm.ask(
            "Auto-generate ISP evidence when issues detected?",
            default=exports.get("isp_evidence", True)
        )
        config["exports"] = exports

    return config


def _configure_profiles(config: Dict[str, Any], console: Console) -> Dict[str, Any]:
    """Configure test profiles."""
    profiles = config.get("profiles", {})

    if profiles:
        table = Table(title="Current Profiles", box=box.ROUNDED)
        table.add_column("Profile", style="cyan")
        table.add_column("Description")
        for name, settings in profiles.items():
            desc = settings.get("description", "No description")
            table.add_row(name, desc)
        console.print(table)
    else:
        console.print("[dim]No custom profiles configured.[/dim]")
    console.print()

    if Confirm.ask("Add a custom profile?", default=False):
        name = Prompt.ask("Profile name")
        if not name:
            console.print("[yellow]Profile name cannot be empty. Skipping.[/yellow]")
            return config

        profile: Dict[str, Any] = {
            "description": Prompt.ask("Description"),
            "ping_count": IntPrompt.ask("Ping count", default=5),
            "skip_speedtest": not Confirm.ask("Include speed test?", default=True),
            "skip_dns": not Confirm.ask("Include DNS tests?", default=True),
            "skip_mtr": not Confirm.ask("Include MTR route analysis?", default=True),
        }

        # Custom targets for this profile?
        if Confirm.ask("Add custom targets for this profile?", default=False):
            targets: Dict[str, str] = {}
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
    """Display configuration summary using Rich panels and tables."""
    console.print(Panel(
        "[bold green]Configuration Summary[/bold green]",
        border_style="green"
    ))

    # Targets table
    targets = config.get("targets", {})
    if targets:
        target_table = Table(title="Test Targets", box=box.ROUNDED)
        target_table.add_column("Name", style="cyan")
        target_table.add_column("Address")
        for name, addr in targets.items():
            target_table.add_row(name, addr)
        console.print(target_table)
        console.print()

    # Test parameters table
    tests = config.get("tests", {})
    param_table = Table(title="Test Parameters", box=box.ROUNDED)
    param_table.add_column("Parameter", style="cyan")
    param_table.add_column("Value", justify="right")
    param_table.add_row("Ping count", str(tests.get("ping_count", 10)))
    param_table.add_row("MTR count", str(tests.get("mtr_count", 10)))
    param_table.add_row("Expected speed", f"{tests.get('expected_speed', 100)} Mbps")
    console.print(param_table)
    console.print()

    # Thresholds table
    thresholds = config.get("thresholds", {})
    thresh_table = Table(title="Alert Thresholds", box=box.ROUNDED)
    thresh_table.add_column("Metric")
    thresh_table.add_column("Good", justify="right", style="green")
    thresh_table.add_column("Warning", justify="right", style="yellow")
    thresh_table.add_row(
        "Latency (ms)",
        f"<= {thresholds.get('latency', {}).get('good', 50)}",
        f"<= {thresholds.get('latency', {}).get('warning', 100)}"
    )
    thresh_table.add_row(
        "Jitter (ms)",
        f"<= {thresholds.get('jitter', {}).get('good', 15)}",
        f"<= {thresholds.get('jitter', {}).get('warning', 30)}"
    )
    thresh_table.add_row(
        "Packet Loss (%)",
        f"<= {thresholds.get('packet_loss', {}).get('good', 0)}",
        f"<= {thresholds.get('packet_loss', {}).get('warning', 2)}"
    )
    console.print(thresh_table)
    console.print()

    # Settings panel
    output = config.get("output", {})
    logging = config.get("logging", {})
    quality = config.get("quality_tests", {})
    exports = config.get("exports", {})

    settings_table = Table(title="Other Settings", box=box.ROUNDED)
    settings_table.add_column("Category", style="cyan")
    settings_table.add_column("Setting")
    settings_table.add_column("Value")

    settings_table.add_row("Output", "Directory", output.get("directory", "~/Downloads"))
    settings_table.add_row("Output", "Auto-open browser", str(output.get("open_browser", True)))
    settings_table.add_row("Logging", "Enabled", str(logging.get("enabled", False)))
    if logging.get("enabled"):
        settings_table.add_row("Logging", "File", logging.get("file", "-"))
    settings_table.add_row("Quality", "Bufferbloat detection", str(quality.get("bufferbloat", False)))
    settings_table.add_row("Quality", "VoIP quality (MOS)", str(quality.get("voip_quality", True)))
    settings_table.add_row("Exports", "CSV export", str(exports.get("csv", False)))
    settings_table.add_row("Exports", "ISP evidence", str(exports.get("isp_evidence", True)))

    console.print(settings_table)
    console.print()

    # Profiles
    profiles = config.get("profiles", {})
    if profiles:
        profile_table = Table(title="Test Profiles", box=box.ROUNDED)
        profile_table.add_column("Profile", style="cyan")
        profile_table.add_column("Description")
        for name, settings in profiles.items():
            profile_table.add_row(name, settings.get("description", "-"))
        console.print(profile_table)
        console.print()


def _save_config_with_options(config: Dict[str, Any], console: Console) -> Optional[str]:
    """
    Save configuration with multiple destination options.

    Args:
        config: Configuration dict to save
        console: Rich console for output

    Returns:
        Path to saved config file, or None if cancelled
    """
    if not YAML_AVAILABLE:
        console.print(Panel(
            "[red]Error: pyyaml is required to save config files.[/red]\n\n"
            "[dim]Install with: pip install pyyaml[/dim]",
            border_style="red"
        ))
        return None

    console.print()
    console.print(Panel(
        "[bold]Save Configuration[/bold]\n\n"
        "Choose where to save your configuration file:",
        box=box.ROUNDED
    ))
    console.print()

    # Define save options
    options = [
        ("1", "./nettest.yml", "Current directory (project-specific)"),
        ("2", os.path.expanduser("~/.config/nettest/config.yml"), "User config directory (global)"),
        ("3", None, "Custom path"),
    ]

    option_table = Table(box=box.ROUNDED, show_header=False)
    option_table.add_column("Option", style="bold cyan")
    option_table.add_column("Path")
    option_table.add_column("Description", style="dim")
    for opt, path, desc in options:
        display_path = path if path else "(enter your path)"
        option_table.add_row(f"[{opt}]", display_path, desc)
    console.print(option_table)
    console.print()

    choice = Prompt.ask(
        "Select option",
        choices=["1", "2", "3"],
        default="1"
    )

    if choice == "1":
        output_path = "./nettest.yml"
    elif choice == "2":
        output_path = os.path.expanduser("~/.config/nettest/config.yml")
    else:
        output_path = Prompt.ask("Enter custom path")
        if not output_path:
            console.print("[yellow]No path provided. Using ./nettest.yml[/yellow]")
            output_path = "./nettest.yml"

    # Expand user path and make absolute
    output_path = os.path.expanduser(output_path)

    # Ensure parent directory exists
    parent_dir = os.path.dirname(os.path.abspath(output_path))
    if parent_dir and not os.path.exists(parent_dir):
        if Confirm.ask(f"Directory '{parent_dir}' does not exist. Create it?", default=True):
            try:
                os.makedirs(parent_dir, exist_ok=True)
                console.print(f"[green]Created directory: {parent_dir}[/green]")
            except OSError as e:
                console.print(Panel(
                    f"[red]Error creating directory: {e}[/red]",
                    border_style="red"
                ))
                return None
        else:
            console.print("[yellow]Cannot save without creating directory.[/yellow]")
            return None

    # Check if file already exists
    if os.path.exists(output_path):
        if not Confirm.ask(f"File '{output_path}' already exists. Overwrite?", default=False):
            console.print("[dim]Configuration not saved.[/dim]")
            return None

    try:
        save_config(config, output_path)

        # Get absolute path for display
        abs_path = os.path.abspath(output_path)

        console.print()
        console.print(Panel(
            f"[bold green]Configuration saved successfully![/bold green]\n\n"
            f"[cyan]Path:[/cyan] {abs_path}\n\n"
            f"[dim]Use this config with:[/dim]\n"
            f"  python -m nettest --config {output_path}\n\n"
            f"[dim]Or place it in the search path for auto-detection:[/dim]\n"
            f"  ./nettest.yml\n"
            f"  ~/.config/nettest/config.yml",
            border_style="green"
        ))

        return output_path

    except Exception as e:
        console.print(Panel(
            f"[red]Error saving configuration: {e}[/red]",
            border_style="red"
        ))
        return None
