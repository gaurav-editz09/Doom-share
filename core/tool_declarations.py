"""Inline tools implemented directly by the local desktop assistant."""

TOOL_DECLARATIONS = [
    {
        "name": "system_status",
        "description": "Read current CPU, memory, GPU, temperature, and uptime metrics.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "screen_process",
        "description": (
            "Capture and inspect the screen or webcam. For a real-world object, "
            "or when the user says 'dekho ye kya hai', 'what is this', or asks you "
            "to look at something, immediately call this with angle='camera'. "
            "Use angle='screen' only when the user explicitly asks about their display. "
            "After capture, describe what is visible and answer the user's text request."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "angle": {"type": "string", "enum": ["screen", "camera"]},
                "text": {"type": "string", "description": "What the user wants to know about the image."},
            },
            "required": ["angle", "text"],
        },
    },
    {
        "name": "close_camera",
        "description": "Close the live webcam view.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "save_memory",
        "description": "Save a personal fact only when the user asks you to remember it.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "key": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["category", "key", "value"],
        },
    },
    {
        "name": "recall_memory",
        "description": "Search personal facts stored in Doom's local memory.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "undo",
        "description": "Undo the last reversible change Doom made, or list undoable changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["undo", "list"]},
            },
            "required": [],
        },
    },
    {
        "name": "shutdown_assistant",
        "description": "Close Doom when the user explicitly asks to exit the assistant.",
        "parameters": {"type": "object", "properties": {}},
    },
]
