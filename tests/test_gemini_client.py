import json

import memory.config_manager as config_manager
from core import llm_client


class _FakeResponse:
    def __init__(self, chunks):
        self.chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        pass

    def iter_lines(self):
        return [f"data: {json.dumps(chunk)}".encode() for chunk in self.chunks]


def test_gemini_stream_sends_audio_tools_and_normalizes_tool_calls(monkeypatch):
    monkeypatch.setattr(llm_client, "get_llm_provider", lambda: "gemini")
    monkeypatch.setattr(llm_client, "get_llm_settings", lambda: ("", "gemini-test-model"))
    monkeypatch.setattr("memory.config_manager.get_gemini_key", lambda: "test-key")
    request = {}

    def fake_post(url, **kwargs):
        request.update(url=url, **kwargs)
        return _FakeResponse([
            {"candidates": [{"content": {"parts": [{"text": "Opening the app. "}]}}]},
            {"candidates": [{
                "content": {"parts": [{
                    "functionCall": {"name": "open_app", "args": {"name": "notepad"}}
                }]}
            }]},
        ])

    monkeypatch.setattr(llm_client.requests, "post", fake_post)
    messages = [
        {"role": "system", "content": "Be helpful."},
        {"role": "user", "content": "Open Notepad.", "audio_wav": "YXVkaW8="},
    ]
    tools = [{
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open an application.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
        },
    }]

    events = list(llm_client.call_llm_stream(messages, tools=tools))

    assert events == [
        {"type": "sentence", "text": "Opening the app."},
        {
            "type": "done",
            "content": "Opening the app.",
            "tool_calls": [{
                "function": {
                    "name": "open_app",
                    "arguments": {"name": "notepad"},
                }
            }],
        },
    ]
    assert request["headers"] == {"x-goog-api-key": "test-key"}
    body = request["json"]
    assert body["contents"][0]["parts"][1]["inlineData"] == {
        "mimeType": "audio/wav",
        "data": "YXVkaW8=",
    }
    declaration = body["tools"][0]["functionDeclarations"][0]
    assert declaration["parameters"]["type"] == "OBJECT"
    assert declaration["parameters"]["properties"]["name"]["type"] == "STRING"
    assert request["url"].endswith("gemini-test-model:streamGenerateContent?alt=sse")


def test_gemini_stream_preserves_camera_image_mime_type(monkeypatch):
    monkeypatch.setattr("memory.config_manager.get_gemini_key", lambda: "test-key")
    request = {}

    def fake_post(url, **kwargs):
        request.update(url=url, **kwargs)
        return _FakeResponse([])

    monkeypatch.setattr(llm_client.requests, "post", fake_post)

    list(llm_client._stream_gemini([
        {"role": "user", "content": "What is this?", "images": [
            {"data": "cG5n", "mime_type": "image/png"},
        ]},
    ], None, 10))

    assert request["json"]["contents"][0]["parts"][1]["inlineData"] == {
        "mimeType": "image/png",
        "data": "cG5n",
    }


def test_get_gemini_key_uses_env_var_when_config_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(config_manager, "load_api_keys", lambda: {})
    monkeypatch.setenv("GEMINI_API_KEY", "env-gemini-key")

    assert config_manager.get_gemini_key() == "env-gemini-key"


def test_configure_gemini_preserves_existing_user_settings(tmp_path, monkeypatch):
    config_path = tmp_path / "config" / "api_keys.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps({"assistant_name": "Doom", "gemini_api_key": "keep-private"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(llm_client, "CONFIG_PATH", config_path)
    monkeypatch.setattr("memory.config_manager.get_gemini_key", lambda: "keep-private")

    llm_client.configure_gemini()

    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["assistant_name"] == "Doom"
    assert config["llm_provider"] == "gemini"
    assert config["llm_model"] == "gemini-flash-latest"
