import json
from types import SimpleNamespace

from core import local_runtime


def test_ensure_local_model_sets_private_ollama_defaults_and_pulls(tmp_path, monkeypatch):
    import core.llm_client as llm_client

    config_path = tmp_path / "api_keys.json"
    config_path.write_text('{"assistant_name": "Doom"}', encoding="utf-8")
    monkeypatch.setattr(llm_client, "CONFIG_PATH", config_path)
    monkeypatch.setattr(local_runtime, "ensure_ollama_installed", lambda log: "C:/Ollama/ollama.exe")
    monkeypatch.setattr(llm_client, "ensure_ollama_running", lambda timeout: True)
    commands = []

    def fake_run(args, **kwargs):
        commands.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(local_runtime.subprocess, "run", fake_run)
    messages = []

    assert local_runtime.ensure_local_model(messages.append, "qwen3-vl:4b") == "qwen3-vl:4b"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["llm_provider"] == "ollama"
    assert config["llm_url"] == "http://localhost:11434"
    assert config["llm_model"] == "qwen3-vl:4b"
    assert commands == [["C:/Ollama/ollama.exe", "pull", "qwen3-vl:4b"]]


def test_ensure_local_model_reports_pull_failures(tmp_path, monkeypatch):
    import core.llm_client as llm_client

    config_path = tmp_path / "api_keys.json"
    monkeypatch.setattr(llm_client, "CONFIG_PATH", config_path)
    monkeypatch.setattr(local_runtime, "ensure_ollama_installed", lambda log: "ollama")
    monkeypatch.setattr(llm_client, "ensure_ollama_running", lambda timeout: True)
    monkeypatch.setattr(
        local_runtime.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="network error"),
    )

    try:
        local_runtime.ensure_local_model(lambda message: None)
    except RuntimeError as exc:
        assert "network error" in str(exc)
    else:
        raise AssertionError("A failed model download must be reported.")
