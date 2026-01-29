"""Output formatters for network test results."""

from .terminal import display_terminal
from .html import generate_html
from .json_output import output_json

# Prometheus is optional
try:
    from .prometheus import start_metrics_server, update_metrics, get_metrics_text
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

__all__ = [
    "display_terminal",
    "generate_html",
    "output_json",
]
