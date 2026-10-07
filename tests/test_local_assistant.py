import asyncio
import base64
import queue
import threading
from contextlib import nullcontext
from types import SimpleNamespace

import numpy as np
import pytest
from google.genai import types

from core.local_assistant import (
    _gemini_live_tools,
    _quick_volume_action,
)
from core import local_assistant
from core.tool_declarations import TOOL_DECLARATIONS


def test_live_audio_uses_short_chunks_and_bounded_buffer():
    assert local_assistant._AUDIO_CHUNK == 1024
    assert local_assistant._AUDIO_BUFFER_CHUNKS == 16
    assert local_assistant._LIVE_AUDIO_BUFFER_CHUNKS == 64


def test_microphone_status_logs_are_rate_limited():
    assert local_assistant._should_log_audio_status("input overflow", None, 10.0)
    assert not local_assistant._should_log_audio_status("input overflow", 10.0, 14.9)
    assert local_assistant._should_log_audio_status("input overflow", 10.0, 15.0)
    assert not local_assistant._should_log_audio_status(None, 10.0, 20.0)


def test_live_microphone_buffer_discards_stale_chunks_and_can_clear():
    async def run():
        buffer = local_assistant._LiveAudioBuffer(asyncio.get_running_loop(), 2)
        buffer.put_from_audio_callback(b"old")
        buffer.put_from_audio_callback(b"middle")
        buffer.put_from_audio_callback(b"latest")

        assert await buffer.get() == b"middle"
        assert await buffer.get() == b"latest"
        assert not buffer._ready.is_set()

        next_chunk = asyncio.create_task(buffer.get())
        await asyncio.sleep(0)
        buffer.put_from_audio_callback(b"next")
        assert await asyncio.wait_for(next_chunk, timeout=0.2) == b"next"

        buffer.put_from_audio_callback(b"muted audio")
        buffer.discard_pending()
        assert buffer._chunks.empty()

    asyncio.run(run())


def test_live_speaker_buffer_keeps_recent_audio_when_full():
    assistant = local_assistant.LocalAssistant.__new__(local_assistant.LocalAssistant)
    assistant._live_audio = queue.Queue(maxsize=2)
    assistant._is_speaking = threading.Event()

    assistant._queue_live_audio(b"old")
    assistant._queue_live_audio(b"middle")
    assistant._queue_live_audio(b"latest")

    assert list(assistant._live_audio.queue) == [b"middle", b"latest"]
    assert assistant._is_speaking.is_set()


def test_live_speech_uses_selected_output_device(monkeypatch):
    captured = {}

    class FakeOutputStream:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    assistant = local_assistant.LocalAssistant.__new__(local_assistant.LocalAssistant)
    assistant._stop = threading.Event()
    assistant._stop.set()
    monkeypatch.setattr(local_assistant.sd, "RawOutputStream", FakeOutputStream)
    monkeypatch.setattr("memory.config_manager.get_output_device", lambda: "Headphones")
    monkeypatch.setattr("core.audio_devices.resolve", lambda name, kind: 4)

    assistant._live_audio_output()

    assert captured["device"] == 4
    assert captured["samplerate"] == 24_000


def test_live_session_config_uses_audio_and_selected_voice(monkeypatch):
    assistant = local_assistant.LocalAssistant.__new__(local_assistant.LocalAssistant)
    assistant._live_tools = []
    assistant._messages = lambda _text: [{"content": "test system prompt"}]
    monkeypatch.setattr("memory.config_manager.get_voice", lambda: "Aoede")

    config = types.LiveConnectConfig(**assistant._run_live_tools())

    assert config.response_modalities == [types.Modality.AUDIO]
    assert config.system_instruction == "test system prompt"
    assert config.speech_config.voice_config.prebuilt_voice_config.voice_name == "Aoede"
    assert config.input_audio_transcription is not None
    assert config.output_audio_transcription is not None
    assert config.realtime_input_config.automatic_activity_detection.silence_duration_ms == 900
    assert config.realtime_input_config.automatic_activity_detection.start_of_speech_sensitivity == "START_SENSITIVITY_LOW"
    assert config.realtime_input_config.automatic_activity_detection.end_of_speech_sensitivity == "END_SENSITIVITY_HIGH"


