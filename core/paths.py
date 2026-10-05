"""Resolve bundled resources separately from per-user Doom data."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def get_bundle_dir() -> Path:
    """Return the directory containing app resources, including frozen builds."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def get_user_data_dir() -> Path:
    """Keep settings and personal memory outside the installed app directory."""
    if not getattr(sys, "frozen", False):
        return get_bundle_dir()
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "Doom"
    return Path.home() / ".local" / "share" / "Doom"


def get_config_path() -> Path:
    """Return the per-user settings file path for source and packaged runs."""
    return get_user_data_dir() / "config" / "api_keys.json"
