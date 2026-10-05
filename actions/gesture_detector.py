"""Real-time hand gesture recognition for the optional Gesture Mode."""
from __future__ import annotations

import time
from dataclasses import dataclass

try:
    import cv2
    import mediapipe as mp
except ImportError:
    cv2 = None
    mp = None


@dataclass(frozen=True)
class GestureEvent:
    name: str
    command: str
    confidence: float


class GestureDetector:
    """Detect a small, stable gesture vocabulary from BGR OpenCV frames.

    Events require several consecutive matching frames and are rate-limited so
    a held hand cannot repeatedly trigger the same command.
    """

    COMMANDS = {
        "OPEN_PALM": "pause",
        "THUMBS_UP": "confirm",
        "THUMBS_DOWN": "cancel",
        "SWIPE_LEFT": "previous",
        "SWIPE_RIGHT": "next",
        "PINCH": "select",
        "TWO_FINGERS_UP": "volume_up",
        "TWO_FINGERS_DOWN": "volume_down",
    }

    def __init__(self, min_confidence: float = 0.72,
                 stable_frames: int = 5, cooldown: float = 1.2):
        self.enabled = bool(cv2 is not None and mp is not None and hasattr(mp, "solutions"))
        self._min_confidence = min_confidence
        self._stable_frames = stable_frames
        self._cooldown = cooldown
        self._last_name = ""
        self._stable_count = 0
        self._last_emit = 0.0
        self._last_x = None
        self._last_x_time = 0.0
        self._hands = None
        self._draw = None
        if self.enabled:
            try:
                self._hands = mp.solutions.hands.Hands(
                    static_image_mode=False,
                    max_num_hands=1,
                    model_complexity=0,
                    min_detection_confidence=min_confidence,
                    min_tracking_confidence=min_confidence,
                )
                self._draw = mp.solutions.drawing_utils
            except Exception:
                self.enabled = False
                self._hands = None
                self._draw = None

    def close(self) -> None:
        if self._hands is not None:
            self._hands.close()
            self._hands = None

    def process(self, frame):
        """Return ``(annotated_frame, event_or_none, label)``."""
        if not self.enabled or frame is None:
            return frame, None, "GESTURE MODE UNAVAILABLE"

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._hands.process(rgb)
        event = None
        label = "NO HAND"
        if result.multi_hand_landmarks:
            landmarks = result.multi_hand_landmarks[0].landmark
            label, confidence = self._classify(landmarks)
            self._draw.draw_landmarks(
                frame, result.multi_hand_landmarks[0], mp.solutions.hands.HAND_CONNECTIONS
            )
            event = self._stable_event(label, confidence)
        else:
            self._stable_count = 0
            self._last_name = ""

        cv2.putText(frame, f"GESTURE: {label}", (18, 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 212, 255), 2,
                    cv2.LINE_AA)
        return frame, event, label

    def _stable_event(self, name: str, confidence: float):
        if name not in self.COMMANDS or confidence < self._min_confidence:
            self._stable_count = 0
            self._last_name = name
            return None
        if name == self._last_name:
            self._stable_count += 1
        else:
            self._last_name = name
            self._stable_count = 1
        now = time.monotonic()
        if self._stable_count < self._stable_frames or now - self._last_emit < self._cooldown:
            return None
        self._last_emit = now
        self._stable_count = 0
        return GestureEvent(name, self.COMMANDS[name], confidence)

    def _classify(self, points) -> tuple[str, float]:
        # Landmark indices: wrist=0, thumb=4, index=8, middle=12,
        # ring=16, pinky=20. This intentionally favors robust coarse gestures.
        wrist = points[0]
        fingers = [
            points[8].y < points[6].y,
            points[12].y < points[10].y,
            points[16].y < points[14].y,
            points[20].y < points[18].y,
        ]
        thumb_up = points[4].y < points[3].y < wrist.y
        thumb_down = points[4].y > points[3].y > wrist.y
        raised = sum(fingers)
        confidence = 0.9

        if thumb_up and raised == 0:
            return "THUMBS_UP", confidence
        if thumb_down and raised == 0:
            return "THUMBS_DOWN", confidence
        dx = points[9].x - wrist.x
        now = time.monotonic()
        if self._last_x is not None and now - self._last_x_time < 0.45:
            delta = points[9].x - self._last_x
            if abs(delta) > 0.18:
                self._last_x = points[9].x
                self._last_x_time = now
                return ("SWIPE_RIGHT" if delta > 0 else "SWIPE_LEFT"), 0.86
        self._last_x = points[9].x
        self._last_x_time = now

        pinch = ((points[4].x - points[8].x) ** 2 +
                 (points[4].y - points[8].y) ** 2) ** 0.5 < 0.07
        if pinch:
            return "PINCH", 0.84
        if raised == 4:
            return "OPEN_PALM", confidence
        if fingers[0] and fingers[1] and not fingers[2] and not fingers[3]:
            return ("TWO_FINGERS_UP" if points[12].y < wrist.y else "TWO_FINGERS_DOWN"), 0.82
        return "UNKNOWN", 0.5
