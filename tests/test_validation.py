from app.models import ProductCategory, ProductDomain, PriceSegment, RecommendationItem
from app.validation import validate_response_grounding


def test_validate_response_grounding_accepts_known_product() -> None:
    item = RecommendationItem(
        sku='1', title='Air Touch Concealer LIGHT_NEUTRAL', brand='Shade Atelier', category=ProductCategory.concealer,
        domain=ProductDomain.makeup, price_segment=PriceSegment.mid, price_value=1000, why='ok', vector_score=0.1, rule_score=0.2, final_score=0.3,
    )
    assert validate_response_grounding('Air Touch Concealer here works very well', [item]) is True


def test_validate_response_grounding_rejects_unknown_text() -> None:
    item = RecommendationItem(
        sku='1', title='Air Touch Concealer LIGHT_NEUTRAL', brand='Shade Atelier', category=ProductCategory.concealer,
        domain=ProductDomain.makeup, price_segment=PriceSegment.mid, price_value=1000, why='ok', vector_score=0.1, rule_score=0.2, final_score=0.3,
    )
    assert validate_response_grounding('Kiehls serum is better here', [item]) is False
