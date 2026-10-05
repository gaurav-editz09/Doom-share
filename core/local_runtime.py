"""Bootstrap the private, on-device Ollama runtime used by Doom."""
from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

DEFAULT_LOCAL_MODEL = "qwen3-vl:4b"


def _ollama_executable() -> str | None:
    executable = shutil.which("ollama")
    if executable:
        return executable

    if sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if local.is_file():
            return str(local)
    return None


def ensure_ollama_installed(log: Callable[[str], None]) -> str:
    """Install Ollama for the current Windows user when it is not already present."""
    executable = _ollama_executable()
    if executable:
        return executable
    if sys.platform != "win32":
        raise RuntimeError("Automatic Ollama setup is currently supported on Windows only.")

    winget = shutil.which("winget")
    if not winget:
        raise RuntimeError(
            "This PC does not have Windows Package Manager (winget). "
            "Install Ollama from https://ollama.com/download, then reopen Doom."
        )

    log("Installing the private local AI runtime. This can take a few minutes.")
    result = subprocess.run(
        [
            winget, "install", "--id", "Ollama.Ollama", "--exact", "--silent",
            "--accept-source-agreements", "--accept-package-agreements",
            "--disable-interactivity",
        ],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    executable = _ollama_executable()
    if result.returncode != 0 or not executable:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            "Ollama could not be installed automatically."
            + (f" Details: {detail[-500:]}" if detail else "")
        )
    return executable


def ensure_local_model(
    log: Callable[[str], None],
    model: str = DEFAULT_LOCAL_MODEL,
) -> str:
    """Start local Ollama and download the model once, reporting pull progress."""
    executable = ensure_ollama_installed(log)

    from core.llm_client import CONFIG_PATH, ensure_ollama_running

    executable_dir = str(Path(executable).parent)
    os.environ["PATH"] = executable_dir + os.pathsep + os.environ.get("PATH", "")
    config = {}
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not read the local AI settings: {exc}") from exc
    config.update({
        "llm_provider": "ollama",
        "llm_url": "http://localhost:11434",
        "llm_model": model,
    })
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")

    if not ensure_ollama_running(timeout=60):
        raise RuntimeError("The local AI runtime did not start. Restart Doom and try again.")

    log(f"Checking local AI model {model}…")
    result = subprocess.run(
        [executable, "pull", model],
        capture_output=True,
        text=True,
        timeout=3600,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"Could not download local AI model '{model}'."
            + (f" Details: {detail[-500:]}" if detail else "")
        )
    log(f"Local model {model} is ready.")
    return model
