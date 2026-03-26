from app.models import DialogIntent, IntentAction, IntentDomain, ProductCategory, ProductDomain, PriceSegment, RecommendationItem, RecommendationPlan, SessionState, SkinProfile, SkinType, PhotoAnalysisResult, RecommendationPlan, UserContext
from app.response_service import compose_followup_response


def make_item(category: ProductCategory, title: str) -> RecommendationItem:
    return RecommendationItem(
        sku=title,
        title=title,
        brand='Brand',
        category=category,
        domain=ProductDomain.makeup,
        price_segment=PriceSegment.mid,
        price_value=1000,
        why='ok',
        vector_score=0.5,
        rule_score=0.6,
        final_score=0.7,
    )


def test_followup_response_stays_grounded_to_visible_items() -> None:
    session = SessionState(
        session_id='1',
        photo_analysis=PhotoAnalysisResult(),
        skin_profile=SkinProfile(skin_type=SkinType.normal, primary_concerns=[], confidence_overall=0.8),
        current_plan=RecommendationPlan(required_categories=[ProductCategory.foundation, ProductCategory.concealer]),
        user_preferences=UserContext(),
    )
    recs = [make_item(ProductCategory.foundation, 'Perfect Match Serum Foundation LIGHT_NEUTRAL'), make_item(ProductCategory.concealer, 'Air Touch Concealer LIGHT_NEUTRAL')]
    text = compose_followup_response(session, DialogIntent(intent='general_advice', action=IntentAction.recommend, domain=IntentDomain.makeup), recs, 'сделай это лучше')
    assert 'Perfect Match' in text
    assert 'Air Touch' in text
    assert 'Kiehl' not in text
