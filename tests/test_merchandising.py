from app.merchandising import bundle_story, order_for_conversion
from app.models import ProductCategory, ProductDomain, PriceSegment, RecommendationItem, RecommendationPlan, UserContext


def item(category: ProductCategory, score: float = 0.7):
    return RecommendationItem(
        sku=category.value,
        title=category.value,
        brand='x',
        category=category,
        domain=ProductDomain.makeup,
        price_segment=PriceSegment.mid,
        price_value=1000,
        why='ok',
        vector_score=0.5,
        rule_score=0.5,
        final_score=score,
    )


def test_order_for_conversion_prefers_hero_category() -> None:
    items = [item(ProductCategory.blush, 0.9), item(ProductCategory.foundation, 0.8), item(ProductCategory.mascara, 0.85)]
    ordered = order_for_conversion(items, RecommendationPlan(required_categories=[x.category for x in items]), UserContext())
    assert ordered[0].category == ProductCategory.foundation


def test_bundle_story_returns_hero_and_support() -> None:
    hero, support = bundle_story([item(ProductCategory.foundation), item(ProductCategory.concealer), item(ProductCategory.blush)])
    assert hero.category == ProductCategory.foundation
    assert len(support) == 2
