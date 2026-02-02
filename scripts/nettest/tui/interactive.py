"""Interactive menu mode for guided test selection."""

from typing import Optional, Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm


def run_interactive_mode(config: Dict[str, Any], console: Console) -> Optional[Dict[str, Any]]:
    """
    Run interactive menu mode.

    Args:
        config: Current configuration dict
        console: Rich console for output

    Returns:
        Dict with test settings, or None if user quits
    """
    console.print()
    console.print(Panel.fit(
        "[bold blue]Network Testing Tool[/bold blue]\n"
        "[dim]Interactive Mode[/dim]",
        border_style="blue"
    ))
    console.print()

    menu = """
[bold]Select test mode:[/bold]

  [cyan]1[/cyan]  Quick check      [dim]- Ping only, 3 packets (fast)[/dim]
  [cyan]2[/cyan]  Full diagnostic  [dim]- All tests, comprehensive analysis[/dim]
  [cyan]3[/cyan]  Speed test only  [dim]- Internet speed measurement[/dim]
  [cyan]4[/cyan]  Route analysis   [dim]- MTR traceroute to targets[/dim]
  [cyan]5[/cyan]  Custom test      [dim]- Configure your own test[/dim]
  [cyan]6[/cyan]  VoIP quality     [dim]- Test call quality (MOS score)[/dim]
  [cyan]7[/cyan]  ISP evidence     [dim]- Generate complaint documentation[/dim]
  [cyan]q[/cyan]  Quit

"""
    console.print(menu)

    choice = Prompt.ask(
        "Enter choice",
        choices=["1", "2", "3", "4", "5", "6", "7", "q"],
        default="2"
    )

    if choice == "q":
        console.print("[dim]Goodbye![/dim]")
        return None

    # Build test settings based on choice
    settings = {
        "skip_speedtest": False,
        "skip_dns": False,
        "skip_mtr": False,
        "ping_count": config["tests"]["ping_count"],
        "mtr_count": config["tests"]["mtr_count"],
        "targets": config["targets"],
        "bufferbloat": False,
        "export_csv": False,
        "generate_evidence": False,
        "video_services": False,
    }

    if choice == "1":
        # Quick check - ping only
        settings["skip_speedtest"] = True
        settings["skip_dns"] = True
        settings["skip_mtr"] = True
        settings["ping_count"] = 3
        console.print("[dim]Running quick check (ping only)...[/dim]")

    elif choice == "2":
        # Full diagnostic - ALL tests enabled
        settings["ping_count"] = 10
        settings["mtr_count"] = 10
        settings["bufferbloat"] = True
        settings["video_services"] = True
        console.print("[dim]Running full diagnostic (all tests)...[/dim]")

    elif choice == "3":
        # Speed test only
        settings["skip_dns"] = True
        settings["skip_mtr"] = True
        settings["ping_count"] = 3
        console.print("[dim]Running speed test...[/dim]")

    elif choice == "4":
        # Route analysis (MTR focus)
        settings["skip_speedtest"] = True
        settings["skip_dns"] = True
        settings["mtr_count"] = 10
        settings["ping_count"] = 3
        console.print("[dim]Running route analysis...[/dim]")

    elif choice == "5":
        # Custom test - ask for settings
        settings = _configure_custom_test(config, console)
        if settings is None:
            return None

    elif choice == "6":
        # VoIP quality test - ping focused
        settings["skip_speedtest"] = True
        settings["skip_dns"] = True
        settings["skip_mtr"] = True
        settings["ping_count"] = 20  # More samples for accurate MOS
        console.print("[dim]Running VoIP quality test (ping for MOS calculation)...[/dim]")

    elif choice == "7":
        # ISP evidence report - full test with evidence generation
        settings["ping_count"] = 10
        settings["mtr_count"] = 10
        settings["generate_evidence"] = True
        settings["export_csv"] = True
        console.print("[dim]Running full test for ISP evidence report...[/dim]")

    console.print()
    return settings


def _configure_custom_test(config: Dict[str, Any], console: Console) -> Optional[Dict[str, Any]]:
    """Configure a custom test interactively."""
    console.print("\n[bold]Custom Test Configuration[/bold]\n")

    settings = {
        "skip_speedtest": False,
        "skip_dns": False,
        "skip_mtr": False,
        "ping_count": config["tests"]["ping_count"],
        "mtr_count": config["tests"]["mtr_count"],
        "targets": config["targets"],
        "bufferbloat": False,
        "export_csv": False,
        "generate_evidence": False,
        "video_services": False,
    }

    # Ask for ping count
    ping_count_str = Prompt.ask(
        "Number of ping packets",
        default="5"
    )
    settings["ping_count"] = int(ping_count_str) if ping_count_str.isdigit() else 5

    # Ask which tests to run
    settings["skip_speedtest"] = not Confirm.ask("Run speed test?", default=True)
    settings["skip_dns"] = not Confirm.ask("Run DNS tests?", default=True)
    settings["skip_mtr"] = not Confirm.ask("Run route analysis (MTR)?", default=True)

    if not settings["skip_mtr"]:
        mtr_count_str = Prompt.ask(
            "Number of MTR packets",
            default="5"
        )
        settings["mtr_count"] = int(mtr_count_str) if mtr_count_str.isdigit() else 5

    # Ask for additional test options
    settings["bufferbloat"] = Confirm.ask("Run bufferbloat test?", default=False)
    settings["video_services"] = Confirm.ask("Test video services (Teams, Zoom, etc.)?", default=False)
    settings["export_csv"] = Confirm.ask("Export results to CSV?", default=False)

    # Ask for custom targets
    if Confirm.ask("Use custom targets?", default=False):
        targets_str = Prompt.ask(
            "Enter targets (comma-separated, format: Name:IP or just IP)",
            default="8.8.8.8,1.1.1.1"
        )
        custom_targets = {}
        for item in targets_str.split(","):
            item = item.strip()
            if ":" in item:
                name, target = item.split(":", 1)
                custom_targets[name.strip()] = target.strip()
            else:
                custom_targets[item] = item
        settings["targets"] = custom_targets

    console.print("[dim]Running custom test...[/dim]")
    return settings
