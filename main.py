from __future__ import annotations

import platform as _platform
import subprocess as _subprocess
import sys
from pathlib import Path


if _platform.system() == "Windows":
    _OrigPopen = _subprocess.Popen

    class _Popen(_OrigPopen):
        def __init__(self, args, **kwargs):
            kwargs["creationflags"] = (
                kwargs.get("creationflags", 0) | _subprocess.CREATE_NO_WINDOW
            )
            kwargs.pop("startupinfo", None)
            super().__init__(args, **kwargs)

    _subprocess.Popen = _Popen

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass


if getattr(sys, "frozen", False):
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    """Open the desktop application and start its on-device assistant."""
    from core.local_assistant import LocalAssistant
    from core.tool_declarations import TOOL_DECLARATIONS
    from ui import DoomUI

    ui = DoomUI()
    assistant = LocalAssistant(ui, TOOL_DECLARATIONS, BASE_DIR)
    assistant.start()
    try:
        ui.root.mainloop()
    finally:
        assistant.stop()


if __name__ == "__main__":
    main()
