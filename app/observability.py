from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import settings

LOG_DIR = Path(__file__).resolve().parent / 'data' / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'app.log'

logger = logging.getLogger('beauty_advisor')
if not logger.handlers:
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)


def new_request_id() -> str:
    return str(uuid.uuid4())


def log_event(event: str, **payload) -> None:
    record = {
        'ts': datetime.now(timezone.utc).isoformat(),
        'event': event,
        **payload,
    }
    logger.info(json.dumps(record, ensure_ascii=False))


def log_warning(event: str, **payload) -> None:
    log_event(event, level='warning', **payload)


def log_error(event: str, **payload) -> None:
    log_event(event, level='error', **payload)
