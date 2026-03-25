from app.models import PhotoAnalysisResult, PhotoSignals, PriceSegment, RoutineSize, SkinTone, Undertone, UserContext
from app.plan_service import build_plan
from app.profile_service import build_skin_profile


def make_profile():
    return build_skin_profile(
        PhotoAnalysisResult(
            signals=PhotoSignals(oiliness=0.64, dryness=0.28, redness=0.52, breakouts=0.71, tone_evenness=0.4, sensitivity_signs=0.45),
            complexion={
                'skin_tone': SkinTone.light,
                'undertone': Undertone.neutral,
                'under_eye_darkness': 0.62,
                'visible_shine': 0.58,
                'texture_visibility': 0.41,
            },
            confidence=0.77,
            source='mock',
        ),
        goal='подбери тональник под мой тон кожи, хочу лёгкое покрытие и сияющий финиш',
    )


def test_build_plan_for_hybrid_goal_contains_makeup_and_skincare() -> None:
    profile = make_profile()
    context = UserContext(budget_segment=PriceSegment.mid, routine_size=RoutineSize.standard, goal='хочу уход и skin tint')
    plan = build_plan(profile, context)
    categories = {item.value for item in plan.required_categories}
    assert 'cleanser' in categories
    assert 'skin_tint' in categories or 'foundation' in categories


def test_build_plan_for_minimal_routine_reduces_makeup_scope() -> None:
    profile = make_profile()
    context = UserContext(budget_segment=PriceSegment.mid, routine_size=RoutineSize.minimal, goal='хочу уход и консилер')
    plan = build_plan(profile, context)
    categories = [item.value for item in plan.required_categories]
    assert 'concealer' in categories
