from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .gemini_client import GeminiClient
from .logic import analyze_photo, handle_message
from .models import AnalyzePhotoRequest, AnalyzePhotoResponse, SessionMessageRequest, SessionMessageResponse, SessionState
from .store import SessionStore

app = FastAPI(title="Golden Apple Beauty Advisor", version="0.4.0")
store = SessionStore()
gemini = GeminiClient()
TEMPLATE_DIR = Path(__file__).parent / "templates"


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((TEMPLATE_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "gemini_configured": bool(gemini.api_key),
        "gemini_model": gemini.model,
    }


@app.post("/v1/photo/analyze", response_model=AnalyzePhotoResponse)
async def analyze_photo_endpoint(request: AnalyzePhotoRequest) -> AnalyzePhotoResponse:
    return await analyze_photo(request, store, gemini)


@app.post("/v1/session/{session_id}/message", response_model=SessionMessageResponse)
async def session_message(session_id: str, request: SessionMessageRequest) -> SessionMessageResponse:
    try:
        return await handle_message(request.message, store, session_id, gemini)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found") from None
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"dialog failed: {exc}") from exc


@app.get("/v1/session/{session_id}", response_model=SessionState)
def get_session(session_id: str) -> SessionState:
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return session
