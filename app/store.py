from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import settings
from .models import SessionState


class SessionStore:
    def __init__(self) -> None:
        self._items: dict[str, tuple[datetime, SessionState]] = {}

    def save(self, session: SessionState) -> None:
        expires = datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours)
        self._items[session.session_id] = (expires, session)

    def get(self, session_id: str) -> SessionState | None:
        item = self._items.get(session_id)
        if not item:
            return None
        expires, session = item
        if expires < datetime.now(timezone.utc):
            self._items.pop(session_id, None)
            return None
        return session
