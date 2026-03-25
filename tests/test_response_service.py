from app.models import MakeupProfile, MakeupStyle, ProductCategory, RecommendationItem, ProductDomain, PriceSegment, SkinProfile, SkinType
from app.response_service import _style_mode, pretty_product_title, sanitize_agent_text


def test_pretty_product_title_humanizes_shade_codes() -> None:
    title = pretty_product_title('Air Touch Concealer LIGHT_WARM')
    assert 'LIGHT_WARM' not in title
    assert 'светлый' in title.lower()


def test_sanitize_agent_text_removes_greeting_and_markdown() -> None:
    text = sanitize_agent_text('Привет! **Тест**')
    assert '**' not in text
    assert 'Привет' not in text


def test_recommendation_item_uses_typed_category() -> None:
    item = RecommendationItem(
        sku='x',
        title='y',
        brand='z',
        category=ProductCategory.concealer,
        domain=ProductDomain.makeup,
        price_segment=PriceSegment.mid,
        price_value=1000,
        why='ok',
        vector_score=0.1,
        rule_score=0.2,
        final_score=0.3,
    )
    assert item.category == ProductCategory.concealer


def test_style_mode_detects_soft_luxury() -> None:
    profile = SkinProfile(skin_type=SkinType.normal, primary_concerns=[], makeup_profile=MakeupProfile(preferred_styles=[MakeupStyle.soft_luxury]), confidence_overall=0.8)
    assert _style_mode(profile) == 'soft_luxury'
