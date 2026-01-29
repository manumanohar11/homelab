"""CSV export for network test results."""

import csv
import os
from datetime import datetime
from typing import List
from ..models import PingResult, SpeedTestResult, MtrResult, DnsResult


def export_csv(
    ping_results: List[PingResult],
    speedtest_result: SpeedTestResult,
    dns_results: List[DnsResult],
    mtr_results: List[MtrResult],
    output_dir: str,
) -> str:
    """
    Export results to CSV files.

    Creates three files:
    - nettest_ping_TIMESTAMP.csv
    - nettest_speed_TIMESTAMP.csv
    - nettest_mtr_TIMESTAMP.csv

    Returns the directory path.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Ping results
    ping_file = os.path.join(output_dir, f"nettest_ping_{timestamp}.csv")
    with open(ping_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Target", "Min (ms)", "Avg (ms)", "Max (ms)", "Jitter (ms)", "Loss (%)", "Success"])
        for pr in ping_results:
            writer.writerow([
                pr.target_name, pr.min_ms, pr.avg_ms, pr.max_ms,
                pr.jitter_ms, pr.packet_loss, pr.success
            ])

    # Speed test
    speed_file = os.path.join(output_dir, f"nettest_speed_{timestamp}.csv")
    with open(speed_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Download (Mbps)", "Upload (Mbps)", "Ping (ms)", "Server", "Success"])
        writer.writerow([
            speedtest_result.download_mbps, speedtest_result.upload_mbps,
            speedtest_result.ping_ms, speedtest_result.server, speedtest_result.success
        ])

    # MTR results
    mtr_file = os.path.join(output_dir, f"nettest_mtr_{timestamp}.csv")
    with open(mtr_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Target", "Hop", "Host", "Loss (%)", "Avg (ms)", "Best (ms)", "Worst (ms)"])
        for mtr in mtr_results:
            if mtr.success:
                for hop in mtr.hops:
                    writer.writerow([
                        mtr.target_name, hop.hop_number, hop.host,
                        hop.loss_pct, hop.avg_ms, hop.best_ms, hop.worst_ms
                    ])

    return output_dir
