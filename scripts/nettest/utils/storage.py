"""
SQLite-based history storage for tracking test results over time.

Provides persistent storage with efficient querying, trend analysis,
and automatic cleanup of old results.
"""

import csv
import json
import os
import platform
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _get_data_directory() -> Path:
    """
    Get platform-appropriate data directory for nettest.

    Returns:
        Path to the data directory (e.g., ~/.local/share/nettest on Linux,
        %LOCALAPPDATA%/nettest on Windows)
    """
    system = platform.system()

    if system == "Windows":
        # Use %LOCALAPPDATA%/nettest on Windows
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "nettest"
        # Fallback to user home
        return Path.home() / "AppData" / "Local" / "nettest"
    elif system == "Darwin":
        # macOS: ~/Library/Application Support/nettest
        return Path.home() / "Library" / "Application Support" / "nettest"
    else:
        # Linux/Unix: Follow XDG Base Directory Specification
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            return Path(xdg_data_home) / "nettest"
        return Path.home() / ".local" / "share" / "nettest"


def _get_default_db_path() -> Path:
    """
    Get the default database path.

    Returns:
        Path to history.db in the platform-appropriate data directory
    """
    return _get_data_directory() / "history.db"


def init_database(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Initialize the SQLite database and create tables if needed.

    Args:
        db_path: Optional custom path to the database file.
                 If not provided, uses the platform-appropriate default location.

    Returns:
        sqlite3.Connection: Database connection object

    Raises:
        sqlite3.Error: If database initialization fails
    """
    if db_path is None:
        path = _get_default_db_path()
    else:
        path = Path(db_path)

    # Create parent directories if they don't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows

    # Create tables if they don't exist
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            profile TEXT,
            ping_avg_ms REAL,
            ping_jitter_ms REAL,
            ping_loss_pct REAL,
            download_mbps REAL,
            upload_mbps REAL,
            overall_score INTEGER,
            grade TEXT,
            raw_json TEXT
        )
    """)

    # Create index on timestamp for efficient date range queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp ON test_results(timestamp)
    """)

    conn.commit()
    return conn


def _extract_summary_metrics(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract summary metrics from full results dictionary.

    Args:
        results: Full test results dictionary

    Returns:
        Dictionary with extracted summary metrics
    """
    metrics: Dict[str, Any] = {
        "ping_avg_ms": None,
        "ping_jitter_ms": None,
        "ping_loss_pct": None,
        "download_mbps": None,
        "upload_mbps": None,
        "overall_score": None,
        "grade": None,
    }

    # Extract ping metrics (average across all targets)
    ping_results = results.get("ping_results", results.get("ping", []))
    if ping_results:
        successful_pings = [p for p in ping_results if p.get("success", False)]
        if successful_pings:
            metrics["ping_avg_ms"] = sum(p.get("avg_ms", 0) for p in successful_pings) / len(successful_pings)
            metrics["ping_jitter_ms"] = sum(p.get("jitter_ms", 0) for p in successful_pings) / len(successful_pings)
            metrics["ping_loss_pct"] = sum(p.get("packet_loss", 0) for p in successful_pings) / len(successful_pings)

    # Extract speedtest metrics
    speedtest = results.get("speedtest", {})
    if speedtest and speedtest.get("success", False):
        metrics["download_mbps"] = speedtest.get("download_mbps")
        metrics["upload_mbps"] = speedtest.get("upload_mbps")

    # Extract connection score if available
    connection_score = results.get("connection_score", {})
    if connection_score:
        metrics["overall_score"] = connection_score.get("overall")
        metrics["grade"] = connection_score.get("grade")

    return metrics


def store_result(
    results: Dict[str, Any],
    profile: Optional[str] = None,
    db_path: Optional[str] = None,
    retention_days: int = 90,
    auto_cleanup: bool = True,
) -> int:
    """
    Store a test result in the database.

    Args:
        results: Test results dictionary (from results_to_dict or similar)
        profile: Test profile name (e.g., "quick", "full")
        db_path: Optional custom database path
        retention_days: Number of days to retain results (for auto-cleanup)
        auto_cleanup: Whether to run automatic cleanup of old results

    Returns:
        int: ID of the inserted row

    Raises:
        sqlite3.Error: If database operation fails
    """
    conn = init_database(db_path)

    try:
        # Run auto-cleanup if enabled (every 10 inserts on average)
        if auto_cleanup:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test_results")
            count = cursor.fetchone()[0]
            # Run cleanup roughly every 10 inserts
            if count > 0 and count % 10 == 0:
                cleanup_old_results(retention_days, db_path)

        # Extract summary metrics
        metrics = _extract_summary_metrics(results)

        # Get timestamp from results or use current time
        timestamp = results.get("timestamp", datetime.now().isoformat())

        # Serialize full results to JSON
        raw_json = json.dumps(results, default=str)

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO test_results (
                timestamp, profile, ping_avg_ms, ping_jitter_ms, ping_loss_pct,
                download_mbps, upload_mbps, overall_score, grade, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            profile,
            metrics["ping_avg_ms"],
            metrics["ping_jitter_ms"],
            metrics["ping_loss_pct"],
            metrics["download_mbps"],
            metrics["upload_mbps"],
            metrics["overall_score"],
            metrics["grade"],
            raw_json,
        ))

        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """
    Convert a sqlite3.Row to a dictionary with parsed JSON.

    Args:
        row: SQLite row object

    Returns:
        Dictionary representation of the row
    """
    result = dict(row)
    # Parse raw_json if present
    if result.get("raw_json"):
        try:
            result["raw_json"] = json.loads(result["raw_json"])
        except json.JSONDecodeError:
            pass  # Keep as string if parsing fails
    return result


