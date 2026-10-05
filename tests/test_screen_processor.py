import numpy as np

from actions import screen_processor
from core.safety import check_action


def test_camera_vision_is_allowed_without_extra_confirmation():
    allowed, message = check_action("screen_process", {"angle": "camera"})

    assert allowed is True
    assert message == ""


def test_open_camera_falls_back_to_another_backend(monkeypatch):
    calls = []

    class FakeCap:
        def __init__(self, index, backend):
            calls.append((index, backend))
            self._opened = (index, backend) == (0, 0)

        def isOpened(self):
            return self._opened

        def read(self):
            return True, np.zeros((24, 32, 3), dtype=np.uint8)

        def release(self):
            pass

    monkeypatch.setattr(screen_processor, "_CV2", True)
    monkeypatch.setattr(screen_processor.cv2, "CAP_DSHOW", 700, raising=False)
    monkeypatch.setattr(screen_processor.cv2, "CAP_ANY", 0, raising=False)
    monkeypatch.setattr(screen_processor.cv2, "VideoCapture", FakeCap)

    cap = screen_processor._open_camera(0, [screen_processor.cv2.CAP_DSHOW, screen_processor.cv2.CAP_ANY])

    assert cap is not None
    assert (0, screen_processor.cv2.CAP_DSHOW) in calls
    assert (0, screen_processor.cv2.CAP_ANY) in calls
