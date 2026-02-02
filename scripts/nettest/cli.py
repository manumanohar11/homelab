"""Command-line interface for the network testing tool."""

import argparse
import sys
import webbrowser
from typing import Optional

from rich.console import Console
from rich.panel import Panel

from . import __version__
from .config import load_config, apply_profile, list_profiles
from .diagnostics import diagnose_network
from .models import PortResult, HttpResult, VideoServiceResult
from .tests import (
    run_tests_with_progress,
    check_tcp_port,
    measure_http_latency,
    calculate_connection_score,
    calculate_mos_score,
    detect_bufferbloat,
    run_video_service_tests,
)
from .tests.ping import run_ping_test
from .output import display_terminal, generate_html, output_json, generate_isp_evidence, export_csv
from .tui import run_interactive_mode, run_monitor_mode
from .utils import check_dependencies, REQUIRED_TOOLS, JsonLogger
from .utils.history import save_history, load_history, show_history_comparison


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        description="Network Testing Tool - Run comprehensive network tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nettest --profile quick          Quick ping-only test
  nettest --profile full           Full comprehensive test
  nettest --format json            Machine-readable JSON output
  nettest --monitor --interval 30  Continuous monitoring mode
  nettest --wizard                 Configuration wizard
  nettest -I eth0 --profile quick  Test using specific interface
        """
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"nettest {__version__}"
    )

    # Configuration
    parser.add_argument(
        "--config",
        type=str,
        help="Path to YAML config file"
    )
    parser.add_argument(
        "--profile",
        type=str,
        help="Use a named test profile (e.g., quick, full, gaming)"
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available test profiles"
    )

    # Test parameters
    parser.add_argument(
        "--expected-speed",
        type=float,
        default=None,
        help="Expected download speed in Mbps"
    )
    parser.add_argument(
        "--ping-count",
        type=int,
        default=None,
        help="Number of ping packets to send"
    )
    parser.add_argument(
        "--targets",
        type=str,
        help="Custom targets (comma-separated), e.g., 'Google:8.8.8.8,CF:1.1.1.1'"
    )

    # Output options
    parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json", "html"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Directory for HTML report"
    )
    parser.add_argument(
        "--bufferbloat",
        action="store_true",
        help="Run bufferbloat detection test"
    )
    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="Export results to CSV files"
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't auto-open HTML report in browser"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress terminal output"
    )

    # Network options
    parser.add_argument(
        "--interface", "-I",
        type=str,
        help="Network interface to use (e.g., eth0, wlan0)"
    )
    parser.add_argument(
        "--list-interfaces",
        action="store_true",
        help="List available network interfaces"
    )
    parser.add_argument(
        "--ipv4", "-4",
        action="store_true",
        help="Force IPv4 only"
    )
    parser.add_argument(
        "--ipv6", "-6",
        action="store_true",
        help="Force IPv6 only"
    )

    # Additional tests
    parser.add_argument(
        "--check-ports",
        type=str,
        help="Test TCP ports (comma-separated), e.g., '80,443,22'"
    )
    parser.add_argument(
        "--check-http",
        type=str,
        help="Test HTTP/HTTPS latency (comma-separated URLs)"
    )

    # Modes
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive menu mode"
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Run in continuous monitoring mode"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Monitoring interval in seconds (default: 30)"
    )
    parser.add_argument(
        "--wizard",
        action="store_true",
        help="Run configuration wizard"
    )

    # Logging and history
    parser.add_argument(
        "--log-file",
        type=str,
        help="Path to JSON log file for Promtail/Loki"
    )
    parser.add_argument(
        "--history",
        type=str,
        metavar="FILE",
        help="Save results to history file and show comparison"
    )

    # Prometheus
    parser.add_argument(
        "--prometheus-port",
        type=int,
        help="Enable Prometheus metrics on specified port"
    )

    # Other options
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip pre-flight dependency check"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run ping and DNS tests in parallel"
    )
    parser.add_argument(
        "--video-services", "-vs",
        action="store_true",
        help="Test video conferencing service connectivity (Teams, Zoom, WhatsApp, Meet, Webex)"
    )

    return parser


def main() -> None:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    console = Console()

    # Determine if we should suppress terminal output
    suppress_output = args.quiet or args.format == "json"

    # Handle --list-interfaces
    if args.list_interfaces:
        _list_network_interfaces(console)
        sys.exit(0)

    # Load configuration
    config = load_config(config_path=args.config, quiet=suppress_output or args.interactive, console=console)

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
        _run_wizard(config, console)
        sys.exit(0)

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

    # Configure JSON logger
    log_file = args.log_file or (config["logging"]["file"] if config["logging"]["enabled"] else None)
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
    ip_version = None
    if args.ipv4 and args.ipv6:
        console.print("[yellow]Warning: Both --ipv4 and --ipv6 specified, using auto-detect[/yellow]")
    elif args.ipv4:
        ip_version = 4
        if not suppress_output:
            console.print("[dim]Forcing IPv4[/dim]")
    elif args.ipv6:
        ip_version = 6
        if not suppress_output:
            console.print("[dim]Forcing IPv6[/dim]")

    # Handle interactive mode
    run_bufferbloat = args.bufferbloat
    run_export_csv = args.export_csv
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
        generate_evidence_report = interactive_settings.get("generate_evidence", False)
    else:
        # Determine skip flags from profile
        profile_config = config.get("profiles", {}).get(args.profile, {}) if args.profile else {}
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
            ping_count=min(ping_count, 3),
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
            console.print(f"[red]Error: Required tools missing: {', '.join(missing_required)}[/red]")
            console.print("[dim]Install the missing tools and try again, or use --skip-check to proceed anyway.[/dim]")
            sys.exit(1)

    # Load previous history for comparison
    previous_history = None
    if args.history:
        previous_history = load_history(args.history)
        if previous_history and not suppress_output:
            console.print(f"[dim]Loaded previous results from {args.history}[/dim]")

    # Start Prometheus metrics server if requested
    if args.prometheus_port:
        try:
            from .output.prometheus import start_metrics_server
            start_metrics_server(args.prometheus_port)
            if not suppress_output:
                console.print(f"[dim]Prometheus metrics available at http://localhost:{args.prometheus_port}/metrics[/dim]")
        except ImportError:
            console.print("[yellow]Warning: prometheus-client not installed. Skipping metrics.[/yellow]")

    # Run all tests
    ping_results, speedtest_result, dns_results, mtr_results = run_tests_with_progress(
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
    )

    # Run optional TCP port tests
    port_results = []
    if args.check_ports:
        if not suppress_output:
            console.print("[dim]Running TCP port tests...[/dim]")
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

    # Run optional HTTP latency tests
    http_results = []
    if args.check_http:
        if not suppress_output:
            console.print("[dim]Running HTTP latency tests...[/dim]")
        for url in args.check_http.split(","):
            url = url.strip()
            result = measure_http_latency(url)
            http_results.append(result)

    # Run video service tests if requested
    video_service_results = []
    if args.video_services:
        if not suppress_output:
            console.print("[dim]Running video service connectivity tests...[/dim]")
        video_service_results = run_video_service_tests()

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
    voip_quality = None
    if ping_results:
        successful_pings = [p for p in ping_results if p.success]
        if successful_pings:
            avg_latency = sum(p.avg_ms for p in successful_pings) / len(successful_pings)
            avg_jitter = sum(p.jitter_ms for p in successful_pings) / len(successful_pings)
            avg_loss = sum(p.packet_loss for p in successful_pings) / len(successful_pings)
            voip_quality = calculate_mos_score(avg_latency, avg_jitter, avg_loss)

    # Generate ISP evidence
    isp_evidence = generate_isp_evidence(
        ping_results, speedtest_result, mtr_results, diagnostic, expected_speed
    )

    # Run bufferbloat test if requested
    bufferbloat_result = None
    if run_bufferbloat:
        if not suppress_output:
            console.print("[dim]Running bufferbloat test...[/dim]")
        bufferbloat_result = detect_bufferbloat(interface=args.interface)
        if bufferbloat_result.success:
            console.print(f"[green]Bufferbloat: Grade {bufferbloat_result.bloat_grade} ({bufferbloat_result.idle_latency_ms:.1f}ms baseline)[/green]")
        else:
            console.print(f"[yellow]Bufferbloat test failed: {bufferbloat_result.error}[/yellow]")

    # Update Prometheus metrics if enabled
    if args.prometheus_port:
        try:
            from .output.prometheus import update_metrics
            update_metrics(ping_results, speedtest_result, dns_results, mtr_results)
        except ImportError:
            pass

    # Handle output
    if args.format == "json":
        output_json(ping_results, speedtest_result, dns_results, mtr_results, diagnostic,
                    port_results=port_results, http_results=http_results)
    else:
        if not suppress_output:
            display_terminal(
                ping_results,
                speedtest_result,
                dns_results,
                mtr_results,
                expected_speed,
                diagnostic,
                thresholds,
                console,
                port_results=port_results,
                http_results=http_results,
            )

            # Show VoIP quality if calculated
            if voip_quality:
                mos_color = "green" if voip_quality.mos_score >= 4.0 else (
                    "yellow" if voip_quality.mos_score >= 3.6 else "red"
                )
                console.print(f"\n[bold]VoIP Quality:[/bold] [{mos_color}]MOS {voip_quality.mos_score:.1f}[/{mos_color}] ({voip_quality.quality})")
                if voip_quality.suitable_for:
                    console.print(f"[dim]Suitable for: {', '.join(voip_quality.suitable_for)}[/dim]")

            # Show ISP evidence summary if requested or issues found
            if generate_evidence_report and isp_evidence:
                has_issues = (
                    isp_evidence.speed_complaint or
                    isp_evidence.packet_loss_complaint or
                    isp_evidence.latency_complaint
                )
                if has_issues:
                    console.print(f"\n[bold red]ISP Evidence Summary:[/bold red]")
                    console.print(f"[bold]{isp_evidence.summary}[/bold]")
                    if isp_evidence.speed_complaint:
                        console.print(f"  [red]• {isp_evidence.speed_complaint}[/red]")
                    if isp_evidence.packet_loss_complaint:
                        console.print(f"  [red]• {isp_evidence.packet_loss_complaint}[/red]")
                    if isp_evidence.latency_complaint:
                        console.print(f"  [yellow]• {isp_evidence.latency_complaint}[/yellow]")
                    console.print("[dim]Full evidence available in HTML report.[/dim]")

        # Generate HTML report
        if not suppress_output:
            console.print("[dim]Generating HTML report...[/dim]")
        html_path = generate_html(
            ping_results,
            speedtest_result,
            dns_results,
            mtr_results,
            expected_speed,
            output_dir,
            diagnostic,
            thresholds,
            historical_data=previous_history,
            connection_score=connection_score,
            voip_quality=voip_quality,
            isp_evidence=isp_evidence,
            bufferbloat_result=bufferbloat_result,
            video_service_results=video_service_results,
        )
        if not suppress_output:
            console.print(f"[green]HTML report saved to: {html_path}[/green]")

        # Export CSV if requested
        if run_export_csv:
            csv_dir = export_csv(
                ping_results, speedtest_result, dns_results, mtr_results,
                output_dir=output_dir
            )
            if not suppress_output:
                console.print(f"[green]CSV files saved to: {csv_dir}[/green]")

        # Open in browser
        if open_browser and args.format != "html":
            if not suppress_output:
                console.print("[dim]Opening report in browser...[/dim]")
            webbrowser.open(f"file://{html_path}")

        if args.format == "html":
            print(html_path)

    # Show history comparison
    if args.history and previous_history and not suppress_output:
        show_history_comparison(ping_results, speedtest_result, previous_history, console)

    # Save to history
    if args.history:
        save_history(args.history, ping_results, speedtest_result, dns_results, console)
        if not suppress_output:
            console.print(f"[dim]Results saved to history: {args.history}[/dim]")

    json_logger.log_end(success=True)


def _list_network_interfaces(console: Console) -> None:
    """List available network interfaces."""
    try:
        from .utils.network import list_interfaces
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
        import os
        if os.path.exists("/sys/class/net"):
            console.print("[bold]Detected interfaces:[/bold]")
            for iface in os.listdir("/sys/class/net"):
                console.print(f"  [cyan]{iface}[/cyan]")


def _run_wizard(config: dict, console: Console) -> None:
    """Run the configuration wizard."""
    from .tui.wizard import run_wizard
    run_wizard(config, console)


if __name__ == "__main__":
    main()
