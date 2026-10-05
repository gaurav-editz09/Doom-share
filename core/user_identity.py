"""Resolve a friendly local account name without sending identity off-device."""
from __future__ import annotations

import getpass
import sys


def get_display_name() -> str:
    """Prefer the signed-in Windows display name; fall back to the account name."""
    if sys.platform == "win32":
        try:
            import ctypes

            get_name = ctypes.WinDLL("secur32", use_last_error=True).GetUserNameExW
            get_name.argtypes = [ctypes.c_int, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
            get_name.restype = ctypes.c_bool
            size = ctypes.c_ulong(0)
            get_name(3, None, ctypes.byref(size))  # NameDisplay
            if size.value:
                buffer = ctypes.create_unicode_buffer(size.value)
                if get_name(3, buffer, ctypes.byref(size)):
                    display_name = buffer.value.strip()
                    if display_name:
                        return display_name
        except (AttributeError, OSError, TypeError, ValueError):
            pass

    account_name = getpass.getuser().strip()
    return account_name or "there"
