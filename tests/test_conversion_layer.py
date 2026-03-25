from app.merchandising import one_best_pick, vibe_alternative, selling_frame
from app.models import ProductCategory, ProductDomain, PriceSegment, RecommendationItem, RecommendationPlan, UserContext


def item(category: ProductCategory):
    return RecommendationItem(
        sku=category.value,
        title=category.value,
        brand='Brand',
        category=category,
        domain=ProductDomain.makeup,
        price_segment=PriceSegment.mid,
        price_value=1200,
        why='ok',
        vector_score=0.6,
        rule_score=0.7,
        final_score=0.8,
    )


def test_one_best_pick_returns_first() -> None:
    items = [item(ProductCategory.foundation), item(ProductCategory.blush)]
    assert one_best_pick(items).category == ProductCategory.foundation


def test_vibe_alternative_returns_second() -> None:
    items = [item(ProductCategory.foundation), item(ProductCategory.blush)]
    assert vibe_alternative(items).category == ProductCategory.blush


def test_selling_frame_contains_fast_effect_language() -> None:
    lines = selling_frame(
        [item(ProductCategory.foundation), item(ProductCategory.concealer), item(ProductCategory.blush)],
        RecommendationPlan(required_categories=[ProductCategory.foundation], look_strategy='soft_luxury'),
        UserContext(),
    )
    assert any('вау-эффекта' in line or 'Самый лёгкий вход' in line for line in lines)
