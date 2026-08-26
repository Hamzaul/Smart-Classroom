"""
backend/services/firebase_service.py

Firebase Service.

Single point of contact with Firebase (Firestore + Cloud Storage +
Authentication token verification). Every other module that needs to
persist or read data goes through this service rather than importing
`firebase_admin` directly — this keeps Firebase-specific error handling,
retry logic, and collection-naming conventions in one place, and makes
the rest of the codebase testable by swapping this service for a fake.

Collections:
  students/{student_id}            -> profile + metadata
  encodings/{student_id}           -> face encoding (base64 float array)
  attendance/{date}/records/{sid}  -> AttendanceRecord
  attention_logs/{date}/{sid}/{ts} -> per-frame AttentionResult snapshots
  alerts/{alert_id}                -> generated alerts (sleeping, low attention, etc.)
"""

from __future__ import annotations

import base64
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import firebase_admin
import numpy as np
from firebase_admin import credentials, firestore, storage

from backend.config.config_loader import get_app_settings
from backend.modules.attendance import AttendanceRecord
from backend.modules.face_recognition_module import StudentEncoding

logger = logging.getLogger("smart_classroom.firebase_service")


class FirebaseServiceError(Exception):
    pass


class FirebaseService:
    """
    Thin, typed wrapper around firebase_admin's Firestore + Storage clients.

    Initialized once at app startup (see backend/app.py) and injected into
    every module that needs persistence (AttendanceManager, FaceRecognitionService).
    """

    def __init__(self):
        settings = get_app_settings()
        if not firebase_admin._apps:
            try:
                cred = credentials.Certificate(settings.firebase_credentials_path)
                init_kwargs: Dict[str, Any] = {}
                if settings.firebase_storage_bucket:
                    init_kwargs["storageBucket"] = settings.firebase_storage_bucket
                firebase_admin.initialize_app(cred, init_kwargs)
                logger.info("Firebase app initialized")
            except FileNotFoundError as e:
                raise FirebaseServiceError(
                    f"Firebase credentials not found at "
                    f"'{settings.firebase_credentials_path}'. Set "
                    f"FIREBASE_CREDENTIALS_PATH in .env."
                ) from e

        self._db = firestore.client()
        self._bucket = storage.bucket() if settings.firebase_storage_bucket else None

    # ------------------------------------------------------------------
    # Students / Encodings
    # ------------------------------------------------------------------
    def save_student_profile(
        self, student_id: str, name: str, roll_number: str, extra_fields: Optional[Dict] = None
    ) -> None:
        doc = {
            "student_id": student_id,
            "name": name,
            "roll_number": roll_number,
            "enrolled_at": datetime.now().isoformat(timespec="seconds"),
            **(extra_fields or {}),
        }
        self._db.collection("students").document(student_id).set(doc, merge=True)
        logger.info("Saved student profile: %s (%s)", name, student_id)

    def save_student_encoding(self, record: StudentEncoding) -> None:
        encoded = base64.b64encode(record.encoding.astype(np.float64).tobytes()).decode("utf-8")
        self._db.collection("encodings").document(record.student_id).set(
            {
                "student_id": record.student_id,
                "name": record.name,
                "roll_number": record.roll_number,
                "encoding_b64": encoded,
                "encoding_dtype": "float64",
                "encoding_length": len(record.encoding),
            }
        )
        # Also keep the human-readable profile up to date.
        self.save_student_profile(record.student_id, record.name, record.roll_number)

    def load_all_student_encodings(self) -> List[StudentEncoding]:
        docs = self._db.collection("encodings").stream()
        results: List[StudentEncoding] = []
        for doc in docs:
            data = doc.to_dict()
            try:
                raw = base64.b64decode(data["encoding_b64"])
                arr = np.frombuffer(raw, dtype=data.get("encoding_dtype", "float64"))
                results.append(
                    StudentEncoding(
                        student_id=data["student_id"],
                        name=data["name"],
                        roll_number=data["roll_number"],
                        encoding=arr,
                    )
                )
            except (KeyError, ValueError) as e:
                logger.error("Corrupt encoding for doc %s: %s", doc.id, e)
        return results

    def delete_student_encoding(self, student_id: str) -> None:
        self._db.collection("encodings").document(student_id).delete()

    def list_students(self) -> List[Dict[str, Any]]:
        return [doc.to_dict() for doc in self._db.collection("students").stream()]

    # ------------------------------------------------------------------
    # Attendance
    # ------------------------------------------------------------------
    def save_attendance_record(self, record: AttendanceRecord) -> None:
        self._db.collection("attendance").document(record.date).collection(
            "records"
        ).document(record.student_id).set(asdict(record))

    def get_attendance_for_date(self, date_str: str) -> List[Dict[str, Any]]:
        docs = (
            self._db.collection("attendance")
            .document(date_str)
            .collection("records")
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    def get_attendance_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Fetch attendance across a date range (inclusive) for weekly/monthly analytics."""
        # Firestore doesn't support range queries across subcollection parents
        # directly, so we enumerate date documents client-side.
        all_records: List[Dict[str, Any]] = []
        date_docs = self._db.collection("attendance").stream()
        for date_doc in date_docs:
            if start_date <= date_doc.id <= end_date:
                records = date_doc.reference.collection("records").stream()
                all_records.extend(r.to_dict() for r in records)
        return all_records

    # ------------------------------------------------------------------
    # Attention logs
    # ------------------------------------------------------------------
    def log_attention_result(self, date_str: str, student_id: str, result_dict: Dict[str, Any]) -> None:
        ts = result_dict.get("timestamp", datetime.now().timestamp())
        doc_id = f"{ts}"
        self._db.collection("attention_logs").document(date_str).collection(
            student_id
        ).document(doc_id).set(result_dict)

    def get_attention_history(
        self, date_str: str, student_id: str, limit: int = 500
    ) -> List[Dict[str, Any]]:
        docs = (
            self._db.collection("attention_logs")
            .document(date_str)
            .collection(student_id)
            .order_by("timestamp")
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    # ------------------------------------------------------------------
    # Daily analytics aggregation (backs GET /api/analytics/daily)
    # ------------------------------------------------------------------
    def get_daily_summary(self, date_str: str) -> Dict[str, Any]:
        """
        Aggregate REAL attention_logs + attendance for a single calendar
        day. Every field here is computed from persisted Firestore data —
        a day with no recorded frames legitimately returns zeros/has_data
        False, which is truthful (unlike the old frontend placeholder that
        fabricated 6 of every 7 "historical" days).

        attention_logs/{date} has one subcollection per student_id, each
        holding per-frame AttentionResult snapshots keyed by timestamp.
        """
        scores: List[float] = []
        date_doc_ref = self._db.collection("attention_logs").document(date_str)
        try:
            student_collections = list(date_doc_ref.collections())
        except Exception:
            logger.exception("Failed to list attention_logs subcollections for %s", date_str)
            student_collections = []

        for col in student_collections:
            for doc in col.stream():
                data = doc.to_dict() or {}
                score = data.get("score")
                if isinstance(score, (int, float)):
                    scores.append(float(score))

        avg_attention = round(sum(scores) / len(scores), 1) if scores else 0.0
        low_attention_count = sum(1 for s in scores if s < 40)

        attendance_records = self.get_attendance_for_date(date_str)
        present_count = sum(1 for r in attendance_records if r.get("status") == "present")

        return {
            "date": date_str,
            "avg_attention": avg_attention,
            "low_attention_count": low_attention_count,
            "present_count": present_count,
            "frames_recorded": len(scores),
            "has_data": bool(scores) or bool(attendance_records),
        }

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------
    def save_alert(self, alert: Dict[str, Any]) -> str:
        ref = self._db.collection("alerts").document()
        alert["alert_id"] = ref.id
        alert["created_at"] = datetime.now().isoformat(timespec="seconds")
        ref.set(alert)
        return ref.id

    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        docs = (
            self._db.collection("alerts")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    # ------------------------------------------------------------------
    # Cloud Storage (reference photos, exported reports)
    # ------------------------------------------------------------------
    def upload_file(self, local_path: str, remote_path: str) -> str:
        if self._bucket is None:
            raise FirebaseServiceError(
                "No storage bucket configured (set FIREBASE_STORAGE_BUCKET in .env)"
            )
        blob = self._bucket.blob(remote_path)
        blob.upload_from_filename(local_path)
        blob.make_public()
        return blob.public_url
