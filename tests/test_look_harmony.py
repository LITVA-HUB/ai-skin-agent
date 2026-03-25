from app.look_harmony import build_cta_from_harmony, harmony_bonus, infer_harmony_profile
from app.models import ProductCategory, RecommendationItem, ProductDomain, PriceSegment, RecommendationPlan


def test_build_cta_from_harmony_prefers_sensual_lips() -> None:
    cta = build_cta_from_harmony({'look_strategy': 'sensual', 'focus_features': ['lips']})
    assert 'губы' in cta


def test_harmony_bonus_rewards_matching_color() -> None:
    class Product:
        color_families = ['rose']
        finishes = ['satin']
    bonus = harmony_bonus(ProductCategory.lipstick, Product(), {'dominant_color': 'rose', 'dominant_finish': 'satin', 'focus_features': ['lips'], 'look_strategy': 'sensual', 'accent_balance': 'feature_focus'})
    assert bonus > 0.1


def test_infer_harmony_profile_keeps_plan_focus() -> None:
    plan = RecommendationPlan(required_categories=[ProductCategory.lipstick], focus_features=['lips'], look_strategy='sensual', accent_balance='feature_focus')
    item = RecommendationItem(sku='LP-MID-01', title='Velvet Muse Lipstick ROSE_NUDE', brand='Atelier Rouge', category=ProductCategory.lipstick, domain=ProductDomain.makeup, price_segment=PriceSegment.mid, price_value=1490, why='ok', vector_score=0.1, rule_score=0.2, final_score=0.3)
    profile = infer_harmony_profile(plan, [item])
    assert profile['look_strategy'] == 'sensual'
    assert 'lips' in profile['focus_features']