def test_messages_match_user_language(monkeypatch):
    monkeypatch.setattr(local_assistant, "load_memory", lambda: {})
    monkeypatch.setattr(local_assistant, "format_memory_for_prompt", lambda memory: "")

    assistant = local_assistant.LocalAssistant.__new__(local_assistant.LocalAssistant)
    assistant.assistant_name = "Doom"
    assistant.user_name = ""
    assistant.base_dir = local_assistant.Path(__file__).resolve().parents[1]

    prompt_text = local_assistant.LocalAssistant._messages(assistant, "")
    system = prompt_text[0]["content"]

    assert "match the user's language exactly" in system
    assert "Hindi, Hinglish, English" in system


def test_microphone_callback_ignores_low_level_background_noise():
    def callback(indata):
        audio = indata.copy()
        rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
        if rms < 30.0:
            return False
        return True

    silence = np.zeros(160, dtype=np.int16)
    quiet = np.array([10, -6, 14, 8], dtype=np.int16)
    voice = np.array([240, -180, 320, -420, 260], dtype=np.int16)

    assert callback(silence) is False
    assert callback(quiet) is False
    assert callback(voice) is True


def test_live_session_connects_with_supported_model(monkeypatch):
    captured = {}
    stop = threading.Event()

    class FakeSession:
        def receive(self):
            async def messages():
                yield SimpleNamespace(server_content=None, tool_call=None)
                stop.set()

            return messages()

    class FakeLiveContext:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *_):
            return False

    class FakeLive:
        def connect(self, **kwargs):
            captured["model"] = kwargs["model"]
            return FakeLiveContext()

    async def close_client():
        pass

    def make_input_stream(**kwargs):
        captured["input_device"] = kwargs["device"]
        return nullcontext()

    client = SimpleNamespace(
        aio=SimpleNamespace(
            live=FakeLive(),
            aclose=close_client,
        )
    )
    monkeypatch.setattr("google.genai.Client", lambda **_: client)
    monkeypatch.setattr(local_assistant.sd, "InputStream", make_input_stream)
    monkeypatch.setattr("memory.config_manager.get_gemini_key", lambda: "test-key")
    monkeypatch.setattr("memory.config_manager.get_input_device", lambda: "Headset Mic")
    monkeypatch.setattr("core.audio_devices.resolve", lambda name, kind: 7)

    assistant = local_assistant.LocalAssistant.__new__(local_assistant.LocalAssistant)
    assistant._live_tools = []
    def messages(text):
        assert text == ""
        return [{"content": "test system prompt"}]

    assistant._messages = messages
    assistant._run_live_tools = lambda: {"response_modalities": ["AUDIO"]}
    assistant._stop = stop
    assistant._ready = threading.Event()
    assistant.ui = SimpleNamespace(set_state=lambda *_: None, write_log=lambda _: None)

    asyncio.run(assistant._run_live_session())

    assert captured["model"] == "gemini-3.8-live"
    assert captured["input_device"] == 7


def test_live_audio_sender_failure_is_propagated_and_receiver_cancelled():
    receiver_cancelled = asyncio.Event()

    async def sender():
        raise RuntimeError("microphone send failed")

    async def receiver():
        try:
            await asyncio.Event().wait()
        finally:
            receiver_cancelled.set()

    async def run():
        sender_task = asyncio.create_task(sender())
        receiver_task = asyncio.create_task(receiver())
        try:
            await local_assistant._wait_for_live_tasks(sender_task, receiver_task)
        except RuntimeError as exc:
            assert str(exc) == "microphone send failed"
        else:
            raise AssertionError("sender failure should be propagated")
        assert receiver_task.cancelled()

    asyncio.run(run())
    assert receiver_cancelled.is_set()


