from __future__ import annotations

from .models import RecommendationItem


def validate_response_grounding(text: str, recommendations: list[RecommendationItem]) -> bool:
    if not text.strip():
        return False
    if not recommendations:
        return True
    normalized = text.lower()
    allowed_tokens = []
    for item in recommendations[:3]:
        allowed_tokens.extend([
            item.brand.lower(),
            item.title.split()[0].lower(),
            item.category.value.lower(),
        ])
    return any(token and token in normalized for token in allowed_tokens)