def get_recent_results(limit: int = 10, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get the most recent test results.

    Args:
        limit: Maximum number of results to return (default 10)
        db_path: Optional custom database path

    Returns:
        List of result dictionaries, most recent first
    """
    conn = init_database(db_path)

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM test_results
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        return [_row_to_dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_results_in_range(
    start: str,
    end: str,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get test results within a date range.

    Args:
        start: Start date/time in ISO format (e.g., "2024-01-01" or "2024-01-01T00:00:00")
        end: End date/time in ISO format (e.g., "2024-01-31" or "2024-01-31T23:59:59")
        db_path: Optional custom database path

    Returns:
        List of result dictionaries within the date range, ordered by timestamp
    """
    conn = init_database(db_path)

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM test_results
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """, (start, end))

        return [_row_to_dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_trend_data(days: int = 7, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get aggregated trend data for graphing and analysis.

    Args:
        days: Number of days to analyze (default 7)
        db_path: Optional custom database path

    Returns:
        Dictionary containing:
        - period: Date range covered
        - count: Number of tests in period
        - averages: Average values for each metric
        - min_max: Min/max values for each metric
        - daily: Daily breakdown of averages
        - trend: Trend direction for each metric (improving/stable/degrading)
    """
    conn = init_database(db_path)

    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = conn.cursor()

        # Get overall statistics
        cursor.execute("""
            SELECT
                COUNT(*) as count,
                MIN(timestamp) as first_test,
                MAX(timestamp) as last_test,
                AVG(ping_avg_ms) as avg_ping,
                AVG(ping_jitter_ms) as avg_jitter,
                AVG(ping_loss_pct) as avg_loss,
                AVG(download_mbps) as avg_download,
                AVG(upload_mbps) as avg_upload,
                AVG(overall_score) as avg_score,
                MIN(ping_avg_ms) as min_ping,
                MAX(ping_avg_ms) as max_ping,
                MIN(download_mbps) as min_download,
                MAX(download_mbps) as max_download,
                MIN(upload_mbps) as min_upload,
                MAX(upload_mbps) as max_upload
            FROM test_results
            WHERE timestamp >= ?
        """, (cutoff,))

        stats = dict(cursor.fetchone())

        # Get daily breakdown
        cursor.execute("""
            SELECT
                DATE(timestamp) as date,
                COUNT(*) as count,
                AVG(ping_avg_ms) as avg_ping,
                AVG(ping_jitter_ms) as avg_jitter,
                AVG(ping_loss_pct) as avg_loss,
                AVG(download_mbps) as avg_download,
                AVG(upload_mbps) as avg_upload,
                AVG(overall_score) as avg_score
            FROM test_results
            WHERE timestamp >= ?
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        """, (cutoff,))

        daily = [dict(row) for row in cursor.fetchall()]

        # Calculate trends (compare first half to second half of period)
        trends: Dict[str, str] = {}
        if len(daily) >= 2:
            mid = len(daily) // 2
            first_half = daily[:mid]
            second_half = daily[mid:]

            def calc_trend(metric: str) -> str:
                first_vals = [d[metric] for d in first_half if d[metric] is not None]
                second_vals = [d[metric] for d in second_half if d[metric] is not None]

                if not first_vals or not second_vals:
                    return "insufficient_data"

                first_avg = sum(first_vals) / len(first_vals)
                second_avg = sum(second_vals) / len(second_vals)

                if first_avg == 0:
                    return "stable"

                change_pct = ((second_avg - first_avg) / first_avg) * 100

                # For ping/jitter/loss, lower is better
                if metric in ("avg_ping", "avg_jitter", "avg_loss"):
                    if change_pct < -5:
                        return "improving"
                    elif change_pct > 5:
                        return "degrading"
                    return "stable"
                else:
                    # For download/upload/score, higher is better
                    if change_pct > 5:
                        return "improving"
                    elif change_pct < -5:
                        return "degrading"
                    return "stable"

            trends["ping"] = calc_trend("avg_ping")
            trends["jitter"] = calc_trend("avg_jitter")
            trends["packet_loss"] = calc_trend("avg_loss")
            trends["download"] = calc_trend("avg_download")
            trends["upload"] = calc_trend("avg_upload")
            trends["score"] = calc_trend("avg_score")

        return {
            "period": {
                "days": days,
                "start": cutoff,
                "end": datetime.now().isoformat(),
                "first_test": stats.get("first_test"),
                "last_test": stats.get("last_test"),
            },
            "count": stats.get("count", 0),
            "averages": {
                "ping_ms": stats.get("avg_ping"),
                "jitter_ms": stats.get("avg_jitter"),
                "packet_loss_pct": stats.get("avg_loss"),
                "download_mbps": stats.get("avg_download"),
                "upload_mbps": stats.get("avg_upload"),
                "overall_score": stats.get("avg_score"),
            },
            "min_max": {
                "ping_ms": (stats.get("min_ping"), stats.get("max_ping")),
                "download_mbps": (stats.get("min_download"), stats.get("max_download")),
                "upload_mbps": (stats.get("min_upload"), stats.get("max_upload")),
            },
            "daily": daily,
            "trends": trends,
        }
    finally:
        conn.close()


def cleanup_old_results(days: int = 90, db_path: Optional[str] = None) -> int:
    """
    Delete test results older than the specified number of days.

    Args:
        days: Number of days to retain (default 90)
        db_path: Optional custom database path

    Returns:
        int: Number of rows deleted
    """
    conn = init_database(db_path)

    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM test_results
            WHERE timestamp < ?
        """, (cutoff,))

        deleted_count = cursor.rowcount
        conn.commit()

        # Vacuum to reclaim space if we deleted a lot
        if deleted_count > 100:
            cursor.execute("VACUUM")

        return deleted_count
    finally:
        conn.close()


def export_to_csv(
    path: str,
    days: int = 30,
    db_path: Optional[str] = None,
    include_raw_json: bool = False,
) -> None:
    """
    Export history data to a CSV file.

    Args:
        path: Path to the output CSV file
        days: Number of days of history to export (default 30)
        db_path: Optional custom database path
        include_raw_json: Whether to include the raw JSON column (default False)

    Raises:
        IOError: If file cannot be written
    """
    conn = init_database(db_path)

    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM test_results
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (cutoff,))

        rows = cursor.fetchall()

        if not rows:
            # Write empty CSV with headers
            columns = [
                "id", "timestamp", "profile", "ping_avg_ms", "ping_jitter_ms",
                "ping_loss_pct", "download_mbps", "upload_mbps", "overall_score", "grade"
            ]
            if include_raw_json:
                columns.append("raw_json")
        else:
            columns = list(rows[0].keys())
            if not include_raw_json and "raw_json" in columns:
                columns.remove("raw_json")

        # Ensure parent directory exists
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()

            for row in rows:
                row_dict = dict(row)
                if not include_raw_json and "raw_json" in row_dict:
                    del row_dict["raw_json"]
                writer.writerow(row_dict)
    finally:
        conn.close()


def get_last_result(db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get the most recent test result (for comparison with current results).

    This is a convenience function similar to load_history() in the JSON module.

    Args:
        db_path: Optional custom database path

    Returns:
        Most recent result dictionary, or None if no results exist
    """
    results = get_recent_results(limit=1, db_path=db_path)
    if results:
        # Return the raw_json for full compatibility with history comparison
        result = results[0]
        if isinstance(result.get("raw_json"), dict):
            return result["raw_json"]
        return result
    return None


def get_database_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get statistics about the database.

    Args:
        db_path: Optional custom database path

    Returns:
        Dictionary with database statistics
    """
    conn = init_database(db_path)

    try:
        cursor = conn.cursor()

        # Total count
        cursor.execute("SELECT COUNT(*) FROM test_results")
        total_count = cursor.fetchone()[0]

        # Date range
        cursor.execute("""
            SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest
            FROM test_results
        """)
        date_range = cursor.fetchone()

        # Count by profile
        cursor.execute("""
            SELECT profile, COUNT(*) as count
            FROM test_results
            GROUP BY profile
            ORDER BY count DESC
        """)
        by_profile = {row[0] or "default": row[1] for row in cursor.fetchall()}

        # Database file size
        db_path_actual = _get_default_db_path() if db_path is None else Path(db_path)
        file_size = db_path_actual.stat().st_size if db_path_actual.exists() else 0

        return {
            "total_results": total_count,
            "oldest_result": date_range[0] if date_range else None,
            "newest_result": date_range[1] if date_range else None,
            "by_profile": by_profile,
            "database_path": str(db_path_actual),
            "database_size_bytes": file_size,
            "database_size_mb": round(file_size / (1024 * 1024), 2),
        }
    finally:
        conn.close()
