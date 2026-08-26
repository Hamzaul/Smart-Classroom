from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np

logger = logging.getLogger("smart_classroom.eye_tracking")

# MediaPipe Face Mesh landmark indices (468-point topology)
_LEFT_EYE = [362, 385, 387, 263, 373, 380]
_RIGHT_EYE = [33, 160, 158, 133, 153, 144]
_MOUTH = [61, 291, 39, 181, 0, 17, 269, 405]  # left, right, top(x2), bottom(x2)... used for MAR

_DEFAULT_EAR_SMOOTHING_WINDOW = 3


@dataclass
class EyeTrackingResult:
    landmarks: Optional[np.ndarray]  # (468, 3) normalized landmarks, or None
    landmarks_available: bool        # False = FaceMesh found no face this frame
    eye_measurement_valid: bool      # True = avg_ear reflects a real reading, not a fallback
    left_ear: Optional[float]
    right_ear: Optional[float]
    avg_ear: Optional[float]         # smoothed
    mouth_aspect_ratio: Optional[float]
    is_blinking: bool
    blink_rate_per_min: float


class _BlinkTracker:
    """Per-student blink-event tracker + EAR smoothing for computing rolling
    blink rate and a stable EAR signal."""

    def __init__(self, window_seconds: float = 60.0, ear_smoothing_window: int = _DEFAULT_EAR_SMOOTHING_WINDOW):
        self.window_seconds = window_seconds
        self.blink_timestamps: Deque[float] = deque()
        self._was_closed = False
        self._ear_history: Deque[float] = deque(maxlen=ear_smoothing_window)

    def smooth_ear(self, raw_ear: float) -> float:
        self._ear_history.append(raw_ear)
        return float(np.mean(self._ear_history))

    def update(self, smoothed_ear: float, closed_threshold: float, now: float) -> bool:
        """Feed the (already-smoothed) EAR; returns True if a new blink was just registered."""
        is_closed = smoothed_ear < closed_threshold
        blinked = False
        if is_closed and not self._was_closed:
            # Eye just closed -> tentative blink start, confirmed on reopen
            pass
        if (not is_closed) and self._was_closed:
            # Eye just reopened -> count as a completed blink
            self.blink_timestamps.append(now)
            blinked = True
        self._was_closed = is_closed

        # Evict timestamps outside the rolling window
        cutoff = now - self.window_seconds
        while self.blink_timestamps and self.blink_timestamps[0] < cutoff:
            self.blink_timestamps.popleft()

        return blinked

    def rate_per_min(self) -> float:
        if not self.blink_timestamps:
            return 0.0
        return len(self.blink_timestamps) * (60.0 / self.window_seconds)


class EyeTracker:
    """
    Wraps mediapipe.solutions.face_mesh.FaceMesh and computes EAR/MAR/blink
    metrics per tracked student.

    A single EyeTracker instance can serve multiple students concurrently by
    keying blink history off `student_id`.
    """

    def __init__(
        self,
        ear_closed_threshold: float = 0.21,
        max_num_faces: int = 30,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        ear_smoothing_window: int = _DEFAULT_EAR_SMOOTHING_WINDOW,
    ):
        self._ear_closed_threshold = ear_closed_threshold
        self._ear_smoothing_window = ear_smoothing_window
        self._mp_face_mesh = mp.solutions.face_mesh
        self._mesh = self._mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=max_num_faces,
            refine_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._blink_trackers: Dict[str, _BlinkTracker] = {}
        logger.info("EyeTracker initialized (max_num_faces=%d)", max_num_faces)

    def process(
        self, face_crop_bgr: np.ndarray, student_id: str
    ) -> EyeTrackingResult:
        """
        Run FaceMesh on a single (already-cropped) face image and compute
        EAR/MAR/blink metrics for the given student.

        Args:
            face_crop_bgr: cropped face region, BGR, as produced by
                DetectedFace.crop_for_landmarks().
            student_id: stable identifier used to key blink-rate/EAR
                smoothing history.
        """
        if face_crop_bgr is None or face_crop_bgr.size == 0:
            return EyeTrackingResult(None, False, False, None, None, None, None, False, 0.0)

        rgb = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self._mesh.process(rgb)

        if not results.multi_face_landmarks:
            # No mesh this frame: this is a *missing measurement*, not a
            # "eyes closed" reading. Downstream state machines must treat
            # avg_ear=None as "unavailable", never as 0.
            return EyeTrackingResult(None, False, False, None, None, None, None, False, 0.0)

        landmarks_obj = results.multi_face_landmarks[0].landmark
        landmarks = np.array(
            [[lm.x, lm.y, lm.z] for lm in landmarks_obj], dtype=np.float32
        )

        left_ear = self._eye_aspect_ratio(landmarks, _LEFT_EYE)
        right_ear = self._eye_aspect_ratio(landmarks, _RIGHT_EYE)
        raw_avg_ear = (left_ear + right_ear) / 2.0
        mar = self._mouth_aspect_ratio(landmarks)

        tracker = self._blink_trackers.setdefault(
            student_id, _BlinkTracker(ear_smoothing_window=self._ear_smoothing_window)
        )
        smoothed_avg_ear = tracker.smooth_ear(raw_avg_ear)
        is_blinking = tracker.update(smoothed_avg_ear, self._ear_closed_threshold, time.time())
        blink_rate = tracker.rate_per_min()

        return EyeTrackingResult(
            landmarks=landmarks,
            landmarks_available=True,
            eye_measurement_valid=True,
            left_ear=round(left_ear, 4),
            right_ear=round(right_ear, 4),
            avg_ear=round(smoothed_avg_ear, 4),
            mouth_aspect_ratio=round(mar, 4),
            is_blinking=is_blinking,
            blink_rate_per_min=round(blink_rate, 2),
        )

    def reset_student(self, student_id: str) -> None:
        self._blink_trackers.pop(student_id, None)

    def close(self) -> None:
        self._mesh.close()

    # ------------------------------------------------------------------
    @staticmethod
    def _euclidean(p1: np.ndarray, p2: np.ndarray) -> float:
        return float(np.linalg.norm(p1[:2] - p2[:2]))

    def _eye_aspect_ratio(self, landmarks: np.ndarray, idx: List[int]) -> float:
        """
        Standard EAR formula (Soukupová & Čech, 2016):
            EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
        idx order: [p1(left corner), p2, p3, p4(right corner), p5, p6]
        matching the ordering used for _LEFT_EYE / _RIGHT_EYE above.
        """
        p1, p2, p3, p4, p5, p6 = [landmarks[i] for i in idx]
        vertical = self._euclidean(p2, p6) + self._euclidean(p3, p5)
        horizontal = self._euclidean(p1, p4)
        if horizontal < 1e-6:
            return 0.0
        return vertical / (2.0 * horizontal)

    def _mouth_aspect_ratio(self, landmarks: np.ndarray) -> float:
        """
        MAR = mean(vertical mouth openings) / horizontal mouth width.
        Used downstream by sleep_yawn_detection.py to flag yawns.
        """
        left, right, top1, bottom1, top2, bottom2, _, _ = [
            landmarks[i] for i in _MOUTH
        ]
        vertical = self._euclidean(top1, bottom1) + self._euclidean(top2, bottom2)
        horizontal = self._euclidean(left, right)
        if horizontal < 1e-6:
            return 0.0
        return vertical / (2.0 * horizontal)

    def __enter__(self) -> "EyeTracker":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
