from __future__ import annotations

import uuid

from .dialog_service import answer_from_conversation_history, append_conversation_turn, is_memory_question
from .gemini_client import GeminiClient, is_probably_base64_image
from .intent_service import heuristic_intent
from .decision_pipeline import build_bundle_recommendations
from .look_harmony import attach_look_profile
from .look_transforms import apply_look_transform, transformation_label
from .merchandising import order_for_conversion
from .observability import log_event
from .validation import validate_response_grounding
from .models import (
    AnalyzePhotoRequest,
    AnalyzePhotoResponse,
    BudgetDirection,
    DialogContextState,
    DialogIntent,
    IntentAction,
    IntentDomain,
    PriceSegment,
    SessionMessageResponse,
    SessionState,
)
from .plan_service import build_plan
from .profile_service import build_skin_profile, merge_context_preferences, mock_photo_analysis
from .response_service import build_reply_prompt, compose_followup_response, compose_initial_response, sanitize_agent_text
from .retrieval import retrieve_products
from .store import SessionStore


def session_summary(session: SessionState) -> str:
    return (
        f"skin_type={session.skin_profile.skin_type.value}; concerns={','.join(item.value for item in session.skin_profile.primary_concerns)}; "
        f"tone={session.skin_profile.complexion.skin_tone.value if session.skin_profile.complexion.skin_tone else ''}; "
        f"undertone={session.skin_profile.complexion.undertone.value if session.skin_profile.complexion.undertone else ''}; "
        f"finish={','.join(item.value for item in session.user_preferences.preferred_finish)}; "
        f"coverage={','.join(item.value for item in session.user_preferences.preferred_coverage)}; "
        f"brands={','.join(session.user_preferences.preferred_brands)}; excluded={','.join(session.user_preferences.excluded_ingredients)}; "
        f"budget={session.user_preferences.budget_segment.value}; budget_direction={session.user_preferences.budget_direction.value}; "
        f"routine={session.user_preferences.routine_size.value}; accepted={','.join(session.accepted_products)}; rejected={','.join(session.rejected_products)}"
    )


def merge_update_dicts(primary: dict[str, object] | None, secondary: dict[str, object] | None) -> dict[str, object]:
    merged: dict[str, object] = {}
    for source in [secondary or {}, primary or {}]:
        for key, value in source.items():
            if isinstance(value, list) and isinstance(merged.get(key), list):
                merged[key] = list(dict.fromkeys([*merged[key], *value]))
            else:
                merged[key] = value
    return merged


def merge_intents(primary: DialogIntent | None, fallback: DialogIntent | None) -> DialogIntent:
    if primary is None:
        return fallback or DialogIntent(intent="general_advice")
    if fallback is None:
        return primary
    base, other = (primary, fallback) if primary.confidence >= 0.55 else (fallback, primary)
    merged = base.model_copy(deep=True)
    if not merged.target_category and other.target_category:
        merged.target_category = other.target_category
    if not merged.target_categories and other.target_categories:
        merged.target_categories = other.target_categories
    if not merged.target_category and merged.target_categories:
        merged.target_category = merged.target_categories[0]
    if not merged.target_product and other.target_product:
        merged.target_product = other.target_product
    if not merged.target_products and other.target_products:
        merged.target_products = other.target_products
    merged.preference_updates = merge_update_dicts(base.preference_updates, other.preference_updates)
    merged.constraints_update = merge_update_dicts(base.constraints_update, other.constraints_update)
    if merged.domain == IntentDomain.skincare and other.domain == IntentDomain.hybrid:
        merged.domain = other.domain
    if merged.domain == IntentDomain.skincare and other.domain == IntentDomain.makeup and other.target_categories:
        merged.domain = other.domain
    return merged


def needs_recommendation_refresh(session: SessionState, intent: DialogIntent) -> bool:
    if intent.action in {IntentAction.compare, IntentAction.explain}:
        non_refresh = {"feedback", "accepted_products", "rejected_products"}
        extra_updates = [key for key in intent.constraints_update if key not in non_refresh]
        if intent.preference_updates or extra_updates:
            return True
        current_map = session.dialog_context.current_recommendations or {}
        if intent.target_categories and any(cat not in current_map for cat in intent.target_categories):
            return True
        return False
    return True


