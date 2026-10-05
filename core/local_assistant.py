"""Local-first desktop assistant runtime."""
from __future__ import annotations

import asyncio
import base64
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd

from actions.screen_processor import _capture_screen
from actions.system_monitor import get_system_status
from core.action_loader import discover_actions
from core import confirm as confirm_gate
from core.llm_client import configure_gemini
from core.plugin_loader import discover_plugins
from core.safety import check_action
from memory.config_manager import get_assistant_name, get_user_name
from memory.memory_manager import (
    format_memory_for_prompt,
    load_memory,
    search_memory,
    update_memory,
)


_AUDIO_RATE = 16_000
_AUDIO_CHUNK = 1_024
_AUDIO_BUFFER_CHUNKS = 16
_LIVE_AUDIO_BUFFER_CHUNKS = 64
_CAMERA_FRAME_TIMEOUT = 5.0
_AUDIO_STATUS_LOG_INTERVAL = 5.0


def _should_log_audio_status(
    status, last_logged_at: float | None, now: float,
) -> bool:
    return bool(status) and (
        last_logged_at is None
        or now - last_logged_at >= _AUDIO_STATUS_LOG_INTERVAL
    )


class _LiveAudioBuffer:
    """Bound microphone buffering and coalesce cross-thread event-loop wakeups."""

    def __init__(self, loop: asyncio.AbstractEventLoop, max_chunks: int):
        self._loop = loop
        self._chunks: queue.Queue[bytes] = queue.Queue(maxsize=max_chunks)
        self._ready = asyncio.Event()
        self._lock = threading.Lock()
        self._notification_pending = False

    def put_from_audio_callback(self, data: bytes) -> None:
        with self._lock:
            if self._chunks.full():
                self._chunks.get_nowait()
            self._chunks.put_nowait(data)
            if self._notification_pending:
                return
            self._notification_pending = True
            try:
                self._loop.call_soon_threadsafe(self._ready.set)
            except RuntimeError:
                self._notification_pending = False

    def discard_pending(self) -> None:
        with self._lock:
            while True:
                try:
                    self._chunks.get_nowait()
                except queue.Empty:
                    break

    async def get(self) -> bytes:
        while True:
            await self._ready.wait()
            with self._lock:
                try:
                    data = self._chunks.get_nowait()
                except queue.Empty:
                    if not self._chunks.empty():
                        continue
                    self._ready.clear()
                    self._notification_pending = False
                    continue
                if self._chunks.empty():
                    self._ready.clear()
                    self._notification_pending = False
                return data


