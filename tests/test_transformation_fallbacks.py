from app.look_rules import fallback_categories_for
from app.models import ProductCategory


def test_fallback_categories_for_lipstick() -> None:
    fallback = fallback_categories_for(ProductCategory.lipstick)
    assert ProductCategory.lip_tint in fallback


def test_fallback_categories_for_foundation() -> None:
    fallback = fallback_categories_for(ProductCategory.foundation)
    assert ProductCategory.skin_tint in fallback
