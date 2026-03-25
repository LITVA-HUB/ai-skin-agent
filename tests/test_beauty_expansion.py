from app.catalog import load_catalog
from app.intent_service import detect_categories, detect_domain, heuristic_intent
from app.models import IntentDomain, PriceSegment, ProductCategory, RoutineSize, UserContext
from app.plan_service import build_plan
from app.profile_service import build_skin_profile
from app.retrieval import retrieve_products
from app.models import PhotoAnalysisResult, PhotoSignals, SkinTone, Undertone


def profile():
    return build_skin_profile(
        PhotoAnalysisResult(
            signals=PhotoSignals(oiliness=0.44, dryness=0.3, redness=0.35, breakouts=0.2, tone_evenness=0.7, sensitivity_signs=0.2),
            complexion={
                'skin_tone': SkinTone.light_medium,
                'undertone': Undertone.neutral,
                'under_eye_darkness': 0.3,
                'visible_shine': 0.35,
                'texture_visibility': 0.2,
            },
            confidence=0.8,
            source='mock',
        ),
        goal='хочу дневной макияж с румянами, тушью и нюдовой помадой',
    )


def test_catalog_contains_new_beauty_categories() -> None:
    categories = {item.category for item in load_catalog()}
    assert ProductCategory.lipstick in categories
    assert ProductCategory.mascara in categories
    assert ProductCategory.blush in categories
    assert ProductCategory.primer in categories


def test_detect_categories_for_lips_and_eyes() -> None:
    categories = detect_categories('подбери помаду и тушь для дневного макияжа')
    assert ProductCategory.lipstick in categories
    assert ProductCategory.mascara in categories


def test_detect_domain_for_makeup_expansion() -> None:
    assert detect_domain('хочу помаду, румяна и тушь') == IntentDomain.makeup


def test_heuristic_intent_for_full_look() -> None:
    intent = heuristic_intent('собери полный образ на вечер')
    assert intent.intent == 'build_full_look'


def test_plan_builds_beauty_categories_for_makeup_goal() -> None:
    p = profile()
    context = UserContext(budget_segment=PriceSegment.mid, routine_size=RoutineSize.standard, goal='хочу дневной макияж с румянами, тушью и нюдовой помадой')
    plan = build_plan(p, context)
    categories = {item for item in plan.required_categories}
    assert ProductCategory.blush in categories
    assert ProductCategory.mascara in categories
    assert ProductCategory.lipstick in categories or ProductCategory.lip_tint in categories
    assert plan.look_strategy in {'fresh', 'balanced'}


def test_plan_sets_sensual_focus_for_sexy_request() -> None:
    p = profile()
    context = UserContext(budget_segment=PriceSegment.mid, routine_size=RoutineSize.standard, goal='хочу sexy образ с акцентом на губы')
    plan = build_plan(p, context)
    assert plan.look_strategy == 'sensual'
    assert plan.accent_balance == 'feature_focus'
    assert 'lips' in plan.focus_features


def test_retrieval_returns_lip_products_for_matching_request() -> None:
    p = profile()
    context = UserContext(budget_segment=PriceSegment.mid, routine_size=RoutineSize.standard, goal='хочу нюдовую помаду на каждый день')
    plan = build_plan(p, context)
    recs = retrieve_products(p, plan, context)
    cats = {item.category for item in recs}
    assert ProductCategory.lipstick in cats or ProductCategory.lip_tint in cats or ProductCategory.lip_gloss in cats
