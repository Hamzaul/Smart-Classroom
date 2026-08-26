
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional

logger = logging.getLogger("smart_classroom.attendance")


class AttendanceError(Exception):
    pass


@dataclass
class AttendanceRecord:
    student_id: str
    name: str
    roll_number: str
    date: str  # ISO format YYYY-MM-DD
    first_seen: str  # ISO datetime
    last_seen: str  # ISO datetime
    status: str  # "present" | "absent"
    recognition_confidence: float


class AttendanceManager:
    """
    Stateful, per-day attendance tracker.

    Usage:
        manager = AttendanceManager(storage_backend=firebase_service)
        manager.mark_present(student_id="s1", name="Aman Kumar",
                              roll_number="21CS001", confidence=0.91)
        ...
        manager.finalize_day(all_enrolled_student_ids=[...])
    """

    MIN_CONFIDENCE_TO_MARK = 0.55

    def __init__(self, storage_backend=None):
        self._storage = storage_backend
        # Keyed by (date_str, student_id)
        self._today_records: Dict[str, AttendanceRecord] = {}
        self._current_date: str = date.today().isoformat()

    def mark_present(
        self,
        student_id: str,
        name: str,
        roll_number: str,
        confidence: float,
    ) -> Optional[AttendanceRecord]:
        """
        Mark a student present for today. No-op (returns None) if confidence
        is below MIN_CONFIDENCE_TO_MARK, to avoid low-confidence recognitions
        polluting the attendance register.
        """
        self._roll_over_day_if_needed()

        if confidence < self.MIN_CONFIDENCE_TO_MARK:
            logger.debug(
                "Skipping attendance mark for %s: confidence %.2f below threshold",
                student_id,
                confidence,
            )
            return None

        now_iso = datetime.now().isoformat(timespec="seconds")

        if student_id in self._today_records:
            record = self._today_records[student_id]
            record.last_seen = now_iso
            record.recognition_confidence = max(record.recognition_confidence, confidence)
        else:
            record = AttendanceRecord(
                student_id=student_id,
                name=name,
                roll_number=roll_number,
                date=self._current_date,
                first_seen=now_iso,
                last_seen=now_iso,
                status="present",
                recognition_confidence=confidence,
            )
            self._today_records[student_id] = record
            logger.info("Attendance marked: %s (%s) at %s", name, roll_number, now_iso)

        if self._storage is not None:
            self._storage.save_attendance_record(record)

        return record

    def finalize_day(self, all_enrolled: List[Dict[str, str]]) -> List[AttendanceRecord]:
        """
        Called at end-of-day (e.g. via a scheduled job) to explicitly mark
        every enrolled student who was never seen as "absent", so the
        attendance register has a complete row per student per day rather
        than only present-students being represented.

        Args:
            all_enrolled: list of dicts with keys student_id, name, roll_number.
        """
        self._roll_over_day_if_needed()
        absent_records: List[AttendanceRecord] = []

        for student in all_enrolled:
            sid = student["student_id"]
            if sid not in self._today_records:
                record = AttendanceRecord(
                    student_id=sid,
                    name=student["name"],
                    roll_number=student["roll_number"],
                    date=self._current_date,
                    first_seen="",
                    last_seen="",
                    status="absent",
                    recognition_confidence=0.0,
                )
                absent_records.append(record)
                if self._storage is not None:
                    self._storage.save_attendance_record(record)

        logger.info(
            "Day finalized (%s): %d present, %d absent",
            self._current_date,
            len(self._today_records),
            len(absent_records),
        )
        return list(self._today_records.values()) + absent_records

    def get_today_summary(self) -> Dict[str, int]:
        self._roll_over_day_if_needed()
        present = sum(1 for r in self._today_records.values() if r.status == "present")
        return {"present": present, "date": self._current_date}

    def get_today_records(self) -> List[AttendanceRecord]:
        self._roll_over_day_if_needed()
        return list(self._today_records.values())

    def load_today_from_storage(self) -> int:
        """
        Rehydrate today's in-memory attendance state from Firestore at
        startup. Every mark_present() call already persists to storage, but
        `_today_records` itself only ever lived in RAM — so a backend
        restart mid-class previously made /api/attendance/today (and the
        dashboard's "Present" count) drop back to zero even though the
        records were safely in Firestore the whole time. Returns the
        number of records loaded. No-op (returns 0) if no storage backend
        is configured.
        """
        self._roll_over_day_if_needed()
        if self._storage is None:
            return 0
        try:
            records = self._storage.get_attendance_for_date(self._current_date)
        except Exception:
            logger.exception("Failed to load today's attendance from storage at startup")
            return 0

        loaded = 0
        for data in records:
            if data.get("status") != "present":
                continue
            try:
                record = AttendanceRecord(
                    student_id=data["student_id"],
                    name=data["name"],
                    roll_number=data["roll_number"],
                    date=data["date"],
                    first_seen=data["first_seen"],
                    last_seen=data["last_seen"],
                    status=data["status"],
                    recognition_confidence=data.get("recognition_confidence", 0.0),
                )
            except KeyError:
                logger.warning("Skipping malformed attendance record from storage: %s", data)
                continue
            self._today_records[record.student_id] = record
            loaded += 1

        if loaded:
            logger.info(
                "Restored %d present record(s) for %s from Firestore after restart",
                loaded, self._current_date,
            )
        return loaded

    # ------------------------------------------------------------------
    def _roll_over_day_if_needed(self) -> None:
        today = date.today().isoformat()
        if today != self._current_date:
            logger.info(
                "Date rolled over from %s to %s — resetting daily attendance state",
                self._current_date,
                today,
            )
            self._current_date = today
            self._today_records = {}