def _gemini_live_tools(declarations: list[dict]) -> list[dict]:
    def normalize_schema(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (item.upper() if key == "type" and isinstance(item, str)
                      else normalize_schema(item))
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [normalize_schema(item) for item in value]
        return value

    return [{
        "function_declarations": [{
            "name": declaration["name"],
            "description": declaration.get("description", ""),
            "parameters": normalize_schema(declaration.get("parameters", {})),
        } for declaration in declarations]
    }] if declarations else []


async def _wait_for_live_tasks(sender: asyncio.Task, receiver: asyncio.Task) -> None:
    tasks = (sender, receiver)
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _receive_live_turns(session, handle_message, stop: threading.Event) -> None:
    while not stop.is_set():
        received_message = False
        async for message in session.receive():
            received_message = True
            await handle_message(message)
        if not received_message and not stop.is_set():
            raise RuntimeError("Gemini Live response stream ended unexpectedly.")


class LocalAssistant:
    """Run Gemini chat/voice requests and guarded desktop actions."""

    def __init__(self, ui, inline_tools: list[dict], base_dir: Path):
        self.ui = ui
        self.base_dir = base_dir
        self.assistant_name = get_assistant_name()
        self.user_name = get_user_name()
        self._speech: queue.Queue[str | None] = queue.Queue(maxsize=64)
        self._live_audio: queue.Queue[bytes | None] = queue.Queue(
            maxsize=_LIVE_AUDIO_BUFFER_CHUNKS
        )
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._is_speaking = threading.Event()
        self._speech_interrupt = threading.Event()
        self._pending_images: list[dict[str, str]] = []
        self._camera_frame_lock = threading.Lock()
        self._camera_frame_event = threading.Event()
        self._latest_camera_frame: bytes | None = None
        self._live_client = None
        self._live_session = None
        self._live_loop: asyncio.AbstractEventLoop | None = None
        self._wake_detector = None
        self._wake_enabled = False
        self._awake = True

        inline_names = {tool["name"] for tool in inline_tools}
        self._inline_tools = {
            tool["name"]: tool for tool in inline_tools
        }
        declarations = list(self._inline_tools.values())
        self._actions = discover_actions(
            actions_dir=base_dir / "actions",
            reserved_names=inline_names,
            logger=self._log_discovery,
        )
        self._plugins = discover_plugins(
            plugins_dir=base_dir / "plugins",
            core_tool_names=inline_names | self._actions.names(),
            logger=self._log_discovery,
        )
        self._live_tools = _gemini_live_tools(
            declarations
            + self._actions.get_tool_declarations()
            + self._plugins.get_tool_declarations()
        )

        self.ui.get_plugins = self._plugins.list_for_ui
        self.ui.get_plugin_settings = self._plugins.settings_schemas
        self.ui.request_say = self._say
        self.ui.on_text_command = self.handle_text
        self.ui.on_gesture_command = self._on_gesture
        self.ui.on_interrupt = self.interrupt
        self.ui.on_camera_frame = self._on_camera_frame
        self.ui.on_voice_change = self._reconnect_live
        self.ui.on_audio_device_change = self._reconnect_live
        from memory.config_manager import get_wake_word_enabled

        self._wake_enabled = bool(get_wake_word_enabled())
        self.ui.wake_is_ready = self._wake_is_ready
        self.ui.wake_get_state = self._wake_get_state
        self.ui.on_wake_toggle = self._toggle_wake_word
        self.ui.on_wake_manual = self._toggle_awake
        confirm_gate.bind(
            show=self.ui.show_confirm,
            hide=self.ui.hide_confirm,
            log=self.ui.write_log,
        )

    def start(self) -> None:
        threading.Thread(target=self._bootstrap, daemon=True, name="DoomBootstrap").start()
        threading.Thread(target=self._speech_output, daemon=True, name="DoomSpeech").start()
        threading.Thread(target=self._live_audio_output, daemon=True, name="DoomLiveAudio").start()
        from core.user_identity import get_display_name

        display_name = self.user_name or get_display_name()
        self._log(f"SYS: Hello, {display_name}. Doom is connecting to Gemini Live.")
        self._say(f"Hello, {display_name}.")

    def _log(self, text: str) -> None:
        self.ui.write_log(text)

    def _log_discovery(self, message: str) -> None:
        if message.startswith((
            "Action loaded:",
            "Action discovery complete:",
            "Plugin loaded:",
            "Plugin discovery complete:",
        )):
            return
        self._log(f"SYS: {message}")

    def _bootstrap(self) -> None:
        self.ui.set_state("THINKING")
        self._log("SYS: Connecting to Gemini Live. Internet access is required.")
        while not self._stop.is_set():
            try:
                self.ui.wait_for_api_key()
                configure_gemini()
                asyncio.run(self._run_live_session())
                if not self._stop.is_set():
                    self._log("SYS: Gemini Live session closed; reconnecting.")
            except Exception as exc:
                client, self._live_client = self._live_client, None
                if client is not None:
                    try:
                        asyncio.run(client.aio.aclose())
                    except Exception as close_error:
                        self._log(f"ERR: Gemini client cleanup failed — {close_error}")
                if self._stop.is_set():
                    break
                self.ui.set_state("SLEEPING")
                self._log(f"ERR: Gemini Live connection failed — {exc}")
                message = str(exc).lower()
                if any(term in message for term in (
                    "api key", "unauthenticated", "permission denied",
                )):
                    self.ui.prompt_reconfig()
            if self._stop.wait(2):
                break

    def handle_text(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        loop, session = self._live_loop, self._live_session
        if not self._ready.is_set() or loop is None or session is None:
            self._log("SYS: Gemini Live is still connecting. Please wait.")
            return
        self._log(f"You: {text}")
        future = asyncio.run_coroutine_threadsafe(
            session.send_realtime_input(text=text),
            loop,
        )

        def report_send_error(done):
            error = done.exception()
            if error is not None:
                self._log(f"ERR: Could not send message to Gemini Live — {error}")

        future.add_done_callback(report_send_error)

    def _run_live_tools(self) -> dict:
        from google.genai import types
        from memory.config_manager import get_voice

        messages = self._messages("")
        return {
            "response_modalities": ["AUDIO"],
            "system_instruction": messages[0]["content"],
            "speech_config": types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=get_voice(),
                    ),
                ),
            ),
            "input_audio_transcription": {},
            "output_audio_transcription": {},
            "realtime_input_config": {
                "automatic_activity_detection": {
                    "start_of_speech_sensitivity": "START_SENSITIVITY_HIGH",
                    "end_of_speech_sensitivity": "END_SENSITIVITY_LOW",
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 600,
                },
            },
            "tools": self._live_tools,
        }

    async def _run_live_session(self) -> None:
        from google import genai
        from google.genai import types
        from core.audio_devices import resolve
        from memory.config_manager import get_gemini_key, get_input_device

        api_key = get_gemini_key()
        if not api_key:
            raise RuntimeError("Gemini API key is missing. Enter it in the setup screen.")
        input_device = resolve(get_input_device(), "input")
        client = genai.Client(api_key=api_key)
        self._live_client = client
        config = self._run_live_tools()
        loop = asyncio.get_running_loop()
        audio_queue = _LiveAudioBuffer(loop, _AUDIO_BUFFER_CHUNKS)
        last_audio_status_log = None

        async with client.aio.live.connect(
            model="gemini-3.8-live",
            config=types.LiveConnectConfig(**config),
        ) as session:
            self._live_loop = loop
            self._live_session = session
            self._ready.set()
            self.ui.set_state("LISTENING")
            self._log("SYS: Gemini Live connected. Doom is ready.")

            def audio_callback(indata, frames, time_info, status) -> None:
                nonlocal last_audio_status_log
                if status:
                    now = time.monotonic()
                    if _should_log_audio_status(status, last_audio_status_log, now):
                        self._log(f"WRN: Microphone stream status — {status}")
                        last_audio_status_log = now
                if self._stop.is_set():
                    return
                if self.ui.muted:
                    audio_queue.discard_pending()
                    return
                audio = indata[:, 0].copy()
                if self._wake_detector is not None:
                    self._wake_detector.feed(audio)
                    if self._wake_enabled and not self._awake:
                        audio_queue.discard_pending()
                        return
                self.ui.set_audio_level(
                    min(1.0, float(np.sqrt(np.mean(audio.astype(np.float32) ** 2))) / 2600.0)
                )
                audio_queue.put_from_audio_callback(audio.tobytes())

            async def send_audio() -> None:
                while not self._stop.is_set():
                    audio = await audio_queue.get()
                    await session.send_realtime_input(
                        audio=types.Blob(data=audio, mime_type="audio/pcm;rate=16000")
                    )

            async def receive_responses() -> None:
                response_text = ""
                input_text = ""

                async def handle_message(message) -> None:
                    nonlocal response_text, input_text
                    if message.server_content:
                        content = message.server_content
                        if content.input_transcription and content.input_transcription.text:
                            input_text += content.input_transcription.text
                        if content.output_transcription and content.output_transcription.text:
                            response_text += content.output_transcription.text
                        if content.model_turn:
                            for part in content.model_turn.parts or []:
                                if part.text and not content.output_transcription:
                                    response_text += part.text
                                if part.inline_data and part.inline_data.data:
                                    self._queue_live_audio(part.inline_data.data)
                        if content.interrupted:
                            self.interrupt()
                        if content.turn_complete:
                            if input_text.strip():
                                self._log(f"You: {input_text.strip()}")
                                input_text = ""
                            if response_text.strip():
                                self._log(f"{self.assistant_name}: {response_text.strip()}")
                                response_text = ""
                            if not self._stop.is_set():
                                self.ui.set_state("LISTENING")
                    if message.tool_call:
                        await self._handle_live_tool_call(session, message.tool_call, types)

                await _receive_live_turns(session, handle_message, self._stop)

            try:
                with sd.InputStream(
                    samplerate=_AUDIO_RATE,
                    channels=1,
                    dtype="int16",
                    blocksize=_AUDIO_CHUNK,
                    device=input_device,
                    callback=audio_callback,
                ):
                    self._log("SYS: Microphone stream active. Speak now.")
                    sender = asyncio.create_task(send_audio())
                    receiver = asyncio.create_task(receive_responses())
                    await _wait_for_live_tasks(sender, receiver)
            finally:
                self._ready.clear()
                self._live_session = None
                self._live_loop = None
                self._live_client = None
                await client.aio.aclose()

    def _queue_live_audio(self, audio: bytes) -> None:
        if self._live_audio.full():
            try:
                self._live_audio.get_nowait()
            except queue.Empty:
                pass
        try:
            self._live_audio.put_nowait(audio)
        except queue.Full:
            self._log("WRN: Live audio playback buffer is full; a speech chunk was skipped.")
            return
        self._is_speaking.set()

    def _live_audio_output(self) -> None:
        try:
            from core.audio_devices import resolve
            from memory.config_manager import get_output_device

            output_device = resolve(get_output_device(), "output")
            with sd.RawOutputStream(
                samplerate=24_000,
                channels=1,
                dtype="int16",
                blocksize=2_400,
                device=output_device,
            ) as stream:
                while not self._stop.is_set():
                    try:
                        audio = self._live_audio.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    if audio is None:
                        break
                    self.ui.set_state("SPEAKING")
                    stream.write(audio)
                    if self._live_audio.empty():
                        self._is_speaking.clear()
                        self.ui.set_state("LISTENING")
        except Exception as exc:
            if not self._stop.is_set():
                self._log(f"ERR: Gemini Live audio playback unavailable — {exc}")

    async def _handle_live_tool_call(self, session, tool_call, types) -> None:
        responses = []
        for function_call in tool_call.function_calls or []:
            name = function_call.name or ""
            args = function_call.args or {}
            if not isinstance(args, dict):
                args = {}
            pending_before = len(self._pending_images)
            result = await asyncio.to_thread(self._run_tool, name, args)
            camera_image_captured = (
                name == "screen_process"
                and args.get("angle") == "camera"
                and len(self._pending_images) > pending_before
            )
            if camera_image_captured:
                request = str(args.get("text", "")).strip()
                if request:
                    result = (
                        f"{result} The camera image is being sent now. "
                        f"Inspect it and answer the user's request: {request}"
                    )
            responses.append(types.FunctionResponse(
                id=function_call.id,
                name=name,
                response={"result": result},
            ))
        images, self._pending_images = self._pending_images, []
        for image in images:
            await session.send_realtime_input(video=types.Blob(
                data=base64.b64decode(image["data"]),
                mime_type=image["mime_type"],
            ))
        if responses:
            await session.send_tool_response(function_responses=responses)

    def _on_camera_frame(self, image: bytes) -> None:
        with self._camera_frame_lock:
            self._latest_camera_frame = image
            self._camera_frame_event.set()

    def _reconnect_live(self) -> None:
        loop, session = self._live_loop, self._live_session
        if loop is not None and session is not None:
            asyncio.run_coroutine_threadsafe(session.close(), loop)

    def _wake_is_ready(self) -> bool:
        return bool(self._wake_detector and self._wake_detector.ready)

    def _wake_get_state(self) -> dict[str, bool]:
        return {
            "ready": self._wake_is_ready(),
            "enabled": self._wake_enabled,
            "awake": self._awake,
        }

    def _toggle_wake_word(self, enabled: bool) -> str:
        from memory.config_manager import save_wake_word_enabled

        if not enabled:
            self._wake_enabled = False
            save_wake_word_enabled(False)
            if self._wake_detector is not None:
                self._wake_detector.stop()
                self._wake_detector = None
            return "Wake word disabled."
        try:
            from core.wake_word import WakeWordDetector, is_ready

            if not is_ready():
                return "Wake-word model is not installed yet."
            detector = WakeWordDetector(
                on_detect=lambda: self._set_awake(True),
                logger=lambda message: self._log(f"SYS: {message}"),
            )
            if not detector.start():
                return "Wake-word detector could not start."
            self._wake_detector = detector
            self._wake_enabled = True
            self._awake = False
            save_wake_word_enabled(True)
            return "Wake word enabled. Say Hey Jarvis to wake Doom."
        except Exception as exc:
            self._log(f"ERR: Wake-word setup failed — {exc}")
            return f"Wake word could not be enabled: {exc}"

    def _set_awake(self, awake: bool) -> None:
        self._awake = awake
        self.ui.set_state("LISTENING" if awake else "SLEEPING")
        self._log("SYS: Doom is awake." if awake else "SYS: Doom is sleeping.")

    def _toggle_awake(self) -> None:
        self._set_awake(not self._awake)

    def _messages(self, text: str) -> list[dict]:
        prompt_path = self.base_dir / "core" / "prompt.txt"
        prompt = prompt_path.read_text(encoding="utf-8")

        memory = load_memory()
        memory_text = format_memory_for_prompt(memory)
        user_name = self.user_name
        if not user_name:
            from core.user_identity import get_display_name

            user_name = get_display_name()
        system = (
            f"{prompt}\n\n"
            f"Assistant name: {self.assistant_name}.\n"
            f"Address the user as {user_name}.\n"
            f"Current local time: {datetime.now().astimezone().isoformat()}.\n"
            "The language model uses Gemini online. Use a tool only when needed; "
            "online tools may access the internet only to fulfill the user's explicit request.\n"
            + (f"\nUser memory:\n{memory_text}" if memory_text else "")
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ]

    def _run_tool(self, name: str, args: dict) -> str:
        allowed, safety_message = check_action(name, args)
        if not allowed:
            self._log(f"SYS: Blocked unsafe tool — {name}")
            return str(safety_message)

        try:
            if name == "save_memory":
                category = str(args.get("category", "notes"))
                key = str(args.get("key", "")).strip()
                value = str(args.get("value", "")).strip()
                if not key or not value:
                    return "A memory key and value are required."
                update_memory({category: {key: {"value": value}}})
                return "Memory saved."
            if name == "recall_memory":
                return search_memory(str(args.get("query", "")), limit=8)
            if name == "undo":
                from core.undo import history, undo_last

                if str(args.get("action", "undo")).lower().strip() == "list":
                    entries = history()
                    return "\n".join(entries) if entries else "There is nothing to undo."
                return undo_last()
            if name == "system_status":
                return str(get_system_status())
            if name == "screen_process":
                angle = str(args.get("angle", "screen")).lower()
                if angle == "camera":
                    with self._camera_frame_lock:
                        self._latest_camera_frame = None
                        self._camera_frame_event.clear()
                    started_stream = self.ui.start_camera_stream(show=False)
                    try:
                        if not self._camera_frame_event.wait(_CAMERA_FRAME_TIMEOUT):
                            raise RuntimeError(
                                "Camera did not provide a frame. Check camera access and try again."
                            )
                    finally:
                        if started_stream:
                            self.ui.stop_camera_stream()
                    with self._camera_frame_lock:
                        image = self._latest_camera_frame
                    if image is None:
                        raise RuntimeError("Camera returned an empty frame. Try again.")
                    mime_type = "image/jpeg"
                    self.ui.show_camera_frame(image)
                else:
                    image, mime_type = _capture_screen()
                self._pending_images.append({
                    "data": base64.b64encode(image).decode("ascii"),
                    "mime_type": mime_type,
                    "prompt": str(args.get("text", "")).strip(),
                })
                return f"{angle.capitalize()} captured ({mime_type}); analyzing it now."
            if name == "close_camera":
                self.ui.stop_camera_stream()
                return "Camera closed."
            if name == "manage_monitor":
                from actions.background_monitor import add_monitor, list_monitors, remove_monitor

                action = str(args.get("action", "")).lower().strip()
                topic = str(args.get("topic", "")).strip()
                if action == "list":
                    topics = list_monitors()
                    return "Monitoring: " + ", ".join(topics) if topics else "No topics are being monitored."
                if action == "add" and topic:
                    return add_monitor(topic)
                if action == "remove" and topic:
                    return remove_monitor(topic)
                return "Specify add/remove with a topic, or list."
            if name == "shutdown_assistant":
                self._say("Shutting down.")
                self.ui._app.quit()
                return "Doom is closing."
            if self._actions.has(name):
                context = {
                    "player": self.ui,
                    "speak": self._say,
                    "response": None,
                    "session_memory": None,
                }
                result = self._actions.run(name, args, context)
                return str(result or "Done.")
            if self._plugins.has(name):
                result = self._plugins.run(
                    name, args, player=self.ui, session_memory=None,
                )
                return str(result or "Done.")
            return f"Unknown tool: {name}"
        except Exception as exc:
            self._log(f"ERR: Tool '{name}' failed — {exc}")
            return f"Tool '{name}' failed: {exc}"

    def _on_gesture(self, command: str) -> None:
        self.handle_text(f"Gesture input: {command}. Perform the matching safe action.")

    def _say(self, text: str) -> None:
        if self.ui.muted or not text.strip():
            return
        try:
            self._speech.put_nowait(text.strip())
        except queue.Full:
            self._log("WRN: Speech queue is full; a spoken sentence was skipped.")

    def _speech_output(self) -> None:
        try:
            import pythoncom
            import win32com.client
        except ImportError as exc:
            self._log(f"ERR: Windows speech output is unavailable — {exc}")
            return

        pythoncom.CoInitialize()
        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            while not self._stop.is_set():
                text = self._speech.get()
                if text is None:
                    break
                if self.ui.muted:
                    continue
                self._speech_interrupt.clear()
                self._is_speaking.set()
                self.ui.set_state("SPEAKING")
                try:
                    voice.Speak(text, 1)
                    while not voice.WaitUntilDone(100):
                        if self._speech_interrupt.is_set() or self._stop.is_set():
                            voice.Speak("", 3)
                            break
                except Exception as exc:
                    self._log(f"ERR: Speech output failed — {exc}")
                finally:
                    self._is_speaking.clear()
                    if not self._stop.is_set():
                        self.ui.set_state("LISTENING")
        finally:
            pythoncom.CoUninitialize()

    def interrupt(self) -> None:
        self._speech_interrupt.set()
        while True:
            try:
                self._speech.get_nowait()
            except queue.Empty:
                break
        while True:
            try:
                self._live_audio.get_nowait()
            except queue.Empty:
                break
        self._log("SYS: Cleared queued speech.")

    def stop(self) -> None:
        self._stop.set()
        loop, session = self._live_loop, self._live_session
        if loop is not None and session is not None:
            asyncio.run_coroutine_threadsafe(session.close(), loop)
        self.interrupt()
        try:
            self._speech.put_nowait(None)
        except queue.Full:
            self.interrupt()
            self._speech.put_nowait(None)
        try:
            self.ui.stop_camera_stream()
        except RuntimeError:
            self._log("SYS: Camera UI already closed.")
