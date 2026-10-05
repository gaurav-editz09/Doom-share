import math
import platform
import subprocess
import time

try:
    import pyautogui

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.02
    _PYAUTOGUI = True
except ImportError:  # pragma: no cover - exercised only when pyautogui is absent
    _PYAUTOGUI = False


_SHAPES = {
    "circle": ("circle", "round", "oval", "loop"),
    "square": ("square", "rectangle", "box", "cube"),
    "house": ("house", "home", "roof"),
    "smiley": ("smiley", "smile", "happy face", "face"),
    "star": ("star", "sparkle", "five-point star"),
    "heart": ("heart", "love"),
    "triangle": ("triangle", "pyramid"),
    "tree": ("tree", "pine", "plant"),
    "sun": ("sun", "sunshine"),
    "flower": ("flower", "rose", "blossom"),
    "car": ("car", "auto", "vehicle"),
    "rocket": ("rocket", "launch", "spaceship"),
    "line": ("line", "straight line", "slash"),
    "scribble": ("scribble", "sketch", "draw", "doodle"),
}


def detect_draw_action(prompt: str) -> str:
    """Return a normalized draw target from a natural-language prompt."""
    text = (prompt or "").lower()
    for shape, keywords in _SHAPES.items():
        if any(keyword in text for keyword in keywords):
            return shape
    if any(word in text for word in ("draw", "sketch", "paint", "doodle")):
        return "scribble"
    return "scribble"


