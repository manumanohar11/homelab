"""Command-line interface package for the network testing tool."""

import argparse
import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

from .. import __version__
from ..config import load_config, apply_profile, list_profiles
from ..diagnostics import diagnose_network
from ..tests import (
    run_tests_with_progress,
    check_tcp_port,
    measure_http_latency,
    calculate_connection_score,
    calculate_mos_score,
)
from ..output import generate_isp_evidence
from ..utils import check_dependencies, REQUIRED_TOOLS, JsonLogger
from ..utils.history import save_history, load_history, show_history_comparison
from ..utils.storage import (
    store_result,
    get_last_result,
    get_trend_data,
    get_database_stats,
    export_to_csv as export_history_csv,
)

from .parser import create_parser as _create_parser
from .handlers import (
    run_wizard_mode,
    run_monitor_mode,
    run_interactive_mode,
    list_network_interfaces,
)
from .output import dispatch_output, handle_csv_export, handle_browser_open

if TYPE_CHECKING:
    pass

__all__ = ["main", "create_parser"]


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser.

    This is a backward-compatible wrapper that passes the version
    to the underlying parser factory.

    Returns:
        Configured ArgumentParser instance
    """
    return _create_parser(__version__)


def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    console = Console()

    # Handle --api flag first (starts REST API server)
    if args.api:
        from ..api import start_api_server
        start_api_server(port=args.api_port)
        sys.exit(0)

    # Determine if we should suppress terminal output
    suppress_output = args.quiet or args.format == "json"

    # Handle --list-interfaces
    if args.list_interfaces:
        list_network_interfaces(console)
        sys.exit(0)

    # Load configuration
    config = load_config(
        config_path=args.config,
        quiet=suppress_output or args.interactive,
        console=console,
    )

    # Handle --list-profiles
    if args.list_profiles:
        profiles = list_profiles(config)
        console.print("[bold]Available profiles:[/bold]")
        for name in profiles:
            profile = config["profiles"].get(name, {})
            desc = profile.get("description", "No description")
            console.print(f"  [cyan]{name}[/cyan] - {desc}")
        sys.exit(0)

    # Handle --wizard
    if args.wizard:
        run_wizard_mode(config, console)
        sys.exit(0)

    # Handle SQLite history utility commands (early exits)
    _handle_history_utility_commands(args, console)

    # Apply profile if specified
    if args.profile:
        if args.profile in list_profiles(config):
            config = apply_profile(config, args.profile)
            if not suppress_output:
                console.print(f"[dim]Using profile: {args.profile}[/dim]")
        else:
            console.print(f"[yellow]Warning: Profile '{args.profile}' not found[/yellow]")
            console.print(f"[dim]Available profiles: {', '.join(list_profiles(config))}[/dim]")

    # Apply CLI overrides to config
    _apply_cli_overrides(args, config, suppress_output, console)

    # Configure JSON logger
    log_file = args.log_file or (
        config["logging"]["file"] if config["logging"]["enabled"] else None
    )
    json_logger = JsonLogger(log_file=log_file, enabled=bool(log_file))
    if log_file and not suppress_output:
        console.print(f"[dim]Logging to: {log_file}[/dim]")

    # Extract config values
    targets = config["targets"]
    thresholds = config["thresholds"]
    ping_count = config["tests"]["ping_count"]
    mtr_count = config["tests"]["mtr_count"]
    expected_speed = config["tests"]["expected_speed"]
    output_dir = config["output"]["directory"]
    open_browser = config["output"]["open_browser"]

    # Determine IP version
    ip_version = _determine_ip_version(args, suppress_output, console)

    # Handle interactive mode
    run_bufferbloat = args.bufferbloat
    run_export_csv = args.export_csv
    run_video_services = args.video_services
    generate_evidence_report = False

    if args.interactive:
        interactive_settings = run_interactive_mode(config, console)
        if interactive_settings is None:
            sys.exit(0)

        # Apply interactive settings
        skip_speedtest = interactive_settings["skip_speedtest"]
        skip_dns = interactive_settings["skip_dns"]
        skip_mtr = interactive_settings["skip_mtr"]
        ping_count = interactive_settings["ping_count"]
        mtr_count = interactive_settings["mtr_count"]
        targets = interactive_settings["targets"]
        run_bufferbloat = interactive_settings.get("bufferbloat", False)
        run_export_csv = interactive_settings.get("export_csv", False)
        run_video_services = interactive_settings.get("video_services", False)
        generate_evidence_report = interactive_settings.get("generate_evidence", False)
    else:
        # Determine skip flags from profile
        profile_config = (
            config.get("profiles", {}).get(args.profile, {}) if args.profile else {}
        )
        skip_speedtest = profile_config.get("skip_speedtest", False)
        skip_dns = profile_config.get("skip_dns", False)
        skip_mtr = profile_config.get("skip_mtr", False)

        # Show header
        if not suppress_output:
            console.print()
            console.print(Panel.fit(
                "[bold blue]Network Testing Tool[/bold blue]\n"
                "[dim]Comprehensive network diagnostics[/dim]",
                border_style="blue"
            ))
            console.print()

    # Log session start
    json_logger.log_start(targets=list(targets.keys()), profile=args.profile)

    # Handle monitor mode
    if args.monitor:
        run_monitor_mode(
            targets=targets,
            interval=args.interval,
            ping_count=ping_count,
            thresholds=thresholds,
            interface=args.interface,
            ip_version=ip_version,
            console=console,
            json_logger=json_logger,
        )
        json_logger.log_end(success=True)
        sys.exit(0)

    # Pre-flight dependency check
    if not args.skip_check:
        tool_status = check_dependencies(quiet=suppress_output, console=console)

        missing_required = [
            tool for tool, available in tool_status.items()
            if not available and REQUIRED_TOOLS[tool]["required"]
        ]
        if missing_required:
            console.print(
                f"[red]Error: Required tools missing: {', '.join(missing_required)}[/red]"
            )
            console.print(
                "[dim]Install the missing tools and try again, "
                "or use --skip-check to proceed anyway.[/dim]"
            )
            sys.exit(1)

    # Load previous history for comparison (JSON or SQLite)
    previous_history = None
    using_sqlite_history = args.history_db or args.history_db_path
    if args.history:
        previous_history = load_history(args.history)
        if previous_history and not suppress_output:
            console.print(f"[dim]Loaded previous results from {args.history}[/dim]")
    elif using_sqlite_history:
        previous_history = get_last_result(db_path=args.history_db_path)
        if previous_history and not suppress_output:
            db_path = args.history_db_path or "~/.local/share/nettest/history.db"
            console.print(f"[dim]Loaded previous results from SQLite: {db_path}[/dim]")

    # Start Prometheus metrics server if requested
    _start_prometheus_server(args, suppress_output, console)

    # Run all tests
    (
        ping_results,
        speedtest_result,
        dns_results,
        mtr_results,
        bufferbloat_result,
        video_service_results,
    ) = run_tests_with_progress(
        targets,
        ping_count=ping_count,
        mtr_count=mtr_count,
        quiet=suppress_output,
        skip_speedtest=skip_speedtest,
        skip_dns=skip_dns,
        skip_mtr=skip_mtr,
        parallel=args.parallel,
        ip_version=ip_version,
        interface=args.interface,
        console=console,
        json_logger=json_logger,
        run_bufferbloat=run_bufferbloat,
        run_video_services=run_video_services,
    )

    # Run optional TCP port tests
    port_results = _run_port_tests(args, targets, suppress_output, console)

    # Run optional HTTP latency tests
    http_results = _run_http_tests(args, suppress_output, console)

    # Ensure we have a list if video tests weren't run
    if video_service_results is None:
        video_service_results = []

    # Run diagnostics
    diagnostic = diagnose_network(
        ping_results,
        speedtest_result,
        mtr_results,
        expected_speed,
        thresholds,
    )
    json_logger.log_diagnostic(diagnostic)

    # Calculate connection health score
    connection_score = calculate_connection_score(
        ping_results=ping_results,
        speedtest_result=speedtest_result,
        expected_speed=expected_speed,
    )

    # Calculate VoIP quality from ping results
    voip_quality = _calculate_voip_quality(ping_results)

    # Generate ISP evidence
    isp_evidence = generate_isp_evidence(
        ping_results, speedtest_result, mtr_results, diagnostic, expected_speed
    )

    # Display bufferbloat result summary if available
    if bufferbloat_result is not None and not suppress_output:
        if bufferbloat_result.success:
            console.print(
                f"[green]Bufferbloat: Grade {bufferbloat_result.bloat_grade} "
                f"({bufferbloat_result.idle_latency_ms:.1f}ms baseline)[/green]"
            )
        else:
            console.print(
                f"[yellow]Bufferbloat test failed: {bufferbloat_result.error}[/yellow]"
            )

    # Update Prometheus metrics if enabled
    _update_prometheus_metrics(args, ping_results, speedtest_result, dns_results, mtr_results)

    # Determine if simple mode is requested
    # --simple enables simple mode, --verbose disables it (default is verbose)
    simple_mode = getattr(args, 'simple', False) and not getattr(args, 'verbose', False)

    # Handle output
    html_path = dispatch_output(
        args=args,
        ping_results=ping_results,
        speedtest_result=speedtest_result,
        dns_results=dns_results,
        mtr_results=mtr_results,
        diagnostic=diagnostic,
        port_results=port_results,
        http_results=http_results,
        video_service_results=video_service_results,
        expected_speed=expected_speed,
        thresholds=thresholds,
        output_dir=output_dir,
        open_browser=open_browser,
        suppress_output=suppress_output,
        previous_history=previous_history,
        connection_score=connection_score,
        voip_quality=voip_quality,
        isp_evidence=isp_evidence,
        bufferbloat_result=bufferbloat_result,
        generate_evidence_report=generate_evidence_report,
        console=console,
        simple_mode=simple_mode,
    )

    # Export CSV if requested
    if run_export_csv and html_path:
        handle_csv_export(
            ping_results=ping_results,
            speedtest_result=speedtest_result,
            dns_results=dns_results,
            mtr_results=mtr_results,
            output_dir=output_dir,
            suppress_output=suppress_output,
            console=console,
        )

    # Open in browser
    if html_path:
        handle_browser_open(
            html_path=html_path,
            open_browser=open_browser,
            format_arg=args.format,
            suppress_output=suppress_output,
            console=console,
        )

    # Show history comparison
    if (args.history or using_sqlite_history) and previous_history and not suppress_output:
        show_history_comparison(ping_results, speedtest_result, previous_history, console)

    # Save to history (JSON format)
    if args.history:
        save_history(args.history, ping_results, speedtest_result, dns_results, console)
        if not suppress_output:
            console.print(f"[dim]Results saved to history: {args.history}[/dim]")

    # Save to SQLite history database
    if using_sqlite_history:
        _save_sqlite_history(
            args=args,
            ping_results=ping_results,
            speedtest_result=speedtest_result,
            dns_results=dns_results,
            mtr_results=mtr_results,
            diagnostic=diagnostic,
            port_results=port_results,
            http_results=http_results,
            video_service_results=video_service_results,
            connection_score=connection_score,
            suppress_output=suppress_output,
            console=console,
        )

    json_logger.log_end(success=True)


def _apply_cli_overrides(args, config: dict, suppress_output: bool, console: "Console") -> None:
    """Apply CLI argument overrides to configuration.

    Args:
        args: Parsed command-line arguments
        config: Configuration dictionary to modify
        suppress_output: Whether to suppress terminal output
        console: Rich console for output
    """
    if args.expected_speed is not None:
        config["tests"]["expected_speed"] = args.expected_speed
    if args.output is not None:
        config["output"]["directory"] = args.output
    if args.no_browser:
        config["output"]["open_browser"] = False
    if args.ping_count is not None:
        config["tests"]["ping_count"] = args.ping_count

    # Parse custom targets if provided
    if args.targets:
        custom_targets = {}
        for item in args.targets.split(","):
            item = item.strip()
            if ":" in item:
                name, target = item.split(":", 1)
                custom_targets[name.strip()] = target.strip()
            else:
                custom_targets[item] = item
        config["targets"] = custom_targets
        if not suppress_output:
            console.print(f"[dim]Using custom targets: {', '.join(custom_targets.keys())}[/dim]")


def _determine_ip_version(args, suppress_output: bool, console: "Console") -> int | None:
    """Determine IP version from arguments.

    Args:
        args: Parsed command-line arguments
        suppress_output: Whether to suppress terminal output
        console: Rich console for output

    Returns:
        IP version (4 or 6) or None for auto-detect
    """
    if args.ipv4 and args.ipv6:
        console.print("[yellow]Warning: Both --ipv4 and --ipv6 specified, using auto-detect[/yellow]")
        return None
    elif args.ipv4:
        if not suppress_output:
            console.print("[dim]Forcing IPv4[/dim]")
        return 4
    elif args.ipv6:
        if not suppress_output:
            console.print("[dim]Forcing IPv6[/dim]")
        return 6
    return None


def _start_prometheus_server(args, suppress_output: bool, console: "Console") -> None:
    """Start Prometheus metrics server if requested.

    Args:
        args: Parsed command-line arguments
        suppress_output: Whether to suppress terminal output
        console: Rich console for output
    """
    if not args.prometheus_port:
        return

    try:
        from ..output.prometheus import start_metrics_server
        start_metrics_server(args.prometheus_port)
        if not suppress_output:
            console.print(
                f"[dim]Prometheus metrics available at "
                f"http://localhost:{args.prometheus_port}/metrics[/dim]"
            )
    except ImportError:
        console.print("[yellow]Warning: prometheus-client not installed. Skipping metrics.[/yellow]")


def _update_prometheus_metrics(args, ping_results, speedtest_result, dns_results, mtr_results) -> None:
    """Update Prometheus metrics if enabled.

    Args:
        args: Parsed command-line arguments
        ping_results: List of ping test results
        speedtest_result: Speed test result
        dns_results: List of DNS test results
        mtr_results: List of MTR test results
    """
    if not args.prometheus_port:
        return

    try:
        from ..output.prometheus import update_metrics
        update_metrics(ping_results, speedtest_result, dns_results, mtr_results)
    except ImportError:
        pass


def _run_port_tests(args, targets: dict, suppress_output: bool, console: "Console") -> list:
    """Run optional TCP port tests.

    Args:
        args: Parsed command-line arguments
        targets: Dictionary of target names to addresses
        suppress_output: Whether to suppress terminal output
        console: Rich console for output

    Returns:
        List of port test results
    """
    if not args.check_ports:
        return []

    if not suppress_output:
        console.print("[dim]Running TCP port tests...[/dim]")

    port_results = []
    for item in args.check_ports.split(","):
        item = item.strip()
        if ":" in item:
            host, port_str = item.rsplit(":", 1)
            port = int(port_str)
        else:
            host = list(targets.values())[0] if targets else "8.8.8.8"
            port = int(item)
        result = check_tcp_port(host, port)
        port_results.append(result)

    return port_results


def _run_http_tests(args, suppress_output: bool, console: "Console") -> list:
    """Run optional HTTP latency tests.

    Args:
        args: Parsed command-line arguments
        suppress_output: Whether to suppress terminal output
        console: Rich console for output

    Returns:
        List of HTTP test results
    """
    if not args.check_http:
        return []

    if not suppress_output:
        console.print("[dim]Running HTTP latency tests...[/dim]")

    http_results = []
    for url in args.check_http.split(","):
        url = url.strip()
        result = measure_http_latency(url)
        http_results.append(result)

    return http_results


def _calculate_voip_quality(ping_results: list):
    """Calculate VoIP quality from ping results.

    Args:
        ping_results: List of ping test results

    Returns:
        VoIP quality metrics or None
    """
    if not ping_results:
        return None

    successful_pings = [p for p in ping_results if p.success]
    if not successful_pings:
        return None

    avg_latency = sum(p.avg_ms for p in successful_pings) / len(successful_pings)
    avg_jitter = sum(p.jitter_ms for p in successful_pings) / len(successful_pings)
    avg_loss = sum(p.packet_loss for p in successful_pings) / len(successful_pings)

    return calculate_mos_score(avg_latency, avg_jitter, avg_loss)


def _handle_history_utility_commands(args, console: "Console") -> None:
    """Handle SQLite history utility commands (stats, export, trends).

    These commands display information and exit without running tests.

    Args:
        args: Parsed command-line arguments
        console: Rich console for output
    """
    from rich.table import Table
    from rich import box

    db_path = args.history_db_path

    # Handle --history-stats
    if args.history_stats:
        try:
            stats = get_database_stats(db_path=db_path)
            console.print()
            console.print("[bold]SQLite History Database Statistics[/bold]")
            console.print()

            table = Table(box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", justify="right")

            table.add_row("Database path", stats["database_path"])
            table.add_row("Database size", f"{stats['database_size_mb']} MB")
            table.add_row("Total results", str(stats["total_results"]))
            table.add_row("Oldest result", stats["oldest_result"] or "N/A")
            table.add_row("Newest result", stats["newest_result"] or "N/A")

            console.print(table)

            if stats["by_profile"]:
                console.print()
                console.print("[bold]Results by Profile:[/bold]")
                profile_table = Table(box=box.ROUNDED)
                profile_table.add_column("Profile", style="cyan")
                profile_table.add_column("Count", justify="right")
                for profile, count in stats["by_profile"].items():
                    profile_table.add_row(profile, str(count))
                console.print(profile_table)

            console.print()
        except Exception as e:
            console.print(f"[red]Error reading database stats: {e}[/red]")
        sys.exit(0)

    # Handle --history-export
    if args.history_export:
        try:
            export_path = args.history_export
            days = args.history_retention
            export_history_csv(path=export_path, days=days, db_path=db_path)
            console.print(f"[green]History exported to: {export_path}[/green]")
            console.print(f"[dim]Exported last {days} days of data[/dim]")
        except Exception as e:
            console.print(f"[red]Error exporting history: {e}[/red]")
        sys.exit(0)

    # Handle --history-trends
    if args.history_trends is not None:
        try:
            days = args.history_trends
            trends = get_trend_data(days=days, db_path=db_path)

            console.print()
            console.print(f"[bold]Network Trends - Last {days} Days[/bold]")
            console.print(f"[dim]Tests in period: {trends['count']}[/dim]")
            console.print()

            if trends["count"] == 0:
                console.print("[yellow]No test results found in the specified period.[/yellow]")
                sys.exit(0)

            # Averages table
            table = Table(title="Average Metrics", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Average", justify="right")
            table.add_column("Trend", justify="center")

            avgs = trends["averages"]
            trend_dirs = trends.get("trends", {})

            def format_trend(trend: str) -> str:
                if trend == "improving":
                    return "[green]Improving[/green]"
                elif trend == "degrading":
                    return "[red]Degrading[/red]"
                elif trend == "stable":
                    return "[dim]Stable[/dim]"
                return "[dim]N/A[/dim]"

            if avgs.get("ping_ms") is not None:
                table.add_row(
                    "Ping (ms)",
                    f"{avgs['ping_ms']:.1f}",
                    format_trend(trend_dirs.get("ping", ""))
                )
            if avgs.get("jitter_ms") is not None:
                table.add_row(
                    "Jitter (ms)",
                    f"{avgs['jitter_ms']:.2f}",
                    format_trend(trend_dirs.get("jitter", ""))
                )
            if avgs.get("packet_loss_pct") is not None:
                table.add_row(
                    "Packet Loss (%)",
                    f"{avgs['packet_loss_pct']:.2f}",
                    format_trend(trend_dirs.get("packet_loss", ""))
                )
            if avgs.get("download_mbps") is not None:
                table.add_row(
                    "Download (Mbps)",
                    f"{avgs['download_mbps']:.1f}",
                    format_trend(trend_dirs.get("download", ""))
                )
            if avgs.get("upload_mbps") is not None:
                table.add_row(
                    "Upload (Mbps)",
                    f"{avgs['upload_mbps']:.1f}",
                    format_trend(trend_dirs.get("upload", ""))
                )
            if avgs.get("overall_score") is not None:
                table.add_row(
                    "Overall Score",
                    f"{avgs['overall_score']:.0f}",
                    format_trend(trend_dirs.get("score", ""))
                )

            console.print(table)

            # Min/Max ranges
            if trends.get("min_max"):
                console.print()
                console.print("[bold]Ranges:[/bold]")
                mm = trends["min_max"]
                if mm.get("ping_ms") and mm["ping_ms"][0] is not None:
                    console.print(f"  Ping: {mm['ping_ms'][0]:.1f} - {mm['ping_ms'][1]:.1f} ms")
                if mm.get("download_mbps") and mm["download_mbps"][0] is not None:
                    console.print(f"  Download: {mm['download_mbps'][0]:.1f} - {mm['download_mbps'][1]:.1f} Mbps")
                if mm.get("upload_mbps") and mm["upload_mbps"][0] is not None:
                    console.print(f"  Upload: {mm['upload_mbps'][0]:.1f} - {mm['upload_mbps'][1]:.1f} Mbps")

            console.print()
        except Exception as e:
            console.print(f"[red]Error getting trend data: {e}[/red]")
        sys.exit(0)


def _save_sqlite_history(
    args,
    ping_results: list,
    speedtest_result,
    dns_results: list,
    mtr_results: list,
    diagnostic,
    port_results: list,
    http_results: list,
    video_service_results: list,
    connection_score,
    suppress_output: bool,
    console: "Console",
) -> None:
    """Save test results to SQLite history database.

    Args:
        args: Parsed command-line arguments
        ping_results: List of ping test results
        speedtest_result: Speed test result
        dns_results: List of DNS test results
        mtr_results: List of MTR test results
        diagnostic: Diagnostic result
        port_results: List of port test results
        http_results: List of HTTP test results
        video_service_results: List of video service results
        connection_score: Connection score object
        suppress_output: Whether to suppress terminal output
        console: Rich console for output
    """
    from dataclasses import asdict
    from datetime import datetime

    try:
        # Build full results dictionary (similar to json_output.results_to_dict)
        results = {
            "timestamp": datetime.now().isoformat(),
            "ping_results": [asdict(r) for r in ping_results] if ping_results else [],
            "speedtest": asdict(speedtest_result) if speedtest_result else {},
            "dns_results": [asdict(r) for r in dns_results] if dns_results else [],
            "mtr_results": [
                {
                    "target": r.target,
                    "target_name": r.target_name,
                    "success": r.success,
                    "error": r.error,
                    "hops": [asdict(h) for h in r.hops],
                }
                for r in mtr_results
            ] if mtr_results else [],
            "diagnostic": asdict(diagnostic) if diagnostic else {},
        }

        # Add optional results
        if port_results:
            results["port_results"] = [asdict(r) for r in port_results]
        if http_results:
            results["http_results"] = [asdict(r) for r in http_results]
        if video_service_results:
            results["video_services"] = [asdict(r) for r in video_service_results]
        if connection_score:
            results["connection_score"] = asdict(connection_score)

        # Store in SQLite
        result_id = store_result(
            results=results,
            profile=args.profile,
            db_path=args.history_db_path,
            retention_days=args.history_retention,
            auto_cleanup=True,
        )

        if not suppress_output:
            db_path = args.history_db_path or "~/.local/share/nettest/history.db"
            console.print(f"[dim]Results saved to SQLite history (ID: {result_id}): {db_path}[/dim]")

    except Exception as e:
        if not suppress_output:
            console.print(f"[yellow]Warning: Could not save to SQLite history: {e}[/yellow]")
