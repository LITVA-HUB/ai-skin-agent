from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings, validate_settings
from .gemini_client import GeminiClient
from .observability import log_event, log_warning
from .store import SessionStore


def build_runtime() -> tuple[SessionStore, GeminiClient]:
    store = SessionStore()
    gemini = GeminiClient()
    return store, gemini


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings_errors = validate_settings()
    if settings_errors:
        for error in settings_errors:
            log_warning('startup_config_warning', message=error)
    store, gemini = build_runtime()
    app.state.store = store
    app.state.gemini = gemini
    app.state.settings_errors = settings_errors
    log_event('startup', version=app.version, storage=store.stats(), gemini_configured=bool(gemini.api_key), sqlite_path=settings.sqlite_path, settings_errors=settings_errors)
    yield
    log_event('shutdown', version=app.version)
