from __future__ import annotations

from .catalog import load_catalog
from .models import ProductCategory, RecommendationItem, RecommendationPlan, SessionState

LIP_CATEGORIES = {ProductCategory.lipstick, ProductCategory.lip_tint, ProductCategory.lip_gloss, ProductCategory.lip_liner}
EYE_CATEGORIES = {ProductCategory.mascara, ProductCategory.eyeliner, ProductCategory.eyeshadow_palette, ProductCategory.brow_pencil, ProductCategory.brow_gel}
CHEEK_CATEGORIES = {ProductCategory.blush, ProductCategory.bronzer, ProductCategory.highlighter, ProductCategory.contour}
BASE_CATEGORIES = {ProductCategory.primer, ProductCategory.foundation, ProductCategory.skin_tint, ProductCategory.concealer, ProductCategory.powder}


def selected_products_map(items: list[RecommendationItem]):
    catalog = {product.sku: product for product in load_catalog()}
    result = {}
    for item in items:
        product = catalog.get(item.sku)
        if product:
            result[item.category] = product
    return result


def infer_harmony_profile(plan: RecommendationPlan, items: list[RecommendationItem]) -> dict[str, object]:
    selected = selected_products_map(items)
    colors = []
    finishes = []
    focus = []
    for category, product in selected.items():
        colors.extend(product.color_families)
        finishes.extend(product.finishes)
        if category in LIP_CATEGORIES:
            focus.append('lips')
        if category in EYE_CATEGORIES:
            focus.append('eyes')
        if category in CHEEK_CATEGORIES:
            focus.append('cheeks')
    dominant_color = next((color for color in plan.preferred_color_families if color in colors), colors[0] if colors else None)
    dominant_finish = next((finish for finish in plan.preferred_finishes if finish in finishes), finishes[0] if finishes else None)
    return {
        'dominant_color': dominant_color,
        'dominant_finish': dominant_finish,
        'focus_features': list(dict.fromkeys(plan.focus_features or focus)),
        'look_strategy': plan.look_strategy,
        'accent_balance': plan.accent_balance,
    }


def harmony_bonus(category: ProductCategory, product, look_profile: dict[str, object]) -> float:
    bonus = 0.0
    dominant_color = look_profile.get('dominant_color')
    dominant_finish = look_profile.get('dominant_finish')
    focus_features = set(look_profile.get('focus_features') or [])
    look_strategy = look_profile.get('look_strategy')
    accent_balance = look_profile.get('accent_balance')

    if dominant_color and dominant_color in product.color_families:
        bonus += 0.08
    if dominant_finish and dominant_finish in product.finishes:
        bonus += 0.05

    if accent_balance == 'feature_focus':
        if 'lips' in focus_features and category in LIP_CATEGORIES:
            bonus += 0.08
        if 'eyes' in focus_features and category in EYE_CATEGORIES:
            bonus += 0.08
        if 'cheeks' in focus_features and category in CHEEK_CATEGORIES:
            bonus += 0.08
        if 'lips' in focus_features and category in EYE_CATEGORIES and look_strategy == 'sensual':
            bonus -= 0.03
    else:
        if category in CHEEK_CATEGORIES and dominant_color in {'peach', 'coral', 'rose', 'pink'}:
            bonus += 0.04
        if category in LIP_CATEGORIES and dominant_color in {'nude', 'rose', 'berry', 'red'}:
            bonus += 0.04

    if look_strategy == 'soft_luxury' and category in BASE_CATEGORIES and dominant_finish in {'natural', 'radiant', 'satin'}:
        bonus += 0.05
    if look_strategy == 'fresh' and category in {ProductCategory.blush, ProductCategory.lip_tint, ProductCategory.skin_tint}:
        bonus += 0.05
    return bonus


def build_cta_from_harmony(profile: dict[str, object]) -> str:
    focus = set(profile.get('focus_features') or [])
    strategy = profile.get('look_strategy')
    if strategy == 'sensual' and 'lips' in focus:
        return 'Если хочешь, я дожму это ещё сильнее через губы и более собранные глаза.'
    if strategy == 'soft_luxury':
        return 'Если хочешь, я ещё сильнее соберу это в дорогой и очень clean luxury образ.'
    if strategy == 'fresh':
        return 'Если хочешь, я сделаю это ещё свежее и легче, но без потери эффекта.'
    if 'eyes' in focus:
        return 'Если хочешь, я усилю глаза и оставлю губы более спокойными, чтобы образ не спорил сам с собой.'
    return 'Если хочешь, я ещё подкручу баланс образа — например сильнее в губы, глаза или более мягкий дневной вайб.'


def attach_look_profile(session: SessionState, recommendations: list[RecommendationItem]) -> None:
    session.dialog_context.look_profile = infer_harmony_profile(session.current_plan, recommendations)
