#!/usr/bin/env python3
"""Entry point for PyInstaller build."""
import sys
sys.path.insert(0, '.')
from nettest.cli import main

if __name__ == "__main__":
    main()
