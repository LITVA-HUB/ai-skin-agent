from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import settings
from .models import SessionState


class SessionStore:
    def __init__(self) -> None:
        self.backend = settings.session_store_backend
        if self.backend == 'sqlite':
            self.db_path = Path(settings.sqlite_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_sqlite()
        else:
            self._items: dict[str, tuple[datetime, SessionState]] = {}

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_sqlite(self) -> None:
        with self._connect() as conn:
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    expires_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                '''
            )
            conn.commit()

    def _ensure_migrations(self) -> None:
        with self._connect() as conn:
            columns = {row[1] for row in conn.execute('PRAGMA table_info(sessions)').fetchall()}
            if 'created_at' not in columns:
                conn.execute("ALTER TABLE sessions ADD COLUMN created_at TEXT DEFAULT ''")
            if 'updated_at' not in columns:
                conn.execute("ALTER TABLE sessions ADD COLUMN updated_at TEXT DEFAULT ''")
            conn.commit()

    def save(self, session: SessionState) -> None:
        expires = datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours)
        if self.backend == 'sqlite':
            self._ensure_migrations()
            now = datetime.now(timezone.utc).isoformat()
            payload = session.model_dump_json()
            with self._connect() as conn:
                existing = conn.execute('SELECT created_at FROM sessions WHERE session_id = ?', (session.session_id,)).fetchone()
                created_at = existing[0] if existing and existing[0] else now
                conn.execute(
                    'INSERT OR REPLACE INTO sessions(session_id, expires_at, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                    (session.session_id, expires.isoformat(), payload, created_at, now),
                )
                conn.commit()
            return
        self._items[session.session_id] = (expires, session)

    def get(self, session_id: str) -> SessionState | None:
        if self.backend == 'sqlite':
            with self._connect() as conn:
                row = conn.execute('SELECT expires_at, payload FROM sessions WHERE session_id = ?', (session_id,)).fetchone()
                if not row:
                    return None
                expires_at, payload = row
                expires = datetime.fromisoformat(expires_at)
                if expires < datetime.now(timezone.utc):
                    conn.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
                    conn.commit()
                    return None
                return SessionState.model_validate(json.loads(payload))
        item = self._items.get(session_id)
        if not item:
            return None
        expires, session = item
        if expires < datetime.now(timezone.utc):
            self._items.pop(session_id, None)
            return None
        return session

    def cleanup_expired(self) -> int:
        now = datetime.now(timezone.utc)
        if self.backend == 'sqlite':
            with self._connect() as conn:
                result = conn.execute('DELETE FROM sessions WHERE expires_at < ?', (now.isoformat(),))
                conn.commit()
                return result.rowcount or 0
        expired = [session_id for session_id, (expires, _) in self._items.items() if expires < now]
        for session_id in expired:
            self._items.pop(session_id, None)
        return len(expired)

    def stats(self) -> dict[str, object]:
        cleaned = self.cleanup_expired()
        if self.backend == 'sqlite':
            self._ensure_migrations()
            with self._connect() as conn:
                count = conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
            return {'backend': 'sqlite', 'sessions': count, 'path': str(self.db_path), 'cleaned_expired': cleaned}
        return {'backend': 'memory', 'sessions': len(self._items), 'cleaned_expired': cleaned}
