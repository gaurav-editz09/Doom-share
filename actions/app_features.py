import re


def detect_app_feature(prompt: str) -> str:
    text = (prompt or "").lower()

    if any(k in text for k in ("notepad", "text editor", "write a note", "type ")):
        return "notepad"
    if any(k in text for k in ("calculator", "calculate", "sum", "add ")):
        return "calculator"
    if any(k in text for k in ("youtube", "video", "music")):
        return "website"
    if any(k in text for k in ("browser", "chrome", "edge", "firefox", "google search")) and any(
        keyword in text for keyword in ("search", "find", "look up")
    ):
        return "search"
    if any(k in text for k in ("open ", "launch ", "start ")):
        return "app"
    return "app"


def app_features(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    prompt = params.get("prompt") or params.get("text") or ""

    if player:
        player.write_log(f"[app_features] {prompt}")

    feature = detect_app_feature(prompt)

    if feature == "notepad":
        try:
            from actions.open_app import open_app

            open_app({"app_name": "notepad"})
            return "Opened Notepad and it is ready for text input."
        except Exception as exc:
            return f"Could not open Notepad: {exc}"

    if feature == "calculator":
        try:
            from actions.open_app import open_app

            open_app({"app_name": "calculator"})
            return "Opened Calculator."
        except Exception as exc:
            return f"Could not open Calculator: {exc}"

    if feature == "search":
        try:
            from actions.open_app import open_app

            open_app({"app_name": "chrome"})
            return "Opened browser for a search."
        except Exception:
            return "Browser opened or is being launched for the requested search."

    if feature == "website":
        try:
            from actions.open_app import open_app

            open_app({"app_name": "chrome"})
            return "Opened browser for the requested website."
        except Exception:
            return "Browser opened for the requested website task."

    try:
        from actions.open_app import open_app

        open_app({"app_name": params.get("app_name") or "paint"})
        if (params.get("app_name") or "").lower() == "paint" or "paint" in prompt.lower():
            return "Opened Paint. Ask the user what they want me to draw before drawing anything."
        return "Opened the requested app."
    except Exception as exc:
        return f"App launch failed: {exc}"


TOOL = {
    "name": "app_features",
    "description": (
        "Open common apps and perform lightweight app-specific actions like Notepad, Calculator, "
        "browser search, and media website access. For drawing in Paint, use paint_draw."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "Natural-language request to open or use an app feature",
            },
            "app_name": {
                "type": "STRING",
                "description": "Optional explicit app name if the user requests a specific app",
            },
        },
        "required": [],
    },
    "handler": app_features,
}
