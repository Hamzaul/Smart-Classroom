from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional

from backend.config.config_loader import get_attention_config

logger = logging.getLogger("smart_classroom.attention_engine")


@dataclass
class FrameSignals:
    """Raw per-frame signals for a single student, produced by the CV pipeline."""

    student_id: str
    face_present: bool
    eye_aspect_ratio: Optional[float] = None       # average of left/right EAR
    blink_rate_per_min: Optional[float] = None      # blinks per minute, rolling
    head_yaw_deg: Optional[float] = None
    head_pitch_deg: Optional[float] = None
    is_sleeping: bool = False
    sleep_duration_seconds: float = 0.0
    yawn_count_last_minute: int = 0
    emotion_label: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class AttentionResult:
    student_id: str
    score: float
    level: str
    sub_scores: Dict[str, float]
    timestamp: float


class _StudentHistory:
    """Per-student rolling history for smoothing and trend analysis."""

    def __init__(self, window_size: int):
        self.scores: Deque[float] = deque(maxlen=window_size)
        self.smoothed_score: Optional[float] = None
        self.face_absent_since: Optional[float] = None

    def push(self, score: float, alpha: float) -> float:
        self.scores.append(score)
        if self.smoothed_score is None:
            self.smoothed_score = score
        else:
            self.smoothed_score = alpha * score + (1 - alpha) * self.smoothed_score
        return self.smoothed_score

    def average(self) -> float:
        if not self.scores:
            return 0.0
        return sum(self.scores) / len(self.scores)


