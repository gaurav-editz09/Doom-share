import pytest

from actions.call_control import detect_call_action


@pytest.mark.parametrize(
    "prompt, expected",
    [
        ("call mom", "call"),
        ("cut the call", "end"),
        ("mute the call", "mute"),
        ("unmute call", "unmute"),
        ("answer the incoming call", "answer"),
        ("speaker on", "speaker"),
    ],
)
def test_detect_call_action(prompt, expected):
    assert detect_call_action(prompt) == expected
