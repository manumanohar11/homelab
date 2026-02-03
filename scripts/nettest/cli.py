"""Backward compatibility shim for cli module."""
from .cli import main, create_parser

__all__ = ["main", "create_parser"]
