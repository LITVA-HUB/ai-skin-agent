from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .gemini_client import GeminiClient
from .logic import analyze_photo, handle_message
from .models import AddCartItemRequest, AnalyzePhotoRequest, AnalyzePhotoResponse, CartItem, CartResponse, SessionMessageRequest, SessionMessageResponse, SessionState, UpdateCartItemRequest
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


@app.get("/v1/session/{session_id}/cart", response_model=CartResponse)
def get_cart(session_id: str) -> CartResponse:
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return CartResponse(
        cart=session.cart,
        total_items=session.cart.total_items,
        total_price=session.cart.total_price,
    )


@app.post("/v1/session/{session_id}/cart/items", response_model=CartResponse)
def add_cart_item(session_id: str, request: AddCartItemRequest) -> CartResponse:
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    existing = next((item for item in session.cart.items if item.sku == request.sku), None)
    if existing:
        existing.quantity += 1
    else:
        session.cart.items.append(CartItem(**request.model_dump(), quantity=1))

    store.save(session)
    return CartResponse(cart=session.cart, total_items=session.cart.total_items, total_price=session.cart.total_price)


@app.patch("/v1/session/{session_id}/cart/items/{sku}", response_model=CartResponse)
def update_cart_item(session_id: str, sku: str, request: UpdateCartItemRequest) -> CartResponse:
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    item = next((item for item in session.cart.items if item.sku == sku), None)
    if not item:
        raise HTTPException(status_code=404, detail="cart item not found")

    if request.quantity <= 0:
        session.cart.items = [cart_item for cart_item in session.cart.items if cart_item.sku != sku]
    else:
        item.quantity = request.quantity

    store.save(session)
    return CartResponse(cart=session.cart, total_items=session.cart.total_items, total_price=session.cart.total_price)


@app.delete("/v1/session/{session_id}/cart/items/{sku}", response_model=CartResponse)
def remove_cart_item(session_id: str, sku: str) -> CartResponse:
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    session.cart.items = [item for item in session.cart.items if item.sku != sku]
    store.save(session)
    return CartResponse(cart=session.cart, total_items=session.cart.total_items, total_price=session.cart.total_price)


@app.delete("/v1/session/{session_id}/cart", response_model=CartResponse)
def clear_cart(session_id: str) -> CartResponse:
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    session.cart.items = []
    store.save(session)
    return CartResponse(cart=session.cart, total_items=session.cart.total_items, total_price=session.cart.total_price)
