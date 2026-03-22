from app.catalog import load_catalog
from app.logic import build_plan, build_skin_profile
from app.models import DialogIntent, PhotoAnalysisResult, PhotoSignals, PriceSegment, RoutineSize, SessionState, SkinProfile, SkinTone, Undertone, UserContext
from app.retrieval import retrieve_products, vectorize_text


def _profile() -> SkinProfile:
    return build_skin_profile(
        PhotoAnalysisResult(
            signals=PhotoSignals(
                oiliness=0.64,
                dryness=0.28,
                redness=0.52,
                breakouts=0.71,
                tone_evenness=0.4,
                sensitivity_signs=0.45,
            ),
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


def test_catalog_contains_skincare_and_makeup() -> None:
    catalog = load_catalog()
    assert len(catalog) >= 70
    categories = {item.category for item in catalog}
    assert {'cleanser', 'serum', 'moisturizer', 'spf', 'foundation', 'skin_tint', 'concealer', 'powder'}.issubset(categories)



def test_vectorization_is_deterministic() -> None:
    left = vectorize_text('radiant light coverage foundation for neutral undertone')
    right = vectorize_text('radiant light coverage foundation for neutral undertone')
    other = vectorize_text('oily skin clarifying blemish serum')
    assert left == right
    assert left != other



def test_hybrid_retrieval_returns_skincare_and_makeup_items() -> None:
    profile = _profile()
    context = UserContext(budget_segment=PriceSegment.mid, routine_size=RoutineSize.standard, goal='хочу и уход, и тональник с лёгким сияющим покрытием')
    plan = build_plan(profile, context)
    recs = retrieve_products(profile, plan, context)
    assert {'cleanser', 'serum', 'moisturizer', 'spf', 'foundation', 'concealer', 'powder'}.issubset({item.category for item in recs})
    foundation = next(item for item in recs if item.category == 'foundation')
    assert foundation.vector_score > 0
    assert foundation.rule_score > 0
    assert foundation.final_score > 0



def test_makeup_retrieval_respects_tone_undertone_and_finish() -> None:
    profile = _profile()
    context = UserContext(budget_segment=PriceSegment.mid, routine_size=RoutineSize.minimal, goal='подбери тональник под светлый нейтральный подтон, хочу сияющий финиш и лёгкое покрытие')
    plan = build_plan(profile, context)
    recs = retrieve_products(profile, plan, context)
    foundation = next(item for item in recs if item.category in {'foundation', 'skin_tint'})
    product = next(item for item in load_catalog() if item.sku == foundation.sku)
    assert 'light' in product.tones
    assert 'neutral' in product.undertones
    assert set(product.finishes) & {'radiant', 'natural'}



def test_cheaper_alternative_is_actually_cheaper_for_target_category() -> None:
    profile = _profile()
    context = UserContext(budget_segment=PriceSegment.premium, routine_size=RoutineSize.standard, goal='нужен консилер под глаза')
    plan = build_plan(profile, context)
    initial = retrieve_products(profile, plan, context)
    selection = {item.category: item.sku for item in initial}
    concealer_before = next(item for item in initial if item.category == 'concealer')

    session = SessionState(
        session_id='s1',
        photo_analysis=PhotoAnalysisResult(signals=PhotoSignals(), confidence=0.5, source='mock'),
        skin_profile=profile,
        current_plan=plan,
        user_preferences=context,
        shown_products=[item.sku for item in initial],
        accepted_products=[item.sku for item in initial],
        dialog_context={'current_recommendations': selection},
    )
    intent = DialogIntent(intent='cheaper_alternative', target_category='concealer', constraints_update={'budget_segment': 'budget'}, confidence=0.9)
    cheaper_context = context.model_copy(update={'budget_segment': PriceSegment.budget})
    updated = retrieve_products(profile, build_plan(profile, cheaper_context), cheaper_context, session=session, intent=intent)
    concealer_after = next(item for item in updated if item.category == 'concealer')

    assert concealer_after.sku != concealer_before.sku
    assert concealer_after.price_value < concealer_before.price_value



def test_replace_product_keeps_other_categories_stable() -> None:
    profile = _profile()
    context = UserContext(budget_segment=PriceSegment.mid, routine_size=RoutineSize.standard, goal='хочу уход и консилер под глаза')
    plan = build_plan(profile, context)
    initial = retrieve_products(profile, plan, context)
    selection = {item.category: item.sku for item in initial}
    concealer_before = selection['concealer']
    cleanser_before = selection['cleanser']

    session = SessionState(
        session_id='s2',
        photo_analysis=PhotoAnalysisResult(signals=PhotoSignals(), confidence=0.5, source='mock'),
        skin_profile=profile,
        current_plan=plan,
        user_preferences=context,
        shown_products=[item.sku for item in initial],
        rejected_products=[concealer_before],
        accepted_products=[item.sku for item in initial],
        dialog_context={'current_recommendations': selection},
    )
    intent = DialogIntent(intent='replace_product', target_category='concealer', constraints_update={'replace': True}, confidence=0.9)
    updated = retrieve_products(profile, plan, context, session=session, intent=intent)
    updated_map = {item.category: item.sku for item in updated}

    assert updated_map['concealer'] != concealer_before
    assert updated_map['cleanser'] == cleanser_before