class AttentionEngine:
    """
    Stateful attention scoring engine. One instance is shared across the
    Flask app (via dependency injection / app context) and holds a
    per-student rolling history to smooth noisy frame-level signals.
    """

    def __init__(self):
        self._config = get_attention_config()
        self._histories: Dict[str, _StudentHistory] = {}
        logger.info(
            "AttentionEngine initialized with weights=%s", self._config.weights
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def compute_score(self, signals: FrameSignals) -> AttentionResult:
        """Compute a smoothed 0-100 attention score for a single frame's signals."""
        history = self._get_or_create_history(signals.student_id)

        if not signals.face_present:
            if history.face_absent_since is None:
                history.face_absent_since = signals.timestamp
            absence_seconds = signals.timestamp - history.face_absent_since
        else:
            history.face_absent_since = None
            absence_seconds = 0.0

        # NOTE: emotion is intentionally NOT included here. `emotion_label`
        # is still accepted on FrameSignals (the CV pipeline never sets it —
        # see classroom_pipeline.py), but no genuine emotion-recognition
        # module is implemented in this project. Previously an "emotion"
        # sub-score was silently included in the weighted average using a
        # constant "unknown" value, which meant an unimplemented feature was
        # quietly influencing every attention score. Do not re-add an
        # emotion sub-score/weight until a real emotion-recognition module
        # is implemented, tested, and documented (see README "Known
        # Limitations").
        sub_scores = {
            "eye_aspect_ratio": self._score_ear(signals.eye_aspect_ratio),
            "blink_rate": self._score_blink_rate(signals.blink_rate_per_min),
            "head_pose": self._score_head_pose(
                signals.head_yaw_deg, signals.head_pitch_deg
            ),
            "face_presence": self._score_face_presence(
                signals.face_present, absence_seconds
            ),
            "sleep_duration": self._score_sleep(
                signals.is_sleeping, signals.sleep_duration_seconds
            ),
            "yawn_count": self._score_yawn(signals.yawn_count_last_minute),
        }

        weights = self._config.weights
        raw_score = sum(sub_scores[key] * weights[key] for key in weights)
        raw_score = max(0.0, min(100.0, raw_score))

        alpha = self._config.history.get("smoothing_alpha", 0.3)
        smoothed = history.push(raw_score, alpha)

        level = self._config.attention_level_for_score(smoothed)

        return AttentionResult(
            student_id=signals.student_id,
            score=round(smoothed, 2),
            level=level,
            sub_scores={k: round(v, 2) for k, v in sub_scores.items()},
            timestamp=signals.timestamp,
        )

    def get_rolling_average(self, student_id: str) -> float:
        history = self._histories.get(student_id)
        return round(history.average(), 2) if history else 0.0

    def reset_student(self, student_id: str) -> None:
        self._histories.pop(student_id, None)

    # ------------------------------------------------------------------
    # Sub-score calculators (each normalized to 0-100)
    # ------------------------------------------------------------------
    def _score_ear(self, ear: Optional[float]) -> float:
        if ear is None:
            return 50.0  # neutral/unknown
        t = self._config.thresholds
        closed = t["ear_closed_threshold"]
        drowsy = t["ear_drowsy_threshold"]
        if ear <= closed:
            return 0.0
        if ear <= drowsy:
            # Linear ramp between "closed" and "drowsy" thresholds
            span = max(drowsy - closed, 1e-6)
            return 40.0 * (ear - closed) / span
        # Fully open eyes -> full score, capped
        open_full = drowsy + 0.10
        span = max(open_full - drowsy, 1e-6)
        return min(100.0, 40.0 + 60.0 * (ear - drowsy) / span)

    def _score_blink_rate(self, rate: Optional[float]) -> float:
        if rate is None:
            return 50.0
        t = self._config.thresholds
        lo, hi = t["blink_rate_normal_min"], t["blink_rate_normal_max"]
        if lo <= rate <= hi:
            return 100.0
        if rate < lo:
            # Too few blinks can indicate a fixed/glazed stare (still risky)
            deficit = lo - rate
            return max(0.0, 100.0 - deficit * 8.0)
        # Too many blinks can indicate fatigue/eye strain
        excess = rate - hi
        return max(0.0, 100.0 - excess * 6.0)

    def _score_head_pose(
        self, yaw: Optional[float], pitch: Optional[float]
    ) -> float:
        if yaw is None or pitch is None:
            return 50.0
        t = self._config.thresholds
        yaw_max = t["head_pose_yaw_max_deg"]
        pitch_max = t["head_pose_pitch_max_deg"]
        yaw_penalty = min(1.0, abs(yaw) / max(yaw_max, 1e-6))
        pitch_penalty = min(1.0, abs(pitch) / max(pitch_max, 1e-6))
        penalty = max(yaw_penalty, pitch_penalty)
        return max(0.0, 100.0 * (1.0 - penalty))

    def _score_face_presence(self, present: bool, absence_seconds: float) -> float:
        if present:
            return 100.0
        t = self._config.thresholds
        penalty_per_sec = t["face_absence_penalty_per_second"]
        return max(0.0, 100.0 - absence_seconds * penalty_per_sec)

    def _score_sleep(self, is_sleeping: bool, duration_seconds: float) -> float:
        if not is_sleeping:
            return 100.0
        t = self._config.thresholds
        alert_threshold = t["sleep_duration_alert_seconds"]
        if duration_seconds < alert_threshold:
            # Micro-closure, not yet classified as concerning
            return 100.0 * (1 - duration_seconds / max(alert_threshold, 1e-6)) * 0.5 + 20
        # Beyond alert threshold, score decays toward 0 the longer they sleep
        overage = duration_seconds - alert_threshold
        return max(0.0, 20.0 - overage * 2.0)

    def _score_yawn(self, yawn_count_last_minute: int) -> float:
        t = self._config.thresholds
        alert = t["yawn_count_alert_per_minute"]
        if yawn_count_last_minute <= 0:
            return 100.0
        if yawn_count_last_minute < alert:
            return 100.0 - (yawn_count_last_minute / alert) * 40.0
        excess = yawn_count_last_minute - alert
        return max(0.0, 60.0 - excess * 15.0)

    # NOTE: _score_emotion was removed from the active scoring path (see
    # compute_score above). `AttentionConfig.emotion_score()` / the
    # `emotion_scores` table in attention_weights.json are kept for a
    # future genuine emotion-recognition module, but nothing calls them
    # today.

    # ------------------------------------------------------------------
    def _get_or_create_history(self, student_id: str) -> _StudentHistory:
        if student_id not in self._histories:
            window = int(self._config.history.get("rolling_window_size", 30))
            self._histories[student_id] = _StudentHistory(window_size=window)
        return self._histories[student_id]


# ---------------------------------------------------------------------------
# Module-level singleton accessor (simple DI pattern used across the app)
# ---------------------------------------------------------------------------
_engine_singleton: Optional[AttentionEngine] = None


def get_attention_engine() -> AttentionEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = AttentionEngine()
    return _engine_singleton
