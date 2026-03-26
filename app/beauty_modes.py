from __future__ import annotations

from .models import ProductCategory

MODE_BUNDLES = {
    'fresh_makeup': [
        ProductCategory.skin_tint,
        ProductCategory.blush,
        ProductCategory.brow_gel,
        ProductCategory.lip_tint,
        ProductCategory.mascara,
    ],
    'evening_makeup': [
        ProductCategory.foundation,
        ProductCategory.concealer,
        ProductCategory.blush,
        ProductCategory.mascara,
        ProductCategory.eyeliner,
        ProductCategory.lipstick,
    ],
    'lips_focus': [
        ProductCategory.lipstick,
        ProductCategory.lip_liner,
        ProductCategory.blush,
        ProductCategory.mascara,
    ],
    'eyes_focus': [
        ProductCategory.mascara,
        ProductCategory.eyeliner,
        ProductCategory.eyeshadow_palette,
        ProductCategory.lip_tint,
        ProductCategory.concealer,
    ],
    'soft_luxury': [
        ProductCategory.primer,
        ProductCategory.foundation,
        ProductCategory.blush,
        ProductCategory.highlighter,
        ProductCategory.lip_tint,
    ],
    'skincare_core': [
        ProductCategory.cleanser,
        ProductCategory.serum,
        ProductCategory.moisturizer,
        ProductCategory.spf,
    ],
    'hybrid_core': [
        ProductCategory.concealer,
        ProductCategory.cleanser,
        ProductCategory.serum,
        ProductCategory.moisturizer,
        ProductCategory.spf,
    ],
}


def detect_mode(goal_text: str) -> str:
    text = goal_text.lower()
    if any(token in text for token in ['уход', 'skincare', 'skin care']) and any(token in text for token in ['консил', 'тон', 'макияж', 'look', 'образ']):
        return 'hybrid_core'
    if any(token in text for token in ['акцент на губы', 'губ', 'lip']) and not any(token in text for token in ['глаз', 'eye']):
        return 'lips_focus'
    if any(token in text for token in ['акцент на глаза', 'глаз', 'eye', 'ресниц', 'бров']):
        return 'eyes_focus'
    if any(token in text for token in ['quiet luxury', 'soft luxury', 'тихая роскошь', 'дорого']):
        return 'soft_luxury'
    if any(token in text for token in ['вечер', 'glam', 'party', 'evening', 'свидание', 'на выход']):
        return 'evening_makeup'
    if any(token in text for token in ['дневн', 'fresh', 'clean girl', 'quick', 'office', 'свеж']) or 'макияж' in text:
        return 'fresh_makeup'
    if any(token in text for token in ['уход', 'skincare', 'skin care']):
        return 'skincare_core'
    return 'fresh_makeup'


def mode_categories(mode: str) -> list[ProductCategory]:
    return list(MODE_BUNDLES.get(mode, MODE_BUNDLES['fresh_makeup']))