def recommendation_items_from_current(session: SessionState, target_categories=None):
    selection = session.dialog_context.current_recommendations
    categories = target_categories or session.current_plan.required_categories
    catalog = {product.sku: product for product in __import__('app.catalog', fromlist=['load_catalog']).load_catalog()}
    items = []
    for category in categories:
        sku = selection.get(category)
        if not sku:
            continue
        product = catalog.get(sku)
        if not product:
            continue
        from .models import RecommendationItem
        items.append(RecommendationItem(
            sku=product.sku,
            title=product.title,
            brand=product.brand,
            category=product.category,
            domain=product.domain,
            price_segment=product.price_segment,
            price_value=product.price_value,
            why="текущий выбор",
            vector_score=0.0,
            rule_score=0.0,
            final_score=0.0,
        ))
    return items


def apply_intent(session: SessionState, intent: DialogIntent) -> SessionState:
    updated = session.model_copy(deep=True)
    prefs = updated.user_preferences
    profile = updated.skin_profile
    pref_updates = intent.preference_updates or {}
    constraint_updates = intent.constraints_update or {}
    merged = {**pref_updates, **constraint_updates}

    explicit_budget = False
    if constraint_updates.get("budget_segment"):
        prefs.budget_segment = PriceSegment(constraint_updates["budget_segment"])
        explicit_budget = True
    if merged.get("budget_direction"):
        prefs.budget_direction = BudgetDirection(merged["budget_direction"])
    if merged.get("routine_size"):
        from .models import RoutineSize
        prefs.routine_size = RoutineSize(merged["routine_size"])
    if merged.get("preferred_brands"):
        prefs.preferred_brands = list(dict.fromkeys([*prefs.preferred_brands, *merged["preferred_brands"]]))
    if merged.get("excluded_ingredients"):
        prefs.excluded_ingredients = list(dict.fromkeys([*prefs.excluded_ingredients, *merged["excluded_ingredients"]]))
    if constraint_updates.get("goal") and intent.action not in {IntentAction.compare, IntentAction.explain}:
        prefs.goal = str(constraint_updates["goal"])
    if merged.get("preferred_finish"):
        from .models import FinishType
        prefs.preferred_finish = [FinishType(item) for item in merged["preferred_finish"]]
        profile.complexion.preferred_finish = [FinishType(item) for item in merged["preferred_finish"]]
    if merged.get("preferred_coverage"):
        from .models import CoverageLevel
        prefs.preferred_coverage = [CoverageLevel(item) for item in merged["preferred_coverage"]]
        profile.complexion.preferred_coverage = [CoverageLevel(item) for item in merged["preferred_coverage"]]
    if merged.get("needs_under_eye_concealer"):
        profile.complexion.needs_under_eye_concealer = True
    if merged.get("skin_type"):
        from .models import SkinType
        profile.skin_type = SkinType(merged["skin_type"])
    if merged.get("skin_tone"):
        from .models import SkinTone
        profile.complexion.skin_tone = SkinTone(merged["skin_tone"])
    if merged.get("undertone"):
        from .models import Undertone
        profile.complexion.undertone = Undertone(merged["undertone"])
    if constraint_updates.get("look_transform"):
        prefs = apply_look_transform(prefs, constraint_updates["look_transform"])
        updated.user_preferences = prefs
        updated.dialog_context.transformation_history.append(transformation_label(constraint_updates["look_transform"]))

    if not explicit_budget and prefs.budget_direction in {BudgetDirection.cheaper, BudgetDirection.premium}:
        if prefs.budget_direction == BudgetDirection.cheaper:
            if prefs.budget_segment == PriceSegment.premium:
                prefs.budget_segment = PriceSegment.mid
            elif prefs.budget_segment == PriceSegment.mid:
                prefs.budget_segment = PriceSegment.budget
        if prefs.budget_direction == BudgetDirection.premium:
            if prefs.budget_segment == PriceSegment.budget:
                prefs.budget_segment = PriceSegment.mid
            elif prefs.budget_segment == PriceSegment.mid:
                prefs.budget_segment = PriceSegment.premium

    current = updated.dialog_context.current_recommendations or {}
    target_for_feedback = intent.target_category or updated.dialog_context.last_target_category
    if constraint_updates.get("feedback") and target_for_feedback:
        current_sku = current.get(target_for_feedback)
        if current_sku:
            if constraint_updates["feedback"] == "reject" and current_sku not in updated.rejected_products:
                updated.rejected_products.append(current_sku)
            if constraint_updates["feedback"] == "accept" and current_sku not in updated.accepted_products:
                updated.accepted_products.append(current_sku)
    if constraint_updates.get("rejected_products"):
        updated.rejected_products = list(dict.fromkeys([*updated.rejected_products, *constraint_updates["rejected_products"]]))
    if constraint_updates.get("accepted_products"):
        updated.accepted_products = list(dict.fromkeys([*updated.accepted_products, *constraint_updates["accepted_products"]]))

    if intent.intent in {"replace_product", "cheaper_alternative"} and intent.target_category:
        current_sku = current.get(intent.target_category)
        if current_sku and current_sku not in updated.rejected_products:
            updated.rejected_products.append(current_sku)

    updated.accepted_products = [sku for sku in updated.accepted_products if sku not in updated.rejected_products]
    prefs.rejected_products = list(dict.fromkeys(updated.rejected_products))
    prefs.accepted_products = list(dict.fromkeys(updated.accepted_products))

    updated.current_plan = build_plan(profile, prefs, intent)
    updated.dialog_context.last_intent = intent.intent
    updated.dialog_context.last_action = intent.action
    updated.dialog_context.last_domain = intent.domain
    updated.dialog_context.last_target_category = intent.target_category
    updated.dialog_context.last_target_categories = list(intent.target_categories)
    updated.dialog_context.last_target_products = list(intent.target_products)
    updated.dialog_context.active_domains = [IntentDomain(domain.value) for domain in updated.current_plan.product_domains]
    return updated


