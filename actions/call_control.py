import platform
import subprocess
import time

try:
    import pyautogui

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.04
    _PYAUTOGUI = True
except ImportError:  # pragma: no cover
    _PYAUTOGUI = False


_CALL_ACTIONS = {
    "call": ("call ", "call mom", "call dad", "dial ", "make a call", "start call"),
    "answer": ("answer", "accept", "pick up", "accept call"),
    "end": ("end call", "cut the call", "hang up", "disconnect", "stop call"),
    "mute": ("mute", "mute call", "silence", "turn off sound"),
    "unmute": ("unmute", "turn on sound", "sound on"),
    "speaker": ("speaker", "speaker on", "speakerphone", "hands free"),
    "video": ("video call", "start video", "turn on camera"),
}


def detect_call_action(prompt: str) -> str:
    text = (prompt or "").lower().strip()

    if not text:
        return "call"

    if "unmute" in text:
        return "unmute"
    if "mute" in text:
        return "mute"

    for action, keywords in _CALL_ACTIONS.items():
        if any(keyword in text for keyword in keywords):
            return action

    if "call" in text:
        return "call"
    if "hang" in text or "disconnect" in text:
        return "end"
    if "answer" in text or "accept" in text:
        return "answer"
    return "call"


def _windows_call(contact: str | None = None) -> str:
    if platform.system() != "Windows":
        raise RuntimeError("This call automation is Windows-only for now.")

    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI is not installed.")

    # Use the default phone app / calling shortcut if one is already open,
    # otherwise fall back to the Start Menu search for a calling app.
    if contact:
        pyautogui.press("win")
        time.sleep(0.5)
        pyautogui.write(contact, interval=0.08)
        time.sleep(0.6)
        pyautogui.press("enter")
        time.sleep(2.0)
        return f"Initiated a call flow for {contact}."

    pyautogui.hotkey("win", "a")
    time.sleep(0.6)
    return "Opened the Windows app launcher for calls."


def _windows_call_control(action: str) -> str:
    if platform.system() != "Windows":
        raise RuntimeError("This call automation is Windows-only for now.")

    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI is not installed.")

    action = action.lower()

    if action == "end":
        pyautogui.hotkey("alt", "f4")
        return "Ended the active call or closed the current call window."
    if action == "mute":
        pyautogui.hotkey("ctrl", "d")
        return "Muted the call."
    if action == "unmute":
        pyautogui.hotkey("ctrl", "d")
        return "Unmuted the call."
    if action == "answer":
        pyautogui.press("enter")
        return "Accepted the incoming call."
    if action == "speaker":
        pyautogui.hotkey("ctrl", "shift", "f")
        return "Enabled speaker mode."
    if action == "video":
        pyautogui.hotkey("ctrl", "shift", "v")
        return "Toggled video on for the call."
    return f"Call action '{action}' is queued for the active calling app."


def call_control(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    prompt = params.get("prompt") or params.get("text") or ""
    action = params.get("action") or detect_call_action(prompt)
    contact = params.get("contact") or params.get("name") or params.get("person")

    if player:
        player.write_log(f"[call_control] {action} {contact or ''}")

    try:
        if action in {"call", "answer", "end", "mute", "unmute", "speaker", "video"}:
            if action == "call":
                if contact:
                    return _windows_call(contact)
                return "Call action received. Please specify a contact name or number."
            return _windows_call_control(action)
        return f"Unsupported call action: {action}"
    except Exception as exc:
        return f"Call control failed: {exc}"


TOOL = {
    "name": "call_control",
    "description": "Handle call-related voice automation: call, answer, hang up, mute, unmute, speakerphone, and video-call controls using the active calling app.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "Natural-language voice command like 'call mom' or 'cut the call'",
            },
            "action": {
                "type": "STRING",
                "description": "Optional explicit action: call | answer | end | mute | unmute | speaker | video",
            },
            "contact": {
                "type": "STRING",
                "description": "Name or number to call",
            },
        },
        "required": [],
    },
    "handler": call_control,
}
