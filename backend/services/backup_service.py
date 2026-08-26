"""
backend/services/backup_service.py

Backup Service.

Exports a timestamped JSON snapshot of the system's key data (enrolled
students, today's attendance, and recent alerts) to a local `backups/`
directory, and can restore attendance records from a snapshot back into
the running AttendanceManager.

Works whether or not Firebase is configured:
  - With Firebase: pulls today's attendance from Firestore for a fuller
    snapshot.
  - Without Firebase: falls back to whatever's in the in-memory
    AttendanceManager for the current process, and says so explicitly in
    the snapshot's metadata rather than silently producing a partial
    backup that looks complete.

Restore only ever adds/overwrites attendance records for the students
present in the snapshot — it does not delete anything not mentioned in
the file, so a restore can't accidentally wipe out data outside the
snapshot's scope.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("smart_classroom.backup_service")

_BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"


class BackupServiceError(Exception):
    pass


class BackupService:
    def __init__(
        self,
        attendance_manager,
        recognition_service,
        notification_service,
        firebase_service=None,
        backup_dir: Optional[Path] = None,
    ):
        self._attendance_manager = attendance_manager
        self._recognition_service = recognition_service
        self._notification_service = notification_service
        self._firebase = firebase_service
        self._backup_dir = backup_dir or _BACKUP_DIR
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> Dict[str, Any]:
        students = self._recognition_service.list_enrolled()

        if self._firebase is not None:
            try:
                attendance_today = self._firebase.get_attendance_for_date(
                    datetime.now().date().isoformat()
                )
                source = "firestore"
            except Exception:
                logger.exception("Firestore read failed during backup; falling back to in-memory data")
                attendance_today = [asdict(r) for r in self._attendance_manager.get_today_records()]
                source = "in_memory_fallback"
        else:
            attendance_today = [asdict(r) for r in self._attendance_manager.get_today_records()]
            source = "in_memory"

        alerts = self._notification_service.get_recent_alerts(limit=200)

        snapshot = {
            "backup_id": str(uuid.uuid4()),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "data_source": source,
            "students": students,
            "attendance": attendance_today,
            "alerts": alerts,
        }

        filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = self._backup_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)

        logger.info(
            "Backup created: %s (%d students, %d attendance records, %d alerts, source=%s)",
            filename, len(students), len(attendance_today), len(alerts), source,
        )
        return {"filename": filename, **snapshot}

    def list_backups(self) -> List[Dict[str, Any]]:
        results = []
        for path in sorted(self._backup_dir.glob("backup_*.json"), reverse=True):
            try:
                stat = path.stat()
                with open(path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                results.append(
                    {
                        "filename": path.name,
                        "created_at": meta.get("created_at"),
                        "data_source": meta.get("data_source"),
                        "student_count": len(meta.get("students", [])),
                        "attendance_count": len(meta.get("attendance", [])),
                        "alert_count": len(meta.get("alerts", [])),
                        "size_bytes": stat.st_size,
                    }
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Skipping unreadable backup file %s: %s", path.name, e)
        return results

    def restore_backup(self, filename: str) -> Dict[str, Any]:
        # Reject any filename that isn't a bare name inside the backup dir —
        # prevents path traversal (e.g. "../../etc/passwd") from a
        # user-supplied filename ever escaping _BACKUP_DIR.
        safe_name = Path(filename).name
        path = self._backup_dir / safe_name
        if not path.is_file() or path.parent.resolve() != self._backup_dir.resolve():
            raise BackupServiceError(f"Backup file not found: {filename}")

        with open(path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)

        restored_count = 0
        for record in snapshot.get("attendance", []):
            try:
                self._attendance_manager.mark_present(
                    student_id=record["student_id"],
                    name=record["name"],
                    roll_number=record["roll_number"],
                    confidence=max(record.get("recognition_confidence", 1.0), 0.55),
                )
                restored_count += 1
            except (KeyError, TypeError) as e:
                logger.warning("Skipping malformed attendance record during restore: %s", e)

        logger.info("Restored %d attendance record(s) from %s", restored_count, safe_name)
        return {
            "filename": safe_name,
            "restored_attendance_records": restored_count,
            "backup_created_at": snapshot.get("created_at"),
        }
