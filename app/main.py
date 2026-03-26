from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from .logic import analyze_photo, handle_message
from .models import AnalyzePhotoRequest, AnalyzePhotoResponse, SessionMessageRequest, SessionMessageResponse, SessionState
from .observability import log_error, new_request_id
from .runtime import lifespan

app = FastAPI(title="Golden Apple Beauty Advisor", version="0.5.1", lifespan=lifespan)
TEMPLATE_DIR = Path(__file__).parent / "templates"


def ensure_runtime(request: Request):
    if not hasattr(request.app.state, 'store') or not hasattr(request.app.state, 'gemini'):
        from .runtime import build_runtime
        store, gemini = build_runtime()
        request.app.state.store = store
        request.app.state.gemini = gemini
    return request.app.state.store, request.app.state.gemini


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((TEMPLATE_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/health")
def health(request: Request) -> dict[str, object]:
    store, gemini = ensure_runtime(request)
    return {
        "status": "ok",
        "gemini_configured": bool(gemini.api_key),
        "gemini_model": gemini.model,
        "version": app.version,
        "storage": store.stats()['backend'],
        "settings_errors": getattr(request.app.state, 'settings_errors', []),
        "production_ready": False,
    }


@app.get('/ready')
def ready(request: Request) -> dict[str, object]:
    store, gemini = ensure_runtime(request)
    stats = store.stats()
    settings_errors = getattr(request.app.state, 'settings_errors', [])
    return {
        'status': 'ready' if not settings_errors else 'degraded',
        'version': app.version,
        'store': stats,
        'gemini_configured': bool(gemini.api_key),
        'settings_errors': settings_errors,
    }


@app.post("/v1/photo/analyze", response_model=AnalyzePhotoResponse)
async def analyze_photo_endpoint(request: AnalyzePhotoRequest, http_request: Request) -> AnalyzePhotoResponse:
    store, gemini = ensure_runtime(http_request)
    return await analyze_photo(request, store, gemini)


@app.post("/v1/session/{session_id}/message", response_model=SessionMessageResponse)
async def session_message(session_id: str, request: SessionMessageRequest, http_request: Request) -> SessionMessageResponse:
    store, gemini = ensure_runtime(http_request)
    request_id = new_request_id()
    try:
        return await handle_message(request.message, store, session_id, gemini)
    except KeyError:
        log_error('session_message_not_found', request_id=request_id, session_id=session_id)
        raise HTTPException(status_code=404, detail="session not found") from None
    except Exception as exc:
        log_error('session_message_failed', request_id=request_id, session_id=session_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"dialog failed: {exc}") from exc


@app.get("/v1/session/{session_id}", response_model=SessionState)
def get_session(session_id: str, request: Request) -> SessionState:
    store, _ = ensure_runtime(request)
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return session
