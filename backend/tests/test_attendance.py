"""
backend/tests/test_attendance.py

Unit tests for AttendanceManager, using a fake in-memory storage backend
so no live Firebase connection is required to run these tests.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest

from backend.modules.attendance import AttendanceManager


class FakeStorage:
    def __init__(self, existing_records=None):
        self.saved_records = []
        self._existing_records = existing_records or []

    def save_attendance_record(self, record):
        self.saved_records.append(record)

    def get_attendance_for_date(self, date_str):
        return self._existing_records


@pytest.fixture
def storage():
    return FakeStorage()


@pytest.fixture
def manager(storage):
    return AttendanceManager(storage_backend=storage)


def test_mark_present_creates_record(manager, storage):
    record = manager.mark_present(
        student_id="s1", name="Aman Kumar", roll_number="21CS001", confidence=0.9
    )
    assert record is not None
    assert record.status == "present"
    assert len(storage.saved_records) == 1


def test_low_confidence_recognition_does_not_mark_attendance(manager, storage):
    record = manager.mark_present(
        student_id="s2", name="Rahul Verma", roll_number="21CS002", confidence=0.2
    )
    assert record is None
    assert len(storage.saved_records) == 0


def test_repeated_recognition_updates_last_seen_not_duplicate(manager):
    manager.mark_present(student_id="s3", name="Priya Singh", roll_number="21CS003", confidence=0.8)
    manager.mark_present(student_id="s3", name="Priya Singh", roll_number="21CS003", confidence=0.85)

    records = manager.get_today_records()
    matching = [r for r in records if r.student_id == "s3"]
    assert len(matching) == 1
    assert matching[0].recognition_confidence == 0.85


def test_finalize_day_marks_unseen_students_absent(manager):
    manager.mark_present(student_id="s4", name="Neha Patel", roll_number="21CS004", confidence=0.9)

    all_enrolled = [
        {"student_id": "s4", "name": "Neha Patel", "roll_number": "21CS004"},
        {"student_id": "s5", "name": "Vikash Yadav", "roll_number": "21CS005"},
    ]
    results = manager.finalize_day(all_enrolled)

    statuses = {r.student_id: r.status for r in results}
    assert statuses["s4"] == "present"
    assert statuses["s5"] == "absent"


def test_today_summary_counts_present_only(manager):
    manager.mark_present(student_id="s6", name="A", roll_number="1", confidence=0.9)
    manager.mark_present(student_id="s7", name="B", roll_number="2", confidence=0.9)
    summary = manager.get_today_summary()
    assert summary["present"] == 2


def test_load_today_from_storage_rehydrates_after_restart():
    """A backend restart must not lose today's attendance: the in-memory
    manager should be rehydrated from whatever was already persisted."""
    from datetime import date

    today = date.today().isoformat()
    existing = [
        {
            "student_id": "s8",
            "name": "Karan Mehta",
            "roll_number": "21CS008",
            "date": today,
            "first_seen": "2026-08-22T09:00:00",
            "last_seen": "2026-08-22T09:05:00",
            "status": "present",
            "recognition_confidence": 0.88,
        },
        {
            "student_id": "s9",
            "name": "Absent Student",
            "roll_number": "21CS009",
            "date": today,
            "first_seen": "",
            "last_seen": "",
            "status": "absent",
            "recognition_confidence": 0.0,
        },
    ]
    storage = FakeStorage(existing_records=existing)
    manager = AttendanceManager(storage_backend=storage)

    loaded = manager.load_today_from_storage()

    assert loaded == 1  # only the "present" record is rehydrated
    records = manager.get_today_records()
    assert len(records) == 1
    assert records[0].student_id == "s8"
    assert records[0].recognition_confidence == 0.88


def test_load_today_from_storage_is_noop_without_backend():
    manager = AttendanceManager(storage_backend=None)
    assert manager.load_today_from_storage() == 0
