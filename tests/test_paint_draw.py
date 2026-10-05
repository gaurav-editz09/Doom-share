import pytest

from actions import paint_draw as paint_draw_module
from actions.paint_draw import detect_draw_action
from core.safety import check_action


@pytest.mark.parametrize(
    "prompt, expected",
    [
        ("open paint and draw a circle", "circle"),
        ("make a house in paint", "house"),
        ("draw a smiley face", "smiley"),
        ("sketch a rocket", "rocket"),
        ("paint a square", "square"),
        ("just doodle something random", "scribble"),
    ],
)
def test_detect_draw_action(prompt, expected):
    assert detect_draw_action(prompt) == expected


def test_paint_draw_is_not_blocked():
    allowed, message = check_action("paint_draw", {"prompt": "draw a circle"})

    assert allowed is True, message


def test_open_paint_waits_for_object(monkeypatch):
    opened = []
    monkeypatch.setattr(paint_draw_module, "_open_paint", lambda: opened.append(True))

    result = paint_draw_module.paint_draw({"prompt": "open paint"})

    assert opened == [True]
    assert "ask the user" in result.lower()


def test_named_shape_draws_many_mouse_events(monkeypatch):
    paths = []
    drag_calls = []
    monkeypatch.setattr(paint_draw_module, "_open_paint", lambda: None)
    monkeypatch.setattr(paint_draw_module, "_PYAUTOGUI", True)
    monkeypatch.setattr(paint_draw_module.pyautogui, "size", lambda: (1200, 800))
    monkeypatch.setattr(paint_draw_module.pyautogui, "moveTo", lambda *args, **kwargs: paths.append(args[:2]))
    monkeypatch.setattr(paint_draw_module.pyautogui, "dragTo", lambda *args, **kwargs: drag_calls.append(args[:2]))
    monkeypatch.setattr(paint_draw_module.pyautogui, "mouseDown", lambda *args, **kwargs: None)
    monkeypatch.setattr(paint_draw_module.pyautogui, "mouseUp", lambda: None)

    result = paint_draw_module.paint_draw({"prompt": "draw a house"})

    assert result.endswith("drew a house.")
    assert len(paths) >= 1
    assert len(drag_calls) > 0


def test_open_app_maximizes_after_launch(monkeypatch):
    launch_calls = []
    maximize_calls = []

    monkeypatch.setattr(paint_draw_module, "_PYAUTOGUI", True)
    monkeypatch.setattr("actions.open_app._SYSTEM", "Windows")
    monkeypatch.setattr(
        "actions.open_app._OS_LAUNCHERS",
        {"Windows": lambda app_name: launch_calls.append(app_name) or True},
    )
    monkeypatch.setattr("actions.open_app._maximize_window_after_launch", lambda: maximize_calls.append(True))

    from actions import open_app as open_app_module

    result = open_app_module.open_app({"app_name": "chrome"})

    assert result == "Opened chrome."
    assert launch_calls == ["chrome"]
    assert maximize_calls == [True]


def test_draw_shape_uses_current_mouse_position(monkeypatch):
    positions = []
    monkeypatch.setattr(paint_draw_module, "_PYAUTOGUI", True)
    monkeypatch.setattr(paint_draw_module.pyautogui, "position", lambda: (320, 240))
    monkeypatch.setattr(paint_draw_module.pyautogui, "size", lambda: (1200, 800))
    monkeypatch.setattr(paint_draw_module, "_draw_circle", lambda cx, cy, radius: positions.append((cx, cy, radius)))

    paint_draw_module._draw_shape("circle")

    assert positions == [(320, 240, 120)]


def test_draw_path_uses_drag_for_continuous_strokes(monkeypatch):
    drag_calls = []
    mouse_down_calls = []
    monkeypatch.setattr(paint_draw_module, "_PYAUTOGUI", True)
    monkeypatch.setattr(paint_draw_module.pyautogui, "moveTo", lambda *args, **kwargs: None)
    monkeypatch.setattr(paint_draw_module.pyautogui, "dragTo", lambda *args, **kwargs: drag_calls.append(args[:2]))
    monkeypatch.setattr(paint_draw_module.pyautogui, "mouseDown", lambda *args, **kwargs: mouse_down_calls.append(args[:2]))
    monkeypatch.setattr(paint_draw_module.pyautogui, "mouseUp", lambda *args, **kwargs: None)

    paint_draw_module._draw_path([(10, 10), (20, 10), (30, 30)])

    assert mouse_down_calls == [(10, 10)]
    assert drag_calls
    assert drag_calls[0][0] in (15, 20)
    assert drag_calls[0][1] == 10
