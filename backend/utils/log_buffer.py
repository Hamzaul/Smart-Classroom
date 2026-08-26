"""
backend/utils/log_buffer.py

In-Memory Log Buffer.

A bounded logging.Handler that keeps the last N formatted log records in
memory, so the dashboard's Logs page can display real backend activity
without needing a separate log-aggregation service. Attached to the root
logger in app.py at startup.

Secrets are never logged in this codebase's log statements (credentials,
API keys, and encodings are deliberately excluded from every log.info/
log.exception call throughout the project), so nothing extra needs to be
redacted here — but as a defense-in-depth measure, `_looks_sensitive`
drops any record whose message contains common secret-ish substrings
before it ever reaches the buffer.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List

_SENSITIVE_MARKERS = ("password", "secret", "private_key", "api_key", "credential")


@dataclass
class LogRecordEntry:
    timestamp: float
    level: str
    logger_name: str
    message: str


class InMemoryLogHandler(logging.Handler):
    def __init__(self, capacity: int = 500):
        super().__init__()
        self._buffer: Deque[LogRecordEntry] = deque(maxlen=capacity)
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            if _looks_sensitive(message):
                message = "[redacted: log line withheld — looked like it might contain a secret]"
            self._buffer.append(
                LogRecordEntry(
                    timestamp=record.created,
                    level=record.levelname,
                    logger_name=record.name,
                    message=message,
                )
            )
        except Exception:
            # A logging handler must never itself raise — that would break
            # logging for the whole application.
            pass

    def get_recent(self, limit: int = 200, level: str | None = None) -> List[Dict]:
        items = list(self._buffer)
        if level:
            items = [i for i in items if i.level == level.upper()]
        items = items[-limit:]
        items.reverse()
        return [
            {
                "timestamp": i.timestamp,
                "level": i.level,
                "logger": i.logger_name,
                "message": i.message,
            }
            for i in items
        ]


def _looks_sensitive(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _SENSITIVE_MARKERS)


_log_handler_singleton: InMemoryLogHandler | None = None


def get_log_handler() -> InMemoryLogHandler:
    global _log_handler_singleton
    if _log_handler_singleton is None:
        _log_handler_singleton = InMemoryLogHandler()
    return _log_handler_singleton