def test_live_receiver_continues_after_each_completed_turn():
    stop = threading.Event()
    handled = []

    class Session:
        def __init__(self):
            self.turn = 0

        def receive(self):
            turn = self.turn
            self.turn += 1

            async def messages():
                yield turn

            return messages()

    async def handle_message(message):
        handled.append(message)
        if len(handled) == 3:
            stop.set()

    asyncio.run(local_assistant._receive_live_turns(Session(), handle_message, stop))

    assert handled == [0, 1, 2]


def test_gemini_live_tool_declarations_use_uppercase_schema_types():
    declarations = [
        {
            "name": "open_app",
            "description": "Open an application.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "options": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                },
            },
        },
    ]

    assert _gemini_live_tools(declarations) == [
        {
            "function_declarations": [{
                "name": "open_app",
                "description": "Open an application.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING"},
                        "options": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                    },
                },
            }],
        }
    ]


@pytest.mark.parametrize(
    "utterance, expected",
    [
        ("volume low kr do", "volume_down"),
        ("volume kam karo", "volume_down"),
        ("awaz thoda kam kar do", "volume_down"),
        ("lower the volume", "volume_down"),
        ("volume down", "volume_down"),
        ("volume badha do", "volume_up"),
        ("turn the sound up", "volume_up"),
        ("my volume is low", None),
    ],
)
def test_quick_volume_intent(utterance, expected):
    assert _quick_volume_action(utterance) == expected


def test_volume_command_runs_locally_without_model_roundtrip():
    events = []
    assistant = local_assistant.LocalAssistant.__new__(local_assistant.LocalAssistant)
    assistant.ui = SimpleNamespace(set_state=events.append)
    assistant.assistant_name = "Doom"
    assistant._stop = threading.Event()
    assistant._log = events.append
    assistant._say = lambda text: events.append(f"SAY: {text}")

    def run_tool(name, args):
        events.append((name, args))
        return "Done: volume_down."

    assistant._run_tool = run_tool

    assistant._run_quick_volume_action("volume low kr do", "volume_down")

    assert ("computer_settings", {"action": "volume_down"}) in events
    assert "SAY: Volume kam kar diya." in events


def test_camera_tool_captures_image_and_opens_preview(monkeypatch):
    preview_calls = []
    assistant = local_assistant.LocalAssistant.__new__(local_assistant.LocalAssistant)
    assistant._pending_images = []
    assistant._camera_frame_lock = threading.Lock()
    assistant._camera_frame_event = threading.Event()
    assistant._latest_camera_frame = None

    def start_camera_stream(show):
        preview_calls.append(show)
        assistant._on_camera_frame(b"camera-image")
        return True

    assistant.ui = SimpleNamespace(
        start_camera_stream=start_camera_stream,
        stop_camera_stream=lambda: preview_calls.append("stopped"),
        show_camera_frame=lambda image: preview_calls.append(image),
    )

    result = assistant._run_tool("screen_process", {"angle": "camera", "text": "describe it"})

    assert "Camera captured" in result
    assert assistant._pending_images == [{
        "data": base64.b64encode(b"camera-image").decode("ascii"),
        "mime_type": "image/jpeg",
        "prompt": "describe it",
    }]
    assert preview_calls == [False, "stopped", b"camera-image"]


def test_camera_tool_does_not_stop_an_existing_camera_stream():
    assistant = local_assistant.LocalAssistant.__new__(local_assistant.LocalAssistant)
    assistant._pending_images = []
    assistant._camera_frame_lock = threading.Lock()
    assistant._camera_frame_event = threading.Event()
    assistant._latest_camera_frame = None
    events = []

    def start_existing_stream(show):
        assert show is False
        assistant._on_camera_frame(b"gesture-camera-frame")
        return False

    assistant.ui = SimpleNamespace(
        start_camera_stream=start_existing_stream,
        stop_camera_stream=lambda: events.append("stopped"),
        show_camera_frame=lambda image: events.append(image),
    )

    result = assistant._run_tool("screen_process", {"angle": "camera", "text": "identify"})

    assert "captured" in result
    assert events == [b"gesture-camera-frame"]


