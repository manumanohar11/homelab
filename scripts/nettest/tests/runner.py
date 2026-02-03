"""Test orchestration and progress tracking."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional, Any

from ..models import (
    PingResult, SpeedTestResult, DnsResult, MtrResult,
    BufferbloatResult, VideoServiceResult
)
from .ping import run_ping_test
from .speedtest import run_speedtest
from .dns import run_dns_test
from .mtr import run_mtr
from .bufferbloat import detect_bufferbloat
from .video_services import run_video_service_tests


def run_tests_with_progress(
    targets: Dict[str, str],
    ping_count: int = 10,
    mtr_count: int = 10,
    quiet: bool = False,
    skip_speedtest: bool = False,
    skip_dns: bool = False,
    skip_mtr: bool = False,
    parallel: bool = False,
    ip_version: Optional[int] = None,
    interface: Optional[str] = None,
    console: Optional[Any] = None,
    json_logger: Optional[Any] = None,
    run_bufferbloat: bool = False,
    run_video_services: bool = False,
) -> Tuple[List[PingResult], SpeedTestResult, List[DnsResult], List[MtrResult], Optional[BufferbloatResult], List[VideoServiceResult]]:
    """
    Run network tests with progress indicators.

    Args:
        targets: Dict of target_name -> target_address
        ping_count: Number of ping packets to send
        mtr_count: Number of mtr packets to send
        quiet: Suppress progress output
        skip_speedtest: Skip speed test
        skip_dns: Skip DNS tests
        skip_mtr: Skip MTR route analysis
        parallel: Run ping and DNS tests in parallel
        ip_version: Force IPv4 (4) or IPv6 (6), or None for auto
        interface: Network interface to use (e.g., "eth0")
        console: Rich console for progress output
        json_logger: JsonLogger instance for structured logging
        run_bufferbloat: Run bufferbloat detection test
        run_video_services: Run video conferencing service tests

    Returns:
        Tuple of (ping_results, speedtest_result, dns_results, mtr_results, bufferbloat_result, video_service_results)
    """
    from rich.progress import (
        Progress, SpinnerColumn, TextColumn,
        BarColumn, TaskProgressColumn, TimeElapsedColumn
    )

    ping_results: List[PingResult] = []
    dns_results: List[DnsResult] = []
    mtr_results: List[MtrResult] = []
    speedtest_result = SpeedTestResult()
    bufferbloat_result: Optional[BufferbloatResult] = None
    video_service_results: List[VideoServiceResult] = []

    # Calculate total steps based on what tests we're running
    num_targets = len(targets)
    total_steps = num_targets  # ping tests always run
    if not skip_speedtest:
        total_steps += 1
    if not skip_dns:
        total_steps += num_targets
    if not skip_mtr:
        total_steps += num_targets
    if run_bufferbloat:
        total_steps += 1
    if run_video_services:
        total_steps += 1  # Video services run as a batch

    # Use console if provided, otherwise create a default
    if console is None:
        from rich.console import Console
        console = Console()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=not quiet,
        disable=quiet,
    ) as progress:
        overall_task = progress.add_task("[cyan]Running network tests...", total=total_steps)

        if parallel:
            # Parallel execution for ping and DNS tests
            progress.update(overall_task, description="[cyan]Running ping tests in parallel...")

            # Run ping tests in parallel
            with ThreadPoolExecutor(max_workers=min(len(targets), 5)) as executor:
                ping_futures = {
                    executor.submit(run_ping_test, target, name, ping_count, ip_version, interface): name
                    for name, target in targets.items()
                }
                for future in as_completed(ping_futures):
                    result = future.result()
                    ping_results.append(result)
                    if json_logger:
                        json_logger.log_ping_result(result)
                    progress.advance(overall_task)

            # Run speed test (sequential - uses bandwidth)
            if not skip_speedtest:
                progress.update(overall_task, description="[cyan]Running speed test...")
                speedtest_result = run_speedtest()
                if json_logger:
                    json_logger.log_speedtest_result(speedtest_result)
                progress.advance(overall_task)

            # Run DNS tests in parallel
            if not skip_dns:
                progress.update(overall_task, description="[cyan]Running DNS tests in parallel...")
                with ThreadPoolExecutor(max_workers=min(len(targets), 5)) as executor:
                    dns_futures = {
                        executor.submit(run_dns_test, target): name
                        for name, target in targets.items()
                    }
                    for future in as_completed(dns_futures):
                        result = future.result()
                        dns_results.append(result)
                        if json_logger:
                            json_logger.log_dns_result(result)
                        progress.advance(overall_task)

            # Run MTR tests (sequential - uses significant network resources)
            if not skip_mtr:
                for name, target in targets.items():
                    progress.update(overall_task, description=f"[cyan]Route analysis to {name}...")
                    result = run_mtr(target, name, count=mtr_count, interface=interface)
                    mtr_results.append(result)
                    if json_logger:
                        json_logger.log_mtr_result(result)
                    progress.advance(overall_task)
        else:
            # Sequential execution (original behavior)
            # Run ping tests
            for name, target in targets.items():
                progress.update(overall_task, description=f"[cyan]Pinging {name}...")
                result = run_ping_test(target, name, count=ping_count, ip_version=ip_version, interface=interface)
                ping_results.append(result)
                if json_logger:
                    json_logger.log_ping_result(result)
                progress.advance(overall_task)

            # Run speed test
            if not skip_speedtest:
                progress.update(overall_task, description="[cyan]Running speed test...")
                speedtest_result = run_speedtest()
                if json_logger:
                    json_logger.log_speedtest_result(speedtest_result)
                progress.advance(overall_task)

            # Run DNS tests
            if not skip_dns:
                for name, target in targets.items():
                    progress.update(overall_task, description=f"[cyan]Testing DNS for {name}...")
                    result = run_dns_test(target)
                    dns_results.append(result)
                    if json_logger:
                        json_logger.log_dns_result(result)
                    progress.advance(overall_task)

            # Run MTR tests
            if not skip_mtr:
                for name, target in targets.items():
                    progress.update(overall_task, description=f"[cyan]Route analysis to {name}...")
                    result = run_mtr(target, name, count=mtr_count, interface=interface)
                    mtr_results.append(result)
                    if json_logger:
                        json_logger.log_mtr_result(result)
                    progress.advance(overall_task)

        # Run bufferbloat test (always sequential - measures latency under load)
        if run_bufferbloat:
            progress.update(overall_task, description="[cyan]Testing bufferbloat...")
            bufferbloat_result = detect_bufferbloat(interface=interface)
            progress.advance(overall_task)

        # Run video service tests
        if run_video_services:
            progress.update(overall_task, description="[cyan]Testing video services...")
            video_service_results = run_video_service_tests()
            progress.advance(overall_task)

        progress.update(overall_task, description="[green]Tests complete!")

    return ping_results, speedtest_result, dns_results, mtr_results, bufferbloat_result, video_service_results
