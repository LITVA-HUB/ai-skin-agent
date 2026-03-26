from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env() -> None:
    env_path = Path(__file__).resolve().parent.parent / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ[key.strip()] = value.strip()


_load_env()


@dataclass(slots=True)
class Settings:
    gemini_api_key: str | None = os.getenv('GEMINI_API_KEY')
    gemini_model: str = os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview')
    session_ttl_hours: int = int(os.getenv('SESSION_TTL_HOURS', '24'))
    session_store_backend: str = os.getenv('SESSION_STORE_BACKEND', 'sqlite')
    sqlite_path: str = os.getenv('SQLITE_PATH', str(Path(__file__).resolve().parent / 'data' / 'sessions.sqlite3'))
    log_level: str = os.getenv('LOG_LEVEL', 'INFO')
    strict_fail_safe: bool = os.getenv('STRICT_FAIL_SAFE', 'true').lower() in {'1', 'true', 'yes'}


settings = Settings()


def validate_settings() -> list[str]:
    errors: list[str] = []
    if settings.session_ttl_hours <= 0:
        errors.append('SESSION_TTL_HOURS must be > 0')
    if settings.session_store_backend not in {'sqlite', 'memory'}:
        errors.append('SESSION_STORE_BACKEND must be sqlite or memory')
    if not settings.sqlite_path:
        errors.append('SQLITE_PATH must not be empty')
    if settings.log_level.upper() not in {'DEBUG', 'INFO', 'WARNING', 'ERROR'}:
        errors.append('LOG_LEVEL must be DEBUG|INFO|WARNING|ERROR')
    return errors
