from __future__ import annotations

from .models import ProductCategory, RecommendationPlan

LOOK_REQUIRED_CATEGORIES = {
    'sensual': [ProductCategory.lipstick, ProductCategory.mascara, ProductCategory.foundation],
    'glam': [ProductCategory.foundation, ProductCategory.mascara, ProductCategory.blush],
    'soft_luxury': [ProductCategory.primer, ProductCategory.foundation, ProductCategory.blush],
    'fresh': [ProductCategory.skin_tint, ProductCategory.blush, ProductCategory.lip_tint],
}

FOCUS_REQUIRED_CATEGORIES = {
    'lips': [ProductCategory.lipstick, ProductCategory.lip_liner],
    'eyes': [ProductCategory.mascara, ProductCategory.eyeliner],
    'cheeks': [ProductCategory.blush, ProductCategory.highlighter],
}

FALLBACK_CATEGORIES = {
    ProductCategory.lipstick: [ProductCategory.lip_tint, ProductCategory.lip_gloss],
    ProductCategory.lip_liner: [ProductCategory.lipstick, ProductCategory.lip_gloss],
    ProductCategory.eyeliner: [ProductCategory.mascara, ProductCategory.eyeshadow_palette],
    ProductCategory.eyeshadow_palette: [ProductCategory.eyeliner, ProductCategory.mascara],
    ProductCategory.foundation: [ProductCategory.skin_tint, ProductCategory.concealer],
    ProductCategory.primer: [ProductCategory.foundation, ProductCategory.highlighter],
    ProductCategory.highlighter: [ProductCategory.blush, ProductCategory.primer],
}


def enforce_look_categories(categories: list[ProductCategory], plan: RecommendationPlan) -> list[ProductCategory]:
    ordered = list(categories)
    for category in LOOK_REQUIRED_CATEGORIES.get(plan.look_strategy or '', []):
        if category not in ordered:
            ordered.insert(0, category)
    for feature in plan.focus_features:
        for category in FOCUS_REQUIRED_CATEGORIES.get(feature, []):
            if category not in ordered:
                ordered.append(category)
    return list(dict.fromkeys(ordered))


def fallback_categories_for(category: ProductCategory) -> list[ProductCategory]:
    return FALLBACK_CATEGORIES.get(category, [])
