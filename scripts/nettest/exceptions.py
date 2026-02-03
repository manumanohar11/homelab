"""Custom exceptions for nettest."""


class NettestError(Exception):
    """Base exception for all nettest errors."""
    pass


class ConfigurationError(NettestError):
    """Raised when configuration is invalid."""
    pass


class DependencyError(NettestError):
    """Raised when a required tool is missing."""

    def __init__(self, tool: str, install_hint: str = ""):
        self.tool = tool
        self.install_hint = install_hint
        message = f"Required tool '{tool}' not found"
        if install_hint:
            message += f". Install with: {install_hint}"
        super().__init__(message)


class TestExecutionError(NettestError):
    """Raised when a test fails to execute."""

    def __init__(self, test_name: str, reason: str = ""):
        self.test_name = test_name
        self.reason = reason
        message = f"Test '{test_name}' failed"
        if reason:
            message += f": {reason}"
        super().__init__(message)
