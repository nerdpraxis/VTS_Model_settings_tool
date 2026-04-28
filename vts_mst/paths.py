"""Resolve directories for dev (script) and PyInstaller frozen EXE."""

from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """
    Directory where config.ini lives: next to this tool's main script,
    or next to the frozen .exe when built with PyInstaller.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # vts_mst/paths.py -> package parent = vts_model_settings_tool/
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return app_root() / "config.ini"
