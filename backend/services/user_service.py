"""
backend/services/user_service.py

User Management Service.

The project has no authentication system (login/sessions are out of
scope for this build), so "Users" here means the small set of
admin/instructor accounts who can access the dashboard — not students
(those are tracked separately by FaceRecognitionService/AttendanceManager).

This is a genuine, working in-memory CRUD store rather than a stub page:
it persists for the lifetime of the backend process. It is intentionally
NOT wired to Firestore, since without an auth layer there's no secure way
to gate who can write to a persisted user list — see the Users page's
own in-dashboard note, which says the same thing rather than silently
pretending this is production-grade user management.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("smart_classroom.user_service")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_VALID_ROLES = {"administrator", "instructor", "viewer"}


class UserServiceError(Exception):
    pass


@dataclass
class AppUser:
    user_id: str
    name: str
    email: str
    role: str
    created_at: str = field(default="")


class UserService:
    def __init__(self):
        self._users: Dict[str, AppUser] = {}
        # Seed with a default administrator so the Users page is never
        # empty on a fresh install.
        self._seed_default_admin()

    def _seed_default_admin(self) -> None:
        from datetime import datetime

        admin = AppUser(
            user_id=str(uuid.uuid4()),
            name="Admin",
            email="admin@smartclassroom.local",
            role="administrator",
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        self._users[admin.user_id] = admin

    def list_users(self) -> List[Dict]:
        return [asdict(u) for u in self._users.values()]

    def create_user(self, name: str, email: str, role: str) -> AppUser:
        from datetime import datetime

        name = (name or "").strip()
        email = (email or "").strip().lower()
        role = (role or "").strip().lower()

        if not name:
            raise UserServiceError("Field 'name' is required")
        if not _EMAIL_RE.match(email):
            raise UserServiceError("A valid 'email' is required")
        if role not in _VALID_ROLES:
            raise UserServiceError(
                f"'role' must be one of: {', '.join(sorted(_VALID_ROLES))}"
            )
        if any(u.email == email for u in self._users.values()):
            raise UserServiceError(f"A user with email '{email}' already exists")

        user = AppUser(
            user_id=str(uuid.uuid4()),
            name=name,
            email=email,
            role=role,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        self._users[user.user_id] = user
        logger.info("User created: %s (%s, role=%s)", name, email, role)
        return user

    def delete_user(self, user_id: str) -> None:
        if user_id not in self._users:
            raise UserServiceError(f"No user with id '{user_id}'")
        if len(self._users) == 1:
            raise UserServiceError("Cannot delete the last remaining user")
        del self._users[user_id]
        logger.info("User deleted: %s", user_id)
