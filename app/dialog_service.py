from __future__ import annotations

import re
from functools import lru_cache

from .catalog import load_catalog
from .models import ConversationTurn, ProductCategory, SessionState

MAX_CONVERSATION_TURNS = 24
MEMORY_QUESTION_HINTS = [
    "что я у тебя спрашивал",
    "что я спрашивал",
    "что ты советовал в первый раз",
    "на чем мы остановились",
    "на чём мы остановились",
    "напомни прошлую подборку",
    "напомни подборку",
    "что было до этого",
    "что ты советовал",
    "что ты рекомендовал",
    "о чем мы говорили",
    "о чём мы говорили",
    "напомни, что было",
]


@lru_cache(maxsize=1)
def _catalog_index() -> dict[str, object]:
    products = load_catalog()
    by_sku = {product.sku: product for product in products}
    return {"by_sku": by_sku}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def append_conversation_turn(session: SessionState, role: str, message: str) -> None:
    text = (message or "").strip()
    if not text:
        return
    session.conversation_history.append(ConversationTurn(role=role, message=text))
    if len(session.conversation_history) > MAX_CONVERSATION_TURNS:
        session.conversation_history = session.conversation_history[-MAX_CONVERSATION_TURNS:]


def is_memory_question(message: str) -> bool:
    normalized = normalize_text(message)
    return any(hint in normalized for hint in MEMORY_QUESTION_HINTS)


def recent_user_messages(session: SessionState, limit: int = 3, exclude_last: str | None = None) -> list[str]:
    items = [turn.message for turn in session.conversation_history if turn.role == "user"]
    if exclude_last and items and items[-1] == exclude_last:
        items = items[:-1]
    return items[-limit:]


def first_agent_recommendation(session: SessionState) -> str | None:
    for turn in session.conversation_history:
        if turn.role == "assistant" and ("- " in turn.message or "вот что выглядит удачно на старте" in turn.message.lower()):
            return turn.message
    return None


def last_assistant_message(session: SessionState) -> str | None:
    for turn in reversed(session.conversation_history):
        if turn.role == "assistant":
            return turn.message
    return None


def summarize_message(text: str, max_len: int = 140) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1].rstrip() + "…"


def answer_from_conversation_history(session: SessionState, message: str) -> str:
    normalized = normalize_text(message)
    user_messages = recent_user_messages(session, exclude_last=message)
    if "что я" in normalized and ("спрашивал" in normalized or "говорил" in normalized):
        if not user_messages:
            return "Пока ты ещё ничего не спрашивал в этой сессии."
        lines = ["Вот последние вопросы в этой сессии:"]
        for item in user_messages:
            lines.append(f"- {summarize_message(item)}")
        return "\n".join(lines)
    if "в первый раз" in normalized or "первый" in normalized:
        first_reply = first_agent_recommendation(session)
        if first_reply:
            return f"В первый раз я советовал вот это:\n{first_reply}"
        return "Не вижу в истории первой подборки, на которую можно точно сослаться."
    if "остановились" in normalized:
        last_reply = last_assistant_message(session)
        if last_reply:
            return f"Мы остановились на этом:\n{last_reply}"
        return "Пока не на чем останавливаться — в истории ещё нет прошлого ответа."
    if "прошлую подборку" in normalized or "напомни подборку" in normalized:
        last_reply = last_assistant_message(session)
        if last_reply:
            return f"Напоминаю прошлую подборку:\n{last_reply}"
        return "Не вижу сохранённой прошлой подборки в этой сессии."
    if user_messages:
        lines = ["Коротко по истории текущего чата:"]
        for item in user_messages:
            lines.append(f"- {summarize_message(item)}")
        return "\n".join(lines)
    return "Пока в этой сессии нет истории, на которую можно опереться."


def recommendations_from_current(session: SessionState, target_categories: list[ProductCategory] | None = None):
    selection = session.dialog_context.current_recommendations
    categories = target_categories or session.current_plan.required_categories
    catalog = _catalog_index()["by_sku"]
    items = []
    for category in categories:
        sku = selection.get(category)
        if not sku:
            continue
        product = catalog.get(sku)
        if not product:
            continue
        items.append({
            "sku": product.sku,
            "title": product.title,
            "brand": product.brand,
            "category": product.category,
            "domain": product.domain,
            "price_segment": product.price_segment,
            "price_value": product.price_value,
            "why": "текущий выбор",
            "vector_score": 0.0,
            "rule_score": 0.0,
            "final_score": 0.0,
        })
    return items
