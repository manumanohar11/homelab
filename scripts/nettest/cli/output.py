"""Output dispatching functions for the CLI."""

import webbrowser
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Console


def dispatch_output(
    args,
    ping_results: list,
    speedtest_result,
    dns_results: list,
    mtr_results: list,
    diagnostic,
    port_results: list,
    http_results: list,
    video_service_results: list,
    expected_speed: float,
    thresholds: dict,
    output_dir: str,
    open_browser: bool,
    suppress_output: bool,
    previous_history: dict | None,
    connection_score,
    voip_quality,
    isp_evidence,
    bufferbloat_result,
    generate_evidence_report: bool,
    console: "Console",
    simple_mode: bool = False,
) -> str | None:
    """Route output to json/html/terminal based on args.

    Args:
        args: Parsed command-line arguments
        ping_results: List of ping test results
        speedtest_result: Speed test result
        dns_results: List of DNS test results
        mtr_results: List of MTR test results
        diagnostic: Network diagnostic result
        port_results: List of port test results
        http_results: List of HTTP test results
        video_service_results: List of video service test results
        expected_speed: Expected download speed in Mbps
        thresholds: Threshold configuration
        output_dir: Directory for output files
        open_browser: Whether to open HTML in browser
        suppress_output: Whether to suppress terminal output
        previous_history: Previous test history for comparison
        connection_score: Connection health score
        voip_quality: VoIP quality metrics
        isp_evidence: ISP evidence report
        bufferbloat_result: Bufferbloat test result
        generate_evidence_report: Whether to show evidence summary
        console: Rich console for output
        simple_mode: Whether to use simple, non-technical output

    Returns:
        Path to HTML report if generated, None otherwise
    """
    from ..output import display_terminal, generate_html, output_json
    from ..output.terminal import simple_display

    if args.format == "json":
        output_json(
            ping_results,
            speedtest_result,
            dns_results,
            mtr_results,
            diagnostic,
            port_results=port_results,
            http_results=http_results,
            video_service_results=video_service_results,
        )
        return None

    # Text or HTML format
    if not suppress_output:
        if simple_mode:
            # Simple, non-technical output for everyday users
            simple_display(
                ping_results,
                speedtest_result,
                diagnostic,
                connection_score,
                console,
            )
        else:
            # Full technical output
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
                video_service_results=video_service_results,
            )

            # Show VoIP quality if calculated
            _display_voip_quality(voip_quality, console)

            # Show ISP evidence summary if requested or issues found
            _display_evidence_summary(isp_evidence, generate_evidence_report, console)

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

    return html_path


def _display_voip_quality(voip_quality, console: "Console") -> None:
    """Display VoIP quality metrics.

    Args:
        voip_quality: VoIP quality metrics
        console: Rich console for output
    """
    if not voip_quality:
        return

    mos_color = "green" if voip_quality.mos_score >= 4.0 else (
        "yellow" if voip_quality.mos_score >= 3.6 else "red"
    )
    console.print(
        f"\n[bold]VoIP Quality:[/bold] [{mos_color}]MOS {voip_quality.mos_score:.1f}"
        f"[/{mos_color}] ({voip_quality.quality})"
    )
    if voip_quality.suitable_for:
        console.print(f"[dim]Suitable for: {', '.join(voip_quality.suitable_for)}[/dim]")


def _display_evidence_summary(isp_evidence, generate_evidence_report: bool, console: "Console") -> None:
    """Display ISP evidence summary if issues found.

    Args:
        isp_evidence: ISP evidence report
        generate_evidence_report: Whether evidence was requested
        console: Rich console for output
    """
    if not generate_evidence_report or not isp_evidence:
        return

    has_issues = (
        isp_evidence.speed_complaint or
        isp_evidence.packet_loss_complaint or
        isp_evidence.latency_complaint
    )

    if not has_issues:
        return

    console.print("\n[bold red]ISP Evidence Summary:[/bold red]")
    console.print(f"[bold]{isp_evidence.summary}[/bold]")
    if isp_evidence.speed_complaint:
        console.print(f"  [red]* {isp_evidence.speed_complaint}[/red]")
    if isp_evidence.packet_loss_complaint:
        console.print(f"  [red]* {isp_evidence.packet_loss_complaint}[/red]")
    if isp_evidence.latency_complaint:
        console.print(f"  [yellow]* {isp_evidence.latency_complaint}[/yellow]")
    console.print("[dim]Full evidence available in HTML report.[/dim]")


def handle_csv_export(
    ping_results: list,
    speedtest_result,
    dns_results: list,
    mtr_results: list,
    output_dir: str,
    suppress_output: bool,
    console: "Console",
) -> str | None:
    """Export results to CSV files.

    Args:
        ping_results: List of ping test results
        speedtest_result: Speed test result
        dns_results: List of DNS test results
        mtr_results: List of MTR test results
        output_dir: Directory for output files
        suppress_output: Whether to suppress terminal output
        console: Rich console for output

    Returns:
        Path to CSV directory if exported, None otherwise
    """
    from ..output import export_csv

    csv_dir = export_csv(
        ping_results,
        speedtest_result,
        dns_results,
        mtr_results,
        output_dir=output_dir,
    )

    if not suppress_output:
        console.print(f"[green]CSV files saved to: {csv_dir}[/green]")

    return csv_dir


def handle_browser_open(
    html_path: str,
    open_browser: bool,
    format_arg: str,
    suppress_output: bool,
    console: "Console",
) -> None:
    """Open HTML report in browser if configured.

    Args:
        html_path: Path to HTML report
        open_browser: Whether to open in browser
        format_arg: Output format argument value
        suppress_output: Whether to suppress terminal output
        console: Rich console for output
    """
    if open_browser and format_arg != "html":
        if not suppress_output:
            console.print("[dim]Opening report in browser...[/dim]")
        webbrowser.open(f"file://{html_path}")

    if format_arg == "html":
        print(html_path)
