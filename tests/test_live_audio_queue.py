import queue
import threading

from core.local_assistant import LocalAssistant


def test_interrupt_clears_queued_speech_and_sets_interrupt_flag():
    assistant = LocalAssistant.__new__(LocalAssistant)
    assistant._speech = queue.Queue()
    assistant._live_audio = queue.Queue()
    assistant._speech_interrupt = threading.Event()
    assistant._speech.put_nowait("stale response")
    assistant._live_audio.put_nowait(b"stale audio")
    assistant._log = lambda _message: None

    assistant.interrupt()

    assert assistant._speech.empty()
    assert assistant._live_audio.empty()
    assert assistant._speech_interrupt.is_set()
