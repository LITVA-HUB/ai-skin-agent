from app.merchandising import order_for_conversion
from app.models import ProductCategory, ProductDomain, PriceSegment, RecommendationItem, RecommendationPlan, UserContext


def item(category: ProductCategory, score: float = 0.8):
    return RecommendationItem(
        sku=category.value,
        title=category.value,
        brand='Brand',
        category=category,
        domain=ProductDomain.makeup if category not in {ProductCategory.cleanser, ProductCategory.serum, ProductCategory.moisturizer, ProductCategory.spf} else ProductDomain.skincare,
        price_segment=PriceSegment.mid,
        price_value=1200,
        why='ok',
        vector_score=0.6,
        rule_score=0.7,
        final_score=score,
    )


def test_sensual_ranking_prefers_makeup_over_skincare() -> None:
    items = [item(ProductCategory.cleanser), item(ProductCategory.lipstick), item(ProductCategory.mascara)]
    plan = RecommendationPlan(required_categories=[x.category for x in items], look_strategy='sensual')
    ordered = order_for_conversion(items, plan, UserContext())
    assert ordered[0].category in {ProductCategory.lipstick, ProductCategory.mascara}
