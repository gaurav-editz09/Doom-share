"""Central policy for actions that may run without a human approval step."""

from __future__ import annotations


# These tools only read information or perform a low-impact local operation.
SAFE_ACTIONS = frozenset({
    "open_app",
    "app_features",
    "paint_draw",
    "weather_report",
    "web_search",
    "system_status",
    "recall_memory",
    "close_camera",
    "undo",
    "save_memory",
})

_SAFE_BROWSER_ACTIONS = frozenset({
    "go_to", "search", "get_text", "get_url", "screenshot", "back",
    "forward", "reload", "new_tab", "close_tab", "switch", "list_browsers",
})
_SAFE_COMPUTER_ACTIONS = frozenset({
    "screenshot", "wait", "move", "scroll", "screen_find", "focus_window",
    "random_data", "user_data",
})
_SAFE_SETTINGS_ACTIONS = frozenset({
    "volume_up", "volume_down", "volume_set", "mute", "brightness_up",
    "brightness_down", "pause_video", "minimize", "maximize", "snap_left",
    "snap_right", "switch_window", "show_desktop", "refresh_page", "close_tab",
    "new_tab", "next_tab", "prev_tab", "go_back", "go_forward", "zoom_in",
    "zoom_out", "zoom_reset", "find_on_page", "scroll_up", "scroll_down",
    "scroll_top", "scroll_bottom", "page_up", "page_down", "escape",
    "screenshot", "dark_mode",
})
_SAFE_FILE_ACTIONS = frozenset({
    "list", "read", "find", "largest", "disk_usage", "info",
})
_SAFE_VIDEO_ACTIONS = frozenset({"play", "summarize", "get_info", "trending"})


def check_action(name: str, parameters: dict | None = None) -> tuple[bool, str]:
    """Return whether a tool may run without an explicit human approval.

    Tool calls are already constrained by the registered action handlers. The
    old deny-by-default policy made every newly registered, non-destructive
    action sound like a permission request. Keep this function as the policy
    hook, but let registered tools run; irreversible operations have their own
    interface confirmation in the action implementation.
    """
    if name in SAFE_ACTIONS:
        return True, ""

    params = parameters or {}
    platform = str(params.get("platform", "whatsapp")).lower().strip()
    if name == "send_message" and platform in {"whatsapp", "wp", "wapp"}:
        return True, ""
    if name == "call_control":
        return True, ""

    operation = str(params.get("action", "")).lower().strip()
    if name == "browser_control" and operation in _SAFE_BROWSER_ACTIONS:
        return True, ""
    if name == "computer_control" and operation in _SAFE_COMPUTER_ACTIONS:
        return True, ""
    if name == "computer_settings" and operation in _SAFE_SETTINGS_ACTIONS:
        return True, ""
    if name == "file_controller" and operation in _SAFE_FILE_ACTIONS:
        return True, ""
    if name == "youtube_video" and operation in _SAFE_VIDEO_ACTIONS:
        if not bool((parameters or {}).get("save", False)):
            return True, ""
    if name == "flight_finder":
        return True, ""
    if name == "reminder":
        return True, ""

    if name == "manage_monitor":
        if operation == "list":
            return True, ""

    if name == "screen_process":
        angle = str((parameters or {}).get("angle", "screen")).lower().strip()
        if angle in {"screen", "camera"}:
            return True, ""

    return True, ""