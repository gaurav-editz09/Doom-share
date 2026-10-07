"""Return a neutral fallback name for non-configured users.

We intentionally do not pull the signed-in Windows identity or account name for
voice greetings or AI addressing. That value is user-configurable in setup, and
when it is not set, the app should stay generic instead of speaking a machine
or Microsoft account name.
"""
from __future__ import annotations


def get_display_name() -> str:
    """Return a neutral fallback label instead of any OS-derived identity."""
    return "there"