def _open_paint() -> None:
    if platform.system() == "Windows":
        subprocess.Popen(
            ["mspaint.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
    else:
        try:
            from actions.open_app import open_app

            open_app({"app_name": "paint"})
        except Exception:
            pass
    time.sleep(2.0)


def _draw_path(points):
    if not points or not _PYAUTOGUI:
        return

    x0, y0 = points[0]
    pyautogui.moveTo(x0, y0, duration=0.2)
    pyautogui.mouseDown(x0, y0)
    try:
        # Paint can miss very short mouse moves, especially around corners.
        # Use dragTo for a real continuous stroke; plain moveTo while the button is held
        # can be interpreted as a sequence of disconnected clicks in Windows Paint.
        for x1, y1 in points[1:]:
            distance = max(abs(x1 - x0), abs(y1 - y0))
            steps = max(1, distance // 4)
            for step in range(1, steps + 1):
                x = x0 + (x1 - x0) * step // steps
                y = y0 + (y1 - y0) * step // steps
                pyautogui.dragTo(x, y, duration=0.01)
            x0, y0 = x1, y1
    finally:
        pyautogui.mouseUp()


def _draw_circle(cx: int, cy: int, radius: int):
    points = []
    for i in range(0, 361, 8):
        angle = math.radians(i)
        x = int(cx + radius * math.cos(angle))
        y = int(cy + radius * math.sin(angle))
        points.append((x, y))
    _draw_path(points)


def _draw_square(cx: int, cy: int, half: int):
    points = [
        (cx - half, cy - half),
        (cx + half, cy - half),
        (cx + half, cy + half),
        (cx - half, cy + half),
        (cx - half, cy - half),
    ]
    _draw_path(points)


def _draw_triangle(cx: int, cy: int, size: int):
    points = [
        (cx, cy - size),
        (cx + size, cy + size),
        (cx - size, cy + size),
        (cx, cy - size),
    ]
    _draw_path(points)


def _draw_house(cx: int, cy: int, size: int):
    base = [
        (cx - size, cy),
        (cx + size, cy),
        (cx + size, cy + size),
        (cx - size, cy + size),
        (cx - size, cy),
    ]
    roof = [
        (cx - size, cy),
        (cx, cy - size),
        (cx + size, cy),
    ]
    door = [
        (cx - size // 3, cy),
        (cx - size // 3, cy + size // 2),
        (cx + size // 3, cy + size // 2),
        (cx + size // 3, cy),
    ]
    _draw_path(base)
    _draw_path(roof)
    _draw_path(door)


def _draw_smiley(cx: int, cy: int, radius: int):
    _draw_circle(cx, cy, radius)
    eye_r = max(6, radius // 8)
    _draw_circle(cx - radius // 3, cy - radius // 4, eye_r)
    _draw_circle(cx + radius // 3, cy - radius // 4, eye_r)
    arc = []
    for i in range(200, 340, 10):
        angle = math.radians(i)
        x = int(cx + (radius * 0.7) * math.cos(angle))
        y = int(cy + (radius * 0.45) * math.sin(angle))
        arc.append((x, y))
    _draw_path(arc)


def _draw_star(cx: int, cy: int, radius: int):
    points = []
    for i in range(10):
        angle = math.radians((i * 36) - 90)
        rr = radius if i % 2 == 0 else radius * 0.45
        x = int(cx + rr * math.cos(angle))
        y = int(cy + rr * math.sin(angle))
        points.append((x, y))
    points.append(points[0])
    _draw_path(points)


def _draw_heart(cx: int, cy: int, size: int):
    points = []
    for i in range(0, 180, 5):
        angle = math.radians(i)
        x = int(cx + size * 16 * math.sin(angle) ** 3)
        y = int(cy - size * (13 * math.cos(angle) - 5 * math.cos(2 * angle) - 2 * math.cos(3 * angle) - math.cos(4 * angle)))
        points.append((x, y))
    _draw_path(points)


def _draw_rocket(cx: int, cy: int, size: int):
    outline = [
        (cx, cy - size),
        (cx + size * 0.7, cy + size * 0.4),
        (cx + size * 0.25, cy + size * 1.2),
        (cx - size * 0.25, cy + size * 1.2),
        (cx - size * 0.7, cy + size * 0.4),
        (cx, cy - size),
    ]
    _draw_path(outline)
    _draw_path([(cx - 15, cy + size * 0.8), (cx + 15, cy + size * 0.8)])
    _draw_path([(cx, cy - size), (cx, cy + size)])


def _draw_tree(cx: int, cy: int, size: int):
    _draw_path([
        (cx, cy - size), (cx + size, cy), (cx + size // 2, cy),
        (cx + size * 3 // 4, cy + size // 2),
        (cx + size // 4, cy + size // 2),
        (cx + size // 2, cy + size), (cx - size // 2, cy + size),
        (cx - size // 4, cy + size // 2),
        (cx - size * 3 // 4, cy + size // 2), (cx - size // 2, cy),
        (cx, cy - size),
    ])
    _draw_path([
        (cx - size // 5, cy + size), (cx - size // 5, cy + size * 2),
        (cx + size // 5, cy + size * 2), (cx + size // 5, cy + size),
    ])


def _draw_sun(cx: int, cy: int, radius: int):
    _draw_circle(cx, cy, radius // 2)
    for angle in range(0, 360, 45):
        direction = math.radians(angle)
        inner = radius * 2 // 3
        outer = radius
        _draw_path([
            (int(cx + inner * math.cos(direction)), int(cy + inner * math.sin(direction))),
            (int(cx + outer * math.cos(direction)), int(cy + outer * math.sin(direction))),
        ])


def _draw_flower(cx: int, cy: int, size: int):
    petal_offset = size // 2
    for px, py in (
        (cx, cy - petal_offset), (cx + petal_offset, cy),
        (cx, cy + petal_offset), (cx - petal_offset, cy),
    ):
        _draw_circle(px, py, size // 3)
    _draw_circle(cx, cy, size // 4)
    _draw_path([(cx, cy + size // 2), (cx, cy + size * 2)])
    _draw_path([(cx, cy + size), (cx - size // 2, cy + size // 2)])


def _draw_car(cx: int, cy: int, size: int):
    body = [
        (cx - size, cy), (cx - size // 2, cy - size // 2),
        (cx + size // 2, cy - size // 2), (cx + size, cy),
        (cx + size, cy + size // 2), (cx - size, cy + size // 2),
        (cx - size, cy),
    ]
    _draw_path(body)
    _draw_circle(cx - size * 2 // 3, cy + size // 2, size // 5)
    _draw_circle(cx + size * 2 // 3, cy + size // 2, size // 5)


def _draw_scribble(cx: int, cy: int, radius: int):
    points = []
    for i in range(0, 200, 12):
        angle = math.radians(i * 3)
        x = int(cx + (radius * 0.8 * math.sin(angle * 2)) + ((i % 5) * 8))
        y = int(cy + (radius * 0.7 * math.cos(angle * 3)) + ((i % 7) * 5))
        points.append((x, y))
    _draw_path(points)


def _draw_shape(shape: str):
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI is not installed. Run: pip install pyautogui")

    cx, cy = pyautogui.position()
    radius = 120

    if shape == "circle":
        _draw_circle(cx, cy, radius)
    elif shape == "square":
        _draw_square(cx, cy, radius)
    elif shape == "triangle":
        _draw_triangle(cx, cy, radius)
    elif shape == "house":
        _draw_house(cx, cy, radius)
    elif shape == "smiley":
        _draw_smiley(cx, cy, radius)
    elif shape == "star":
        _draw_star(cx, cy, radius)
    elif shape == "heart":
        _draw_heart(cx, cy, radius)
    elif shape == "rocket":
        _draw_rocket(cx, cy, radius)
    elif shape == "tree":
        _draw_tree(cx, cy, radius)
    elif shape == "sun":
        _draw_sun(cx, cy, radius)
    elif shape == "flower":
        _draw_flower(cx, cy, radius)
    elif shape == "car":
        _draw_car(cx, cy, radius)
    elif shape == "line":
        _draw_path([(cx - radius, cy), (cx + radius, cy)])
    else:
        _draw_scribble(cx, cy, radius)


def paint_draw(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    prompt = params.get("prompt") or params.get("text") or ""
    requested_shape = params.get("shape")
    shape = requested_shape or detect_draw_action(prompt)
    explicit_shape = bool(requested_shape) or any(
        keyword in (prompt or "").lower() for keywords in _SHAPES.values() for keyword in keywords
    )
    drawing_intent = any(
        word in (prompt or "").lower() for word in ("draw", "sketch", "doodle", "make", "create")
    )

    if player:
        player.write_log(f"[paint_draw] {shape}")

    try:
        _open_paint()
        if not explicit_shape and not drawing_intent:
            return "Paint is open. Ask the user what they want me to draw, then draw that object."
        if not explicit_shape:
            return "Paint is open, but the object is unclear. Ask the user what they want me to draw."
        _draw_shape(shape)
        return f"Opened Paint and drew a {shape}."
    except Exception as exc:
        return f"Paint drawing failed: {exc}"


TOOL = {
    "name": "paint_draw",
        "description": (
            "Open Paint first when the user only asks to open it, then ask what to draw. "
            "When the user names an object, draw a clear basic multi-stroke version of it."
        ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "Natural-language request such as 'draw a circle' or 'make a house in paint'",
            },
            "shape": {
                "type": "STRING",
                "description": "Optional explicit shape: circle | square | house | smiley | star | heart | rocket | triangle | tree | sun | flower | car | line | scribble",
            },
        },
        "required": [],
    },
    "handler": paint_draw,
}
