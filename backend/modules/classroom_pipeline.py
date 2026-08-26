from __future__ import annotations

import logging
import time
from dataclasses import asdict
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np

from backend.modules.attendance import AttendanceManager
from backend.modules.attention_engine import AttentionEngine, FrameSignals
from backend.modules.face_detection import FaceDetector
from backend.modules.face_recognition_module import FaceRecognitionService
from backend.modules.head_pose import HeadPoseEstimator
from backend.modules.sleep_yawn_detection import SleepYawnDetector
from backend.modules.eye_tracking import EyeTracker
from backend.services.firebase_service import FirebaseService
from backend.services.notification_service import NotificationService

logger = logging.getLogger("smart_classroom.pipeline")

_DEFAULT_STALE_STUDENT_SECONDS = 8.0


class ClassroomPipeline:
    def __init__(
        self,
        face_detector: FaceDetector,
        eye_tracker: EyeTracker,
        head_pose_estimator: HeadPoseEstimator,
        sleep_yawn_detector: SleepYawnDetector,
        attention_engine: AttentionEngine,
        recognition_service: FaceRecognitionService,
        attendance_manager: AttendanceManager,
        notification_service: NotificationService,
        firebase_service: Optional[FirebaseService] = None,
        low_attention_threshold: float = 40.0,
        stale_student_seconds: float = _DEFAULT_STALE_STUDENT_SECONDS,
    ):
        self._face_detector = face_detector
        self._eye_tracker = eye_tracker
        self._head_pose_estimator = head_pose_estimator
        self._sleep_yawn_detector = sleep_yawn_detector
        self._attention_engine = attention_engine
        self._recognition_service = recognition_service
        self._attendance_manager = attendance_manager
        self._notifier = notification_service
        self._firebase = firebase_service
        self._low_attention_threshold = low_attention_threshold
        self._stale_student_seconds = stale_student_seconds

        # Latest per-student snapshot, kept in memory for /analytics/class-summary.
        # Each entry also carries "last_seen" so _evict_stale_students can drop
        # students who have left the frame instead of leaving them in the
        # live summary forever (see _evict_stale_students).
        self._latest_by_student: Dict[str, Dict[str, Any]] = {}

    def process_frame(self, frame_rgb: np.ndarray) -> Dict[str, Any]:
        """
        Run the full pipeline on a single RGB frame (as decoded from the
        dashboard's webcam capture). Returns a JSON-serializable dict with
        per-person results, ready for the API layer to return directly.
        """
        frame_h, frame_w = frame_rgb.shape[:2]
        frame_bgr = frame_rgb[:, :, ::-1]
        now = time.time()
        today_str = date.today().isoformat()

        detected_faces = self._face_detector.detect(frame_bgr)

        student_results: List[Dict[str, Any]] = []
        students_recognized = 0
        unknown_faces = 0

        for face in detected_faces:
            recognition_crop_bgr = face.crop_for_recognition(frame_bgr)
            recognition_crop_rgb = recognition_crop_bgr[:, :, ::-1]
            match = self._recognition_service.identify_face(
                recognition_crop_rgb, face.bbox, face.confidence
            )

            landmarks_crop_bgr = face.crop_for_landmarks(frame_bgr)
            student_id = match.student_id or f"unknown-{face.x}-{face.y}"

            eye_result = self._eye_tracker.process(landmarks_crop_bgr, student_id)
            crop_h, crop_w = landmarks_crop_bgr.shape[:2]
            pose_result = self._head_pose_estimator.estimate(
                eye_result.landmarks, max(crop_w, 1), max(crop_h, 1), student_id
            )
            sleep_yawn_result = self._sleep_yawn_detector.update(
                student_id=student_id,
                avg_ear=eye_result.avg_ear,
                mouth_aspect_ratio=eye_result.mouth_aspect_ratio,
            )

            signals = FrameSignals(
                student_id=student_id,
                face_present=True,
                eye_aspect_ratio=eye_result.avg_ear,
                blink_rate_per_min=eye_result.blink_rate_per_min,
                head_yaw_deg=pose_result.yaw_deg,
                head_pitch_deg=pose_result.pitch_deg,
                is_sleeping=sleep_yawn_result.is_sleeping,
                sleep_duration_seconds=sleep_yawn_result.sleep_duration_seconds,
                yawn_count_last_minute=sleep_yawn_result.yawn_count_last_minute,
                emotion_label=None,  # populated by emotion module if/when wired in
            )
            attention_result = self._attention_engine.compute_score(signals)

            if match.is_known:
                students_recognized += 1
                self._attendance_manager.mark_present(
                    student_id=match.student_id,
                    name=match.name,
                    roll_number=match.roll_number,
                    confidence=match.match_score,
                )
                self._raise_condition_alerts(
                    student_id=match.student_id,
                    student_name=match.name,
                    sleep_yawn_result=sleep_yawn_result,
                    attention_result=attention_result,
                )
            else:
                unknown_faces += 1
                self._notifier.raise_alert(
                    alert_type="unrecognized_person",
                    student_id=None,
                    student_name=None,
                    message="Unrecognized person detected in classroom",
                    severity="warning",
                )

            if self._firebase is not None and match.is_known:
                self._firebase.log_attention_result(
                    today_str, match.student_id, asdict(attention_result)
                )

            top, right, bottom, left = face.y, face.x + face.width, face.y + face.height, face.x
            result = {
                "student_id": match.student_id,
                "name": match.name,
                "roll_number": match.roll_number,
                "is_known": match.is_known,
                "face_detection_confidence": round(face.confidence, 4),
                "recognition_score": match.match_score,
                "bbox": {"top": top, "right": right, "bottom": bottom, "left": left},
                "attention_score": attention_result.score,
                "attention_level": attention_result.level,
                "sub_scores": attention_result.sub_scores,
                "is_sleeping": sleep_yawn_result.is_sleeping,
                "is_yawning": sleep_yawn_result.is_yawning,
                "head_pose": {
                    "yaw": pose_result.yaw_deg,
                    "pitch": pose_result.pitch_deg,
                    "roll": pose_result.roll_deg,
                    "is_looking_away": pose_result.is_looking_away,
                    "confidence": pose_result.pose_confidence,
                },
                # Raw model diagnostics — not meant for the main teacher
                # dashboard, kept for a diagnostics/details view.
                "diagnostics": {
                    "avg_ear": eye_result.avg_ear,
                    "mouth_aspect_ratio": eye_result.mouth_aspect_ratio,
                    "blink_rate_per_min": eye_result.blink_rate_per_min,
                    "eye_measurement_valid": eye_result.eye_measurement_valid,
                    "recognition_distance": match.recognition_distance,
                    "recognition_threshold": match.recognition_threshold,
                },
            }
            student_results.append(result)
            self._latest_by_student[student_id] = {**result, "last_seen": now}

        self._evict_stale_students(now)

        return {
            "timestamp": now,
            "frame_dimensions": {"width": frame_w, "height": frame_h},
            "faces_detected": len(detected_faces),
            "students_recognized": students_recognized,
            "unknown_faces": unknown_faces,
            "students": student_results,
        }

    def get_class_summary(self) -> Dict[str, Any]:
        """Aggregate the most recent (non-stale) per-person snapshots into a
        class-wide summary. Students who have left the frame are dropped by
        _evict_stale_students before this is called on the next frame, so a
        student who walked out a few seconds ago won't still count toward
        total_students."""
        results = list(self._latest_by_student.values())
        if not results:
            return {
                "total_students": 0,
                "avg_attention": 0,
                "low_attention_count": 0,
                "sleeping_count": 0,
                "yawning_count": 0,
            }
        scores = [r["attention_score"] for r in results if r.get("is_known")]
        avg_attention = round(sum(scores) / len(scores), 2) if scores else 0.0
        return {
            "total_students": len(results),
            "avg_attention": avg_attention,
            "low_attention_count": sum(
                1 for r in results if r["attention_score"] < self._low_attention_threshold
            ),
            "sleeping_count": sum(1 for r in results if r["is_sleeping"]),
            "yawning_count": sum(1 for r in results if r["is_yawning"]),
        }

    # ------------------------------------------------------------------
    def _evict_stale_students(self, now: float) -> None:
        """Drop entries from the live in-memory summary once they haven't
        been seen for stale_student_seconds. This only affects the live
        /analytics/class-summary view — historical Firestore attendance is
        never touched here."""
        stale_ids = [
            sid
            for sid, entry in self._latest_by_student.items()
            if now - entry.get("last_seen", now) > self._stale_student_seconds
        ]
        for sid in stale_ids:
            self._latest_by_student.pop(sid, None)

    def _raise_condition_alerts(
        self,
        student_id: str,
        student_name: str,
        sleep_yawn_result,
        attention_result,
    ) -> None:
        # Software-only build: alerts are never forwarded to hardware.
        if sleep_yawn_result.is_sleeping:
            self._notifier.raise_alert(
                alert_type="sleeping",
                student_id=student_id,
                student_name=student_name,
                message=f"{student_name} is showing signs of sleepiness",
                severity="warning",
            )
        if sleep_yawn_result.yawn_count_last_minute >= 3:
            self._notifier.raise_alert(
                alert_type="yawning",
                student_id=student_id,
                student_name=student_name,
                message=f"Frequent yawning detected - {student_name}",
                severity="info",
            )
        if attention_result.score < self._low_attention_threshold:
            severity = "critical" if attention_result.score < 20 else "warning"
            self._notifier.raise_alert(
                alert_type="low_attention",
                student_id=student_id,
                student_name=student_name,
                message=f"{student_name} - {attention_result.level} attention ({attention_result.score:.0f}%)",
                severity=severity,
            )
