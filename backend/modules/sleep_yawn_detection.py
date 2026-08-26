from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

logger = logging.getLogger("smart_classroom.sleep_yawn_detection")


@dataclass
class SleepYawnResult:
    is_sleeping: bool
    sleep_duration_seconds: float
    is_yawning: bool
    yawn_count_last_minute: int


class _StudentSleepYawnState:
    def __init__(self, yawn_window_seconds: float = 60.0):
        self.eyes_closed_since: Optional[float] = None
        self.eyes_currently_closed: bool = False
        self.mouth_open_since: Optional[float] = None
        self.yawn_timestamps: Deque[float] = deque()
        self.yawn_window_seconds = yawn_window_seconds
        self._counted_current_yawn = False


class SleepYawnDetector:
    """
    Stateful per-student sleep/yawn detector.

    Usage:
        detector = SleepYawnDetector()
        result = detector.update(
            student_id="s1", avg_ear=0.14, mouth_aspect_ratio=0.55
        )
    """

    def __init__(
        self,
        ear_closed_threshold: float = 0.21,
        ear_reopen_threshold: Optional[float] = None,
        sleep_confirm_seconds: float = 1.5,
        mar_yawn_threshold: float = 0.55,
        yawn_confirm_seconds: float = 0.6,
    ):
        """
        Args:
            ear_closed_threshold: EAR below this is where eyes are
                considered to have *started* closing.
            ear_reopen_threshold: EAR must rise back above this before
                eyes are considered reopened. Defaults to
                ear_closed_threshold + 0.02 if not given. Keeping this
                slightly above the closed threshold (hysteresis) stops a
                value oscillating right at the boundary from flapping
                between "closed"/"open" every frame. Final numbers need
                calibration against real footage — this default is a
                starting point.
            sleep_confirm_seconds: eyes must stay closed at least this long
                before it's classified as sleeping rather than a blink.
                1.5s is a reasonable start for testing; classroom use may
                want 2-3s to rule out long blinks/micro-sleeps.
            mar_yawn_threshold: MAR above this is considered "mouth wide open".
            yawn_confirm_seconds: mouth must stay open at least this long
                before it's counted as a yawn (filters out talking/laughing).
        """
        self._ear_closed_threshold = ear_closed_threshold
        self._ear_reopen_threshold = (
            ear_reopen_threshold if ear_reopen_threshold is not None else ear_closed_threshold + 0.02
        )
        self._sleep_confirm_seconds = sleep_confirm_seconds
        self._mar_yawn_threshold = mar_yawn_threshold
        self._yawn_confirm_seconds = yawn_confirm_seconds
        self._states: dict[str, _StudentSleepYawnState] = {}

    def update(
        self,
        student_id: str,
        avg_ear: Optional[float],
        mouth_aspect_ratio: Optional[float],
        now: Optional[float] = None,
    ) -> SleepYawnResult:
        now = now if now is not None else time.time()
        state = self._states.setdefault(student_id, _StudentSleepYawnState())

        is_sleeping, sleep_duration = self._update_sleep(state, avg_ear, now)
        is_yawning = self._update_yawn(state, mouth_aspect_ratio, now)

        # Evict old yawn timestamps outside the rolling window
        cutoff = now - state.yawn_window_seconds
        while state.yawn_timestamps and state.yawn_timestamps[0] < cutoff:
            state.yawn_timestamps.popleft()

        return SleepYawnResult(
            is_sleeping=is_sleeping,
            sleep_duration_seconds=round(sleep_duration, 2),
            is_yawning=is_yawning,
            yawn_count_last_minute=len(state.yawn_timestamps),
        )

    def reset_student(self, student_id: str) -> None:
        self._states.pop(student_id, None)

    # ------------------------------------------------------------------
    def _update_sleep(
        self, state: _StudentSleepYawnState, avg_ear: Optional[float], now: float
    ) -> tuple[bool, float]:
        if avg_ear is None:
            # Measurement unavailable (e.g. FaceMesh lost the face this
            # frame) — this must never be treated as "eyes closed". Hold
            # the existing timer rather than resetting it, since a couple
            # of dropped frames shouldn't erase an in-progress sleep
            # window; just don't advance the duration while data is
            # missing.
            if state.eyes_closed_since is not None:
                duration = now - state.eyes_closed_since
                is_sleeping = duration >= self._sleep_confirm_seconds
                return is_sleeping, duration
            return False, 0.0

        if state.eyes_currently_closed:
            # Hysteresis: once closed, require EAR to rise back above the
            # (higher) reopen threshold before counting as open again.
            if avg_ear >= self._ear_reopen_threshold:
                state.eyes_currently_closed = False
                state.eyes_closed_since = None
                return False, 0.0
            duration = now - state.eyes_closed_since if state.eyes_closed_since is not None else 0.0
            is_sleeping = duration >= self._sleep_confirm_seconds
            return is_sleeping, duration
        else:
            if avg_ear < self._ear_closed_threshold:
                state.eyes_currently_closed = True
                state.eyes_closed_since = now
                return False, 0.0
            return False, 0.0

    def _update_yawn(
        self,
        state: _StudentSleepYawnState,
        mar: Optional[float],
        now: float,
    ) -> bool:
        if mar is None:
            state.mouth_open_since = None
            state._counted_current_yawn = False
            return False

        mouth_open = mar > self._mar_yawn_threshold
        if mouth_open:
            if state.mouth_open_since is None:
                state.mouth_open_since = now
            duration = now - state.mouth_open_since
            confirmed = duration >= self._yawn_confirm_seconds
            if confirmed and not state._counted_current_yawn:
                state.yawn_timestamps.append(now)
                state._counted_current_yawn = True
                logger.debug("Yawn confirmed and counted (duration=%.2fs)", duration)
            return confirmed
        else:
            state.mouth_open_since = None
            state._counted_current_yawn = False
            return False