def test_repeated_camera_tool_requests_capture_distinct_frames():
    assistant = local_assistant.LocalAssistant.__new__(local_assistant.LocalAssistant)
    assistant._pending_images = []
    assistant._camera_frame_lock = threading.Lock()
    assistant._camera_frame_event = threading.Event()
    assistant._latest_camera_frame = None
    frames = iter((b"first-frame", b"second-frame"))

    def start_camera_stream(show):
        assistant._on_camera_frame(next(frames))
        return True

    assistant.ui = SimpleNamespace(
        start_camera_stream=start_camera_stream,
        stop_camera_stream=lambda: None,
        show_camera_frame=lambda _image: None,
    )

    for _ in range(2):
        result = assistant._run_tool(
            "screen_process", {"angle": "camera", "text": "what is this"}
        )
        assert "captured" in result

    assert [
        base64.b64decode(image["data"])
        for image in assistant._pending_images
    ] == [b"first-frame", b"second-frame"]


def test_camera_frame_callback_stores_latest_frame_without_streaming_it(monkeypatch):
    assistant = local_assistant.LocalAssistant.__new__(local_assistant.LocalAssistant)
    assistant._camera_frame_lock = threading.Lock()
    assistant._camera_frame_event = threading.Event()
    assistant._latest_camera_frame = None
    assistant._live_loop = None
    assistant._live_session = None

    assistant._on_camera_frame(b"fresh-frame")

    assert assistant._camera_frame_event.is_set()
    assert assistant._latest_camera_frame == b"fresh-frame"


def test_camera_tool_is_explicit_for_hinglish_object_requests():
    camera_tool = next(
        tool for tool in TOOL_DECLARATIONS if tool["name"] == "screen_process"
    )

    assert camera_tool["parameters"]["required"] == ["angle", "text"]
    assert "dekho ye kya hai" in camera_tool["description"]


def test_live_tool_sends_camera_image_before_tool_response():
    events = []

    class FakeTypes:
        @staticmethod
        def FunctionResponse(**kwargs):
            return kwargs

        @staticmethod
        def Blob(**kwargs):
            return kwargs

    class FakeSession:
        async def send_realtime_input(self, **kwargs):
            events.append(("image", kwargs["video"]["data"]))

        async def send_tool_response(self, **kwargs):
            events.append(("tool_response", kwargs["function_responses"]))

    assistant = local_assistant.LocalAssistant.__new__(local_assistant.LocalAssistant)
    assistant._pending_images = []

    def run_camera_tool(*_):
        assistant._pending_images.append({
            "data": base64.b64encode(b"camera-image").decode("ascii"),
            "mime_type": "image/jpeg",
            "prompt": "dekho ye kya hai",
        })
        return "Camera captured; analyzing it now."

    assistant._run_tool = run_camera_tool
    tool_call = SimpleNamespace(function_calls=[
        SimpleNamespace(
            name="screen_process",
            args={"angle": "camera", "text": "dekho ye kya hai"},
            id="call-1",
        ),
    ])

    asyncio.run(assistant._handle_live_tool_call(FakeSession(), tool_call, FakeTypes))

    assert events[0] == ("image", b"camera-image")
    assert events[1][0] == "tool_response"
    result = events[1][1][0]["response"]["result"]
    assert "dekho ye kya hai" in result
    assert "answer the user's request" in result
    assert assistant._pending_images == []


def test_discovery_log_hides_successful_loads_but_keeps_problems():
    logged = []
    assistant = local_assistant.LocalAssistant.__new__(local_assistant.LocalAssistant)
    assistant.ui = SimpleNamespace(write_log=logged.append)

    assistant._log_discovery("Action loaded: web_search (web_search.py)")
    assistant._log_discovery("Action rejected: broken.py — invalid tool")
    assistant._log_discovery("Action 'web_search' crashed during run(): failure")

    assert logged == [
        "SYS: Action rejected: broken.py — invalid tool",
        "SYS: Action 'web_search' crashed during run(): failure",
    ]
