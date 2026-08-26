"""
backend/tests/test_face_recognition_module.py

Unit tests for FaceRecognitionService's in-memory index, using a fake
storage backend and a stub for the underlying `face_recognition` library
calls (dlib-based) so these tests don't require a real dlib build or
real face images to run.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
import pytest

from backend.modules.face_recognition_module import FaceRecognitionService, StudentEncoding


class FakeStorage:
    def __init__(self, fail=False):
        self.fail = fail
        self.saved = []

    def save_student_encoding(self, record):
        if self.fail:
            raise RuntimeError("firestore unavailable")
        self.saved.append(record)


def _make_service_with_manual_enrollment(storage=None):
    """
    Bypasses enroll_student's dependency on the real face_recognition
    library (dlib) by inserting directly into the service's internal
    index — the same code path list_enrolled() and identify_faces() read
    from, so this still exercises the real logic under test.
    """
    service = FaceRecognitionService(storage_backend=storage)
    record = StudentEncoding(
        student_id="s1", name="Aman Kumar", roll_number="21CS001",
        encoding=np.zeros(128, dtype=np.float64),
    )
    service._index["s1"] = record
    return service


def test_list_enrolled_returns_in_memory_students_without_storage():
    """
    Regression test for the exact bug reported: /api/students used to call
    firebase.list_students() directly and crash with AttributeError when
    Firebase was unavailable. list_enrolled() must work purely from the
    in-memory index.
    """
    service = _make_service_with_manual_enrollment(storage=None)
    result = service.list_enrolled()
    assert result == [{"student_id": "s1", "name": "Aman Kumar", "roll_number": "21CS001"}]


def test_enrolled_count_reflects_index():
    service = _make_service_with_manual_enrollment(storage=None)
    assert service.enrolled_count == 1


def test_remove_student_updates_list_enrolled():
    service = _make_service_with_manual_enrollment(storage=None)
    service.remove_student("s1")
    assert service.list_enrolled() == []


def test_list_enrolled_empty_when_nothing_registered():
    service = FaceRecognitionService(storage_backend=None)
    assert service.list_enrolled() == []