async def analyze_photo(request: AnalyzePhotoRequest, store: SessionStore, gemini: GeminiClient) -> AnalyzePhotoResponse:
    analysis = None
    if request.photo_b64 and is_probably_base64_image(request.photo_b64):
        analysis = await gemini.analyze_photo(request.photo_b64)
    if analysis is None:
        analysis = mock_photo_analysis(request)

    profile = build_skin_profile(analysis, request.user_context.goal)
    context = merge_context_preferences(request.user_context, profile)
    plan = build_plan(profile, context)
    recommendations, trace = build_bundle_recommendations(profile, plan, context)
    recommendations = order_for_conversion(recommendations, plan, context)
    context.accepted_products = [item.sku for item in recommendations]
    context.rejected_products = list(dict.fromkeys(context.rejected_products))
    answer_text = compose_initial_response(profile, recommendations, plan)
    session = SessionState(
        session_id=str(uuid.uuid4()),
        photo_analysis=analysis,
        skin_profile=profile,
        current_plan=plan,
        user_preferences=context,
        shown_products=[item.sku for item in recommendations],
        accepted_products=[item.sku for item in recommendations],
        dialog_context=DialogContextState(
            current_recommendations={item.category: item.sku for item in recommendations},
            active_domains=[IntentDomain(domain.value) for domain in plan.product_domains],
            decision_trace=trace.model_dump(mode='json'),
        ),
        conversation_history=[],
    )
    attach_look_profile(session, recommendations)
    append_conversation_turn(session, "assistant", answer_text)
    store.save(session)
    log_event(
        'analyze_photo',
        session_id=session.session_id,
        recommendation_count=len(recommendations),
        mode=trace.mode,
        requested_categories=[c.value for c in trace.requested_categories],
        resolved_categories=[item.category.value for item in recommendations],
    )
    return AnalyzePhotoResponse(
        session_id=session.session_id,
        photo_analysis_result=analysis,
        skin_profile=profile,
        recommendation_plan=plan,
        recommendations=recommendations,
        answer_text=answer_text,
    )


