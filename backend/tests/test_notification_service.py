"""
backend/tests/test_notification_service.py

Unit tests for NotificationService's cooldown/dedup behavior and
subscriber fan-out, since incorrect alert-flooding logic would make the
live dashboard and hardware unusable in a real classroom.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import time
import pytest

from backend.services.notification_service import NotificationService


class FakeStorage:
    def __init__(self):
        self.alerts = []

    def save_alert(self, alert_dict):
        self.alerts.append(alert_dict)


def test_alert_is_raised_and_persisted():
    storage = FakeStorage()
    notifier = NotificationService(storage_backend=storage, cooldown_seconds=60)
    alert = notifier.raise_alert(
        "sleeping", student_id="s1", student_name="Priya", message="Priya is sleepy"
    )
    assert alert is not None
    assert len(storage.alerts) == 1


def test_duplicate_alert_within_cooldown_is_suppressed():
    storage = FakeStorage()
    notifier = NotificationService(storage_backend=storage, cooldown_seconds=60)
    first = notifier.raise_alert("sleeping", student_id="s1", message="A")
    second = notifier.raise_alert("sleeping", student_id="s1", message="A again")
    assert first is not None
    assert second is None
    assert len(storage.alerts) == 1


def test_different_students_not_deduplicated_against_each_other():
    storage = FakeStorage()
    notifier = NotificationService(storage_backend=storage, cooldown_seconds=60)
    a = notifier.raise_alert("sleeping", student_id="s1", message="A")
    b = notifier.raise_alert("sleeping", student_id="s2", message="B")
    assert a is not None
    assert b is not None
    assert len(storage.alerts) == 2


def test_different_alert_types_for_same_student_not_deduplicated():
    storage = FakeStorage()
    notifier = NotificationService(storage_backend=storage, cooldown_seconds=60)
    a = notifier.raise_alert("sleeping", student_id="s1", message="A")
    b = notifier.raise_alert("low_attention", student_id="s1", message="B")
    assert a is not None
    assert b is not None


def test_alert_after_cooldown_expires_is_raised():
    storage = FakeStorage()
    notifier = NotificationService(storage_backend=storage, cooldown_seconds=0.1)
    first = notifier.raise_alert("sleeping", student_id="s1", message="A")
    time.sleep(0.15)
    second = notifier.raise_alert("sleeping", student_id="s1", message="A")
    assert first is not None
    assert second is not None


def test_subscribers_are_notified_on_alert():
    received = []
    notifier = NotificationService(cooldown_seconds=60)
    notifier.subscribe(lambda alert: received.append(alert))
    notifier.raise_alert("low_attention", student_id="s1", message="Low")
    assert len(received) == 1
    assert received[0].message == "Low"


def test_subscriber_exception_does_not_break_alert_flow():
    def bad_subscriber(alert):
        raise RuntimeError("boom")

    storage = FakeStorage()
    notifier = NotificationService(storage_backend=storage, cooldown_seconds=60)
    notifier.subscribe(bad_subscriber)
    # Should not raise, despite the subscriber blowing up.
    alert = notifier.raise_alert("sleeping", student_id="s1", message="A")
    assert alert is not None
    assert len(storage.alerts) == 1


def test_get_recent_alerts_works_without_any_storage_backend():
    """
    Regression test for the exact bug reported in production: with no
    storage backend configured (Firebase unavailable), /api/alerts/recent
    used to crash with AttributeError because alerts were never kept
    anywhere except the (absent) storage backend. Alerts must be
    retrievable purely from the in-memory buffer.
    """
    notifier = NotificationService(storage_backend=None, cooldown_seconds=60)
    notifier.raise_alert("sleeping", student_id="s1", student_name="Priya", message="Priya is sleepy")
    notifier.raise_alert("low_attention", student_id="s2", student_name="Rahul", message="Rahul is distracted")

    recent = notifier.get_recent_alerts(limit=10)
    assert len(recent) == 2
    # Newest first
    assert recent[0]["message"] == "Rahul is distracted"
    assert recent[1]["message"] == "Priya is sleepy"


def test_alert_survives_storage_backend_failure():
    """A Firestore write failure must not prevent the alert from being
    raised, returned, or retrievable — persistence is best-effort."""

    class BrokenStorage:
        def save_alert(self, d):
            raise RuntimeError("firestore is down")

    notifier = NotificationService(storage_backend=BrokenStorage(), cooldown_seconds=60)
    alert = notifier.raise_alert("sleeping", student_id="s1", message="still works")
    assert alert is not None
    assert len(notifier.get_recent_alerts()) == 1


def test_get_recent_alerts_respects_limit():
    notifier = NotificationService(cooldown_seconds=0)  # no cooldown, so repeats aren't suppressed
    for i in range(5):
        notifier.raise_alert("low_attention", student_id=f"s{i}", message=f"alert {i}")
    recent = notifier.get_recent_alerts(limit=2)
    assert len(recent) == 2
