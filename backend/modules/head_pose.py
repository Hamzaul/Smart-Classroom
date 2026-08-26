from __future__ import annotations
 
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
 
import cv2
import numpy as np
 
logger = logging.getLogger("smart_classroom.head_pose")
 
# ---------------------------------------------------------------------------
# NOTE ON THIS MODEL — 2026-08 diagnostic pass
#
# The Y-components below are negated relative to the original values. This
# is a TESTED HYPOTHESIS, not a confirmed fix as of this revision.
#
# Diagnostic evidence that motivated the change (see project notes):
#   - Straight-facing pose consistently reported roll ~ +/-177-179 deg
#     instead of ~0 deg, and roll stayed pinned near that value across
#     every test regardless of physical motion (straight/tilt/turn).
#   - Real ~20-30 deg tilts (roll) and ~20-25 deg turns (yaw) both showed
#     up almost entirely as swings in the *pitch* output instead, while
#     the yaw output stayed within +/-9 deg of baseline in every test.
#   - That signature (fixed near-180 deg offset on one axis + real motion
#     leaking into a different axis) is consistent with the 3D model
#     points and the 2D image-landmark points using mismatched Y-axis
#     conventions (image coordinates are Y-down; the original model
#     values assumed Y-up), which distorts solvePnP's rotation solution
#     without necessarily hurting reprojection error / confidence.
#
# This must be re-validated with the same five-test protocol (straight,
# left ~20 deg, right ~20 deg, tilt-left ~20-30 deg, tilt-right ~20-30 deg)
# before being treated as resolved. If yaw still fails to track left/right
# turns after this change, the next suspects are _LANDMARK_INDICES
# correspondence and/or _rotation_matrix_to_euler's axis assignment —
# NOT the confidence/threshold values, which were deliberately left
# untouched throughout this diagnostic pass.
# ---------------------------------------------------------------------------
_MODEL_POINTS_3D = np.array(
    [
        (0.0, 0.0, 0.0),           # Nose tip
        (0.0, 330.0, -65.0),       # Chin
        (-225.0, -170.0, -135.0),  # Left eye left corner
        (225.0, -170.0, -135.0),   # Right eye right corner
        (-150.0, 150.0, -125.0),   # Left mouth corner
        (150.0, 150.0, -125.0),    # Right mouth corner
    ],
    dtype=np.float64,
)
 
# Corresponding indices into the 468-point MediaPipe FaceMesh landmark array
_LANDMARK_INDICES = {
    "nose_tip": 1,
    "chin": 152,
    "left_eye_left_corner": 33,
    "right_eye_right_corner": 263,
    "left_mouth_corner": 61,
    "right_mouth_corner": 291,
}
 
 
@dataclass
class HeadPoseResult:
    yaw_deg: Optional[float]
    pitch_deg: Optional[float]
    roll_deg: Optional[float]
    is_looking_away: bool
    pose_confidence: Optional[float]  # 0-1, based on solvePnP reprojection error; None if pose unavailable
 
 
class _StudentPoseState:
    def __init__(self) -> None:
        self.smoothed_yaw: Optional[float] = None
        self.smoothed_pitch: Optional[float] = None
        self.smoothed_roll: Optional[float] = None
        self.consecutive_away_frames: int = 0
 
 
