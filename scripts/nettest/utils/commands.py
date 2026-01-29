"""
Command execution utilities and dependency checking.
"""

import shutil
import subprocess
from typing import Dict, Tuple, Optional, Any

# Tool requirements with installation instructions
REQUIRED_TOOLS: Dict[str, Dict[str, Any]] = {
    "ping": {
        "required": True,
        "description": "Basic connectivity test",
        "install": {
            "debian": "Usually pre-installed. If missing: sudo apt install iputils-ping",
            "fedora": "Usually pre-installed. If missing: sudo dnf install iputils",
        }
    },
    "dig": {
        "required": False,
        "description": "DNS resolution testing",
        "install": {
            "debian": "sudo apt install dnsutils",
            "fedora": "sudo dnf install bind-utils",
        }
    },
    "mtr": {
        "required": False,
        "description": "Route analysis and traceroute",
        "install": {
            "debian": "sudo apt install mtr-tiny",
            "fedora": "sudo dnf install mtr",
        }
    },
    "speedtest-cli": {
        "required": False,
        "description": "Internet speed testing",
        "install": {
            "debian": "sudo apt install speedtest-cli  # or: pip install speedtest-cli",
            "fedora": "pip install speedtest-cli",
        },
        "alternatives": ["speedtest"]
    },
}


def run_command(cmd: list, timeout: int = 60) -> Tuple[int, str, str]:
    """
    Run a command and return exit code, stdout, stderr.

    Args:
        cmd: Command as list of arguments
        timeout: Timeout in seconds (default: 60)

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return -1, "", str(e)


def check_dependencies(quiet: bool = False, console: Optional[Any] = None) -> Dict[str, bool]:
    """
    Check if required tools are installed.

    Args:
        quiet: Suppress status output
        console: Rich console for formatted output (optional)

    Returns:
        Dict of tool_name -> is_available
    """
    results = {}

    for tool, info in REQUIRED_TOOLS.items():
        # Check main tool
        available = shutil.which(tool) is not None

        # Check alternatives if main tool not found
        if not available and "alternatives" in info:
            for alt in info["alternatives"]:
                if shutil.which(alt) is not None:
                    available = True
                    break

        results[tool] = available

    if not quiet and console:
        from rich.table import Table
        from rich import box

        table = Table(title="Tool Availability", box=box.ROUNDED)
        table.add_column("Tool", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Purpose", style="dim")

        for tool, info in REQUIRED_TOOLS.items():
            available = results[tool]
            status = "[green]Available[/green]" if available else "[red]Missing[/red]"
            required_marker = " [yellow](required)[/yellow]" if info["required"] else ""
            table.add_row(tool, status, info["description"] + required_marker)

        console.print(table)
        console.print()

        # Show install instructions for missing tools
        missing = [t for t, available in results.items() if not available]
        if missing:
            console.print("[yellow]Missing tools - install instructions:[/yellow]")
            for tool in missing:
                info = REQUIRED_TOOLS[tool]
                console.print(f"\n[bold]{tool}[/bold]:")
                console.print(f"  Debian/Ubuntu: {info['install']['debian']}")
                console.print(f"  Fedora/RHEL:   {info['install']['fedora']}")
            console.print()

    return results
