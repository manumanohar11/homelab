"""Output formatters for network test results."""

from .terminal import display_terminal, simple_display
from .html import generate_html
from .json_output import output_json
from .evidence import generate_isp_evidence
from .csv_export import export_csv

# Prometheus is optional
try:
    from .prometheus import start_metrics_server, update_metrics, get_metrics_text
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

__all__ = [
    "display_terminal",
    "simple_display",
    "generate_html",
    "output_json",
    "generate_isp_evidence",
    "export_csv",
]