class HeadPoseEstimator:
    """
    Estimates head orientation from normalized FaceMesh landmarks.
 
    Usage:
        estimator = HeadPoseEstimator(yaw_threshold_deg=25, pitch_threshold_deg=20)
        result = estimator.estimate(landmarks, frame_width, frame_height, student_id)
    """
 
    def __init__(
        self,
        yaw_threshold_deg: float = 25.0,
        pitch_threshold_deg: float = 20.0,
        smoothing_alpha: float = 0.4,
        consecutive_frames_required: int = 3,
        max_reprojection_error_px: float = 15.0,
        min_pose_confidence: float = 0.15,
    ):
        """
        Args:
            yaw_threshold_deg / pitch_threshold_deg: beyond these (on the
                *smoothed* angle) counts as "away" for that frame.
            smoothing_alpha: exponential smoothing factor applied per
                student to yaw/pitch/roll, same idea as AttentionEngine's
                history smoothing. Higher = more responsive, lower = more
                stable. 0.4 is a starting point, not a final value.
            consecutive_frames_required: number of consecutive "away"
                frames (post-smoothing) required before is_looking_away
                flips to True. Prevents one noisy frame from firing an
                alert.
            max_reprojection_error_px: solvePnP solutions whose model
                points reproject with more average pixel error than this
                are treated as unstable.
            min_pose_confidence: below this confidence, the pose is
                reported as unavailable (None angles) rather than feeding
                a poor estimate into attention scoring.
        """
        self._yaw_threshold = yaw_threshold_deg
        self._pitch_threshold = pitch_threshold_deg
        self._smoothing_alpha = smoothing_alpha
        self._consecutive_frames_required = consecutive_frames_required
        self._max_reprojection_error_px = max_reprojection_error_px
        self._min_pose_confidence = min_pose_confidence
        self._states: Dict[str, _StudentPoseState] = {}
 
    def estimate(
        self,
        landmarks: Optional[np.ndarray],
        frame_width: int,
        frame_height: int,
        student_id: str = "default",
    ) -> HeadPoseResult:
        """
        Args:
            landmarks: (468, 3) normalized landmark array from EyeTracker
                (x, y in [0,1] relative to the cropped face image; z relative depth).
            frame_width / frame_height: dimensions of the image the landmarks
                were computed on (i.e. the face crop, not the full frame).
            student_id: stable identifier used to key per-student smoothing
                and consecutive-away-frame state.
        """
        state = self._states.setdefault(student_id, _StudentPoseState())
 
        if landmarks is None:
            state.consecutive_away_frames = 0
            return HeadPoseResult(None, None, None, is_looking_away=False, pose_confidence=None)
 
        try:
            image_points = np.array(
                [
                    (
                        landmarks[_LANDMARK_INDICES[name]][0] * frame_width,
                        landmarks[_LANDMARK_INDICES[name]][1] * frame_height,
                    )
                    for name in _LANDMARK_INDICES
                ],
                dtype=np.float64,
            )
        except IndexError:
            logger.warning("Landmark array too short for head pose estimation")
            state.consecutive_away_frames = 0
            return HeadPoseResult(None, None, None, is_looking_away=False, pose_confidence=None)
 
        focal_length = frame_width
        center = (frame_width / 2.0, frame_height / 2.0)
        camera_matrix = np.array(
            [
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1],
            ],
            dtype=np.float64,
        )
        dist_coeffs = np.zeros((4, 1))  # assume no lens distortion
 
        success, rotation_vec, translation_vec = cv2.solvePnP(
            _MODEL_POINTS_3D,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not success:
            state.consecutive_away_frames = 0
            return HeadPoseResult(None, None, None, is_looking_away=False, pose_confidence=None)
 
        confidence = self._pose_confidence(
            rotation_vec, translation_vec, camera_matrix, dist_coeffs, image_points
        )
        if confidence < self._min_pose_confidence:
            # Unstable solve — don't let it poison attention scoring or
            # trigger a looking-away alert. Leave smoothing state as-is so
            # a single bad frame doesn't reset the running estimate either.
            logger.debug(
                "Rejecting unstable head pose solve for %s (confidence=%.2f)",
                student_id, confidence,
            )
            return HeadPoseResult(None, None, None, is_looking_away=False, pose_confidence=round(confidence, 2))
 
        rotation_matrix, _ = cv2.Rodrigues(rotation_vec)
        yaw, pitch, roll = self._rotation_matrix_to_euler(rotation_matrix)
        roll = self._normalize_angle(roll)
 
        alpha = self._smoothing_alpha
        state.smoothed_yaw = yaw if state.smoothed_yaw is None else alpha * yaw + (1 - alpha) * state.smoothed_yaw
        state.smoothed_pitch = pitch if state.smoothed_pitch is None else alpha * pitch + (1 - alpha) * state.smoothed_pitch
        state.smoothed_roll = roll if state.smoothed_roll is None else alpha * roll + (1 - alpha) * state.smoothed_roll
 
        # Roll is informational only — it is NOT part of the looking-away
        # decision (see AttentionEngine, which also only uses yaw/pitch).
        raw_away = (
            abs(state.smoothed_yaw) > self._yaw_threshold
            or abs(state.smoothed_pitch) > self._pitch_threshold
        )
        if raw_away:
            state.consecutive_away_frames += 1
        else:
            state.consecutive_away_frames = 0
 
        is_looking_away = state.consecutive_away_frames >= self._consecutive_frames_required
 
        return HeadPoseResult(
            yaw_deg=round(state.smoothed_yaw, 2),
            pitch_deg=round(state.smoothed_pitch, 2),
            roll_deg=round(state.smoothed_roll, 2),
            is_looking_away=is_looking_away,
            pose_confidence=round(confidence, 2),
        )
 
    def reset_student(self, student_id: str) -> None:
        self._states.pop(student_id, None)
 
    # ------------------------------------------------------------------
    def _pose_confidence(
        self,
        rotation_vec: np.ndarray,
        translation_vec: np.ndarray,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
        image_points: np.ndarray,
    ) -> float:
        """Reproject the 3D model points using the solved pose and compare
        against the detected 2D landmarks. A stable solve reprojects close
        to the original points; a degenerate/noisy solve does not."""
        projected, _ = cv2.projectPoints(
            _MODEL_POINTS_3D, rotation_vec, translation_vec, camera_matrix, dist_coeffs
        )
        projected = projected.reshape(-1, 2)
        errors = np.linalg.norm(projected - image_points, axis=1)
        mean_error = float(np.mean(errors))
        confidence = 1.0 - min(1.0, mean_error / max(self._max_reprojection_error_px, 1e-6))
        return max(0.0, confidence)
 
    @staticmethod
    def _normalize_angle(angle_deg: float) -> float:
        """Wrap an angle into [-180, 180]."""
        return ((angle_deg + 180.0) % 360.0) - 180.0
 
    @staticmethod
    def _rotation_matrix_to_euler(R: np.ndarray) -> Tuple[float, float, float]:
        """Convert a 3x3 rotation matrix to yaw/pitch/roll in degrees."""
        sy = np.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
        singular = sy < 1e-6
 
        if not singular:
            pitch = np.arctan2(-R[2, 0], sy)
            yaw = np.arctan2(R[1, 0], R[0, 0])
            roll = np.arctan2(R[2, 1], R[2, 2])
        else:
            pitch = np.arctan2(-R[2, 0], sy)
            yaw = 0.0
            roll = np.arctan2(-R[1, 2], R[1, 1])
 
        to_deg = 180.0 / np.pi
        return yaw * to_deg, pitch * to_deg, roll * to_deg
 