async def handle_message(message: str, store: SessionStore, session_id: str, gemini: GeminiClient) -> SessionMessageResponse:
    session = store.get(session_id)
    if not session:
        raise KeyError(session_id)

    if is_memory_question(message):
        updated = session.model_copy(deep=True)
        append_conversation_turn(updated, "user", message)
        answer_text = answer_from_conversation_history(updated, message)
        append_conversation_turn(updated, "assistant", answer_text)
        store.save(updated)
        return SessionMessageResponse(
            intent=DialogIntent(intent="conversation_memory", action=IntentAction.explain, confidence=1.0),
            updated_session_state=updated,
            recommendations=recommendation_items_from_current(updated),
            answer_text=answer_text,
        )

    model_intent = await gemini.parse_intent(message, session_summary(session))
    heuristic = heuristic_intent(message, session=session)
    intent = merge_intents(model_intent, heuristic)
    updated = apply_intent(session, intent)
    append_conversation_turn(updated, "user", message)

    if needs_recommendation_refresh(updated, intent):
        recommendations, trace = build_bundle_recommendations(updated.skin_profile, updated.current_plan, updated.user_preferences, session=updated, intent=intent)
        recommendations = order_for_conversion(
            recommendations,
            updated.current_plan,
            updated.user_preferences,
        )
        new_skus = [item.sku for item in recommendations]
        updated.shown_products = sorted(set(updated.shown_products + new_skus))
        updated.accepted_products = list(dict.fromkeys([*updated.accepted_products, *new_skus]))
        updated.accepted_products = [sku for sku in updated.accepted_products if sku not in updated.rejected_products]
        updated.user_preferences.accepted_products = list(updated.accepted_products)
        updated.user_preferences.rejected_products = list(updated.rejected_products)
        updated.dialog_context.current_recommendations = {item.category: item.sku for item in recommendations}
        updated.dialog_context.decision_trace = trace.model_dump(mode='json')
        attach_look_profile(updated, recommendations)
    else:
        target_categories = intent.target_categories or ([intent.target_category] if intent.target_category else None)
        recommendations = order_for_conversion(recommendation_items_from_current(updated, target_categories), updated.current_plan, updated.user_preferences)
        updated.dialog_context.decision_trace = {
            'mode': 'current_selection',
            'requested_categories': [cat.value for cat in (target_categories or updated.current_plan.required_categories)],
            'resolved_items': [],
        }
        updated.user_preferences.accepted_products = list(updated.accepted_products)
        updated.user_preferences.rejected_products = list(updated.rejected_products)
        attach_look_profile(updated, recommendations)

    use_llm_for_reply = intent.action in {IntentAction.compare, IntentAction.explain} and len(recommendations) <= 2
    if use_llm_for_reply:
        reply = await gemini.generate_agent_reply(build_reply_prompt(updated, intent, recommendations, message))
        cleaned_reply = sanitize_agent_text(reply) if reply else ''
        reply_looks_safe = validate_response_grounding(cleaned_reply, recommendations)
        if reply_looks_safe and not __import__('app.config', fromlist=['settings']).settings.strict_fail_safe:
            answer_text = cleaned_reply
        elif reply_looks_safe and len(cleaned_reply) < 700:
            answer_text = cleaned_reply
        else:
            answer_text = compose_followup_response(updated, intent, recommendations, message)
    else:
        answer_text = compose_followup_response(updated, intent, recommendations, message)
    append_conversation_turn(updated, "assistant", answer_text)
    store.save(updated)
    log_event(
        'handle_message',
        session_id=updated.session_id,
        intent=intent.intent,
        action=intent.action.value,
        recommendation_count=len(recommendations),
        used_llm=use_llm_for_reply,
        decision_mode=updated.dialog_context.decision_trace.get('mode') if updated.dialog_context.decision_trace else None,
        resolved_categories=[item.category.value for item in recommendations],
    )
    return SessionMessageResponse(intent=intent, updated_session_state=updated, recommendations=recommendations, answer_text=answer_text)
