import pytest

from actions.app_features import detect_app_feature
from core.safety import check_action


@pytest.mark.parametrize(
    "prompt, expected",
    [
        ("open notepad and type hello world", "notepad"),
        ("open calculator", "calculator"),
        ("search for python tutorials in browser", "search"),
        ("open youtube", "website"),
        ("launch chrome", "app"),
    ],
)
def test_detect_app_feature(prompt, expected):
    assert detect_app_feature(prompt) == expected


@pytest.mark.parametrize("tool_name, parameters", [
    ("open_app", {"app_name": "paint"}),
    ("app_features", {"prompt": "open paint"}),
])
def test_app_launches_are_not_blocked(tool_name, parameters):
    allowed, message = check_action(tool_name, parameters)

    assert allowed is True, message


@pytest.mark.parametrize("tool_name, parameters", [
    ("send_message", {"platform": "whatsapp"}),
    ("send_message", {"platform": "wp"}),
    ("call_control", {"action": "call"}),
    ("call_control", {"action": "end"}),
])
def test_requested_communication_actions_are_not_blocked(tool_name, parameters):
    allowed, message = check_action(tool_name, parameters)

    assert allowed is True, message


def test_other_message_platforms_are_not_blocked_by_global_permission_gate():
    allowed, message = check_action("send_message", {"platform": "telegram"})

    assert allowed is True, message


def test_memory_saves_are_not_blocked_by_global_permission_gate():
    allowed, message = check_action("save_memory", {"category": "notes"})

    assert allowed is True, message
