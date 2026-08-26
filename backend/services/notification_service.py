
from __future__ import annotations
 
import logging
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Callable, Deque, Dict, List, Optional
 
logger = logging.getLogger("smart_classroom.notification_service")
 
 
@dataclass
class Alert:
    alert_type: str  # "sleeping" | "low_attention" | "yawning" | "face_not_detected" | "unrecognized_person"
    student_id: Optional[str]
    student_name: Optional[str]
    message: str
    severity: str  # "info" | "warning" | "critical"
    timestamp: float
    # Generated once here and carried through unchanged to in-memory
    # history, Firestore, and the API response — the frontend's list
    # `key` and any future "mark as read" / "dismiss" action all need to
    # reference the exact same ID, not independently-generated ones at
    # each layer. Placed last (with a default) so every other field
    # stays required, same as before this change.
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
 
 
class NotificationService:
    """
    Usage:
        notifier = NotificationService(storage_backend=firebase_service, esp32_service=esp32)
        notifier.raise_alert("sleeping", student_id="s1", student_name="Priya Singh",
                              message="Priya Singh is showing signs of sleepiness",
                              severity="warning")
 
    Recent alerts are always kept in an in-memory ring buffer (independent
    of whether a storage backend is configured), so `/api/alerts/recent`
    works correctly even when Firebase is unavailable — persistence to
    Firestore (when present) is best-effort in addition to, not instead
    of, this in-memory history.
    """
 
    MAX_IN_MEMORY_ALERTS = 200
 
    def __init__(
        self,
        storage_backend=None,
        esp32_service=None,
        cooldown_seconds: float = 60.0,
    ):
        self._storage = storage_backend
        self._esp32 = esp32_service
        self._cooldown_seconds = cooldown_seconds
        # Key: (alert_type, student_id) -> last raised timestamp
        self._last_raised: Dict[tuple, float] = {}
        self._subscribers: list[Callable[[Alert], None]] = []
        self._recent_alerts: Deque[Alert] = deque(maxlen=self.MAX_IN_MEMORY_ALERTS)
 
    def subscribe(self, callback: Callable[[Alert], None]) -> None:
        """Register a callback invoked synchronously whenever an alert fires
        (e.g. to push over a WebSocket to the live dashboard)."""
        self._subscribers.append(callback)
 
    def raise_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "warning",
        student_id: Optional[str] = None,
        student_name: Optional[str] = None,
        trigger_hardware: bool = False,
    ) -> Optional[Alert]:
        """
        Raise an alert, subject to a per-(type, student) cooldown so the same
        condition doesn't flood the dashboard/hardware every frame.
 
        Returns the Alert if it was actually raised, or None if suppressed
        by the cooldown.
        """
        key = (alert_type, student_id)
        now = time.time()
        last = self._last_raised.get(key, 0.0)
        if now - last < self._cooldown_seconds:
            return None
 
        self._last_raised[key] = now
        alert = Alert(
            alert_type=alert_type,
            student_id=student_id,
            student_name=student_name,
            message=message,
            severity=severity,
            timestamp=now,
        )
        self._recent_alerts.append(alert)
 
        if self._storage is not None:
            try:
                self._storage.save_alert(
                    {
                        "alert_id": alert.alert_id,
                        "alert_type": alert.alert_type,
                        "student_id": alert.student_id,
                        "student_name": alert.student_name,
                        "message": alert.message,
                        "severity": alert.severity,
                        "timestamp": alert.timestamp,
                    }
                )
            except Exception:
                # Persistence is best-effort: an alert must still reach the
                # in-memory buffer/subscribers/hardware even if Firestore
                # is down, so the live dashboard doesn't lose real-time
                # alerts over a storage hiccup.
                logger.exception("Failed to persist alert to storage backend")
 
        for callback in self._subscribers:
            try:
                callback(alert)
            except Exception:
                logger.exception("Alert subscriber callback raised an exception")
 
        if trigger_hardware and self._esp32 is not None:
            try:
                self._esp32.trigger_alert(severity=severity, message=message)
            except Exception:
                logger.exception("Failed to forward alert to ESP32")
 
        logger.info("[ALERT:%s] %s", severity.upper(), message)
        return alert
 
    def get_recent_alerts(self, limit: int = 50) -> List[Dict]:
        """
        Return the most recent alerts, newest first, from the in-memory
        buffer. This is the source of truth for `/api/alerts/recent` —
        it works regardless of whether Firebase is configured.
        """
        items = list(self._recent_alerts)[-limit:]
        items.reverse()
        return [asdict(a) for a in items]
 