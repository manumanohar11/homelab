"""Utility modules for the network testing tool."""

from .commands import run_command, check_dependencies, REQUIRED_TOOLS
from .logging import JsonLogger
from .history import save_history, load_history, format_change
from .network import list_interfaces, get_interface_ip, validate_interface, get_default_interface
from .storage import (
    init_database,
    store_result,
    get_recent_results,
    get_results_in_range,
    get_trend_data,
    cleanup_old_results,
    export_to_csv,
    get_last_result,
    get_database_stats,
)

__all__ = [
    "run_command",
    "check_dependencies",
    "REQUIRED_TOOLS",
    "JsonLogger",
    "save_history",
    "load_history",
    "format_change",
    "list_interfaces",
    "get_interface_ip",
    "validate_interface",
    "get_default_interface",
    # SQLite storage functions
    "init_database",
    "store_result",
    "get_recent_results",
    "get_results_in_range",
    "get_trend_data",
    "cleanup_old_results",
    "export_to_csv",
    "get_last_result",
    "get_database_stats",
]
