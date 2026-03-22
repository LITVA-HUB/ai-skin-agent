from __future__ import annotations

import re
import uuid
from functools import lru_cache

from .catalog import load_catalog
from .gemini_client import GeminiClient, is_probably_base64_image
from .models import (
    AnalyzePhotoRequest,
    AnalyzePhotoResponse,
    BudgetDirection,
    ComplexionProfile,
    ConversationTurn,
    CoverageLevel,
    DialogIntent,
    FinishType,
    IntentAction,
    IntentDomain,
    PhotoAnalysisResult,
    PhotoSignals,
    PriceSegment,
    ProductDomain,
    RecommendationItem,
    RecommendationPlan,
    RoutineSize,
    SessionMessageResponse,
    SessionState,
    SkinProfile,
    SkinTone,
    SkinType,
    Undertone,
    UserContext,
)
from .retrieval import retrieve_products
from .store import SessionStore

CATEGORY_LABELS = {
    "cleanser": "очищение",
    "serum": "сыворотка",
    "moisturizer": "крем",
    "spf": "SPF",
    "toner": "тонер",
    "mask": "маска",
    "spot_treatment": "точечный уход",
    "foundation": "тональный",
    "skin_tint": "скин тинт",
    "concealer": "консилер",
    "powder": "пудра",
}
CONCERN_LABELS = {
    "redness": "покраснение",
    "breakouts": "высыпания",
    "dryness": "сухость",
    "oiliness": "жирность",
    "maintenance": "поддержание кожи",
}
SKIN_TYPE_LABELS = {
    "dry": "сухой",
    "oily": "жирной",
    "combination": "комбинированной",
    "normal": "нормальной",
    "sensitive": "чувствительной",
}
SKIN_TONE_LABELS = {
    "fair": "очень светлая",
    "light": "светлая",
    "light_medium": "светло-средняя",
    "medium": "средняя",
    "tan": "загорелая",
    "deep": "глубокая",
}
UNDERTONE_LABELS = {
    "cool": "холодный",
    "neutral": "нейтральный",
    "warm": "тёплый",
    "olive": "оливковый",
}
CATEGORY_HINTS = {
    "cleanser": ["очищ", "умыва", "cleanser", "wash", "foam"],
    "serum": ["сывор", "serum", "ampoule"],
    "moisturizer": ["крем", "moistur", "cream"],
    "spf": ["spf", "санск", "sunscreen", "sun"],
    "toner": ["тонер", "essence", "mist"],
    "spot_treatment": ["точеч", "spot", "patch"],
    "foundation": ["тональ", "foundation", "тональный", "base makeup"],
    "skin_tint": ["тинт", "skin tint", "sheer", "light coverage"],
    "concealer": ["консил", "под глаза", "concealer"],
    "powder": ["пудр", "powder", "setting"],
}
DOMAIN_HINTS = {
    IntentDomain.skincare: ["уход", "skin care", "skincare", "routine", "кожа", "cream", "serum", "spf"],
    IntentDomain.makeup: ["makeup", "tone", "complexion", "skin tint", "foundation", "concealer", "powder", "тон", "тинт", "консил", "пудр", "макияж"],
}
ACTION_HINTS = {
    IntentAction.compare: ["срав", "compare", "что лучше", "vs", "против"],
    IntentAction.explain: ["почему", "объяс", "explain", "зачем", "расскажи"],
    IntentAction.cheaper: ["дешев", "бюджетн", "cheaper", "подешев"],
    IntentAction.replace: ["замени", "другой", "вместо", "replacement", "альтернатива"],
    IntentAction.simplify: ["упрост", "короче", "минимал", "simplify", "short"],
    IntentAction.refine: ["уточни", "refine", "чуть", "более", "менее", "подстрой"],
}
POSITIVE_FEEDBACK = ["нрав", "устраивает", "подходит", "leave", "keep", "ok"]
NEGATIVE_FEEDBACK = ["не нрав", "не подход", "убери", "не то", "too much", "not working", "replace"]
INGREDIENT_HINTS = ["niacinamide", "retinol", "acids", "fragrance", "alcohol", "acid", "bha", "aha"]
EXCLUDE_PATTERNS = [
    re.compile(r"(?:без|исключи|исключить|exclude|no|avoid)\s+([a-zа-я0-9_-]+)", re.IGNORECASE),
    re.compile(r"(?:аллергия на|не переношу)\s+([a-zа-я0-9_-]+)", re.IGNORECASE),
]
MAKEUP_CATEGORIES = {"foundation", "skin_tint", "concealer", "powder"}
SKINCARE_CATEGORIES = {"cleanser", "serum", "moisturizer", "spf", "toner", "spot_treatment", "mask"}
MAX_CONVERSATION_TURNS = 24
MEMORY_QUESTION_HINTS = [
    "что я у тебя спрашивал",
    "что я спрашивал",
    "что ты советовал в первый раз",
    "на чем мы остановились",
    "на чём мы остановились",
    "напомни прошлую подборку",
    "напомни подборку",
    "что было до этого",
    "что ты советовал",
    "что ты рекомендовал",
    "о чем мы говорили",
    "о чём мы говорили",
    "напомни, что было",
]


@lru_cache(maxsize=1)
def _catalog_index() -> dict[str, object]:
    products = load_catalog()
    by_sku = {product.sku: product for product in products}
    brand_map: dict[str, str] = {}
    ingredients: set[str] = set(INGREDIENT_HINTS)
    title_map: dict[str, str] = {}
    for product in products:
        brand_map.setdefault(product.brand.lower(), product.brand)
        title_map.setdefault(product.title.lower(), product.sku)
        for ingredient in product.ingredients:
            if ingredient:
                ingredients.add(ingredient.lower())
    return {
        "by_sku": by_sku,
        "brand_map": brand_map,
        "ingredients": sorted(ingredients, key=len, reverse=True),
        "title_map": title_map,
    }


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _append_conversation_turn(session: SessionState, role: str, message: str) -> None:
    text = (message or '').strip()
    if not text:
        return
    session.conversation_history.append(ConversationTurn(role=role, message=text))
    if len(session.conversation_history) > MAX_CONVERSATION_TURNS:
        session.conversation_history = session.conversation_history[-MAX_CONVERSATION_TURNS:]


def _is_memory_question(message: str) -> bool:
    normalized = _normalize_text(message)
    return any(hint in normalized for hint in MEMORY_QUESTION_HINTS)


def _recent_user_messages(session: SessionState, limit: int = 3, exclude_last: str | None = None) -> list[str]:
    items = [turn.message for turn in session.conversation_history if turn.role == 'user']
    if exclude_last and items and items[-1] == exclude_last:
        items = items[:-1]
    return items[-limit:]


def _first_agent_recommendation(session: SessionState) -> str | None:
    for turn in session.conversation_history:
        if turn.role == 'assistant' and ('- ' in turn.message or 'вот что выглядит удачно на старте' in turn.message.lower()):
            return turn.message
    return None


def _last_assistant_message(session: SessionState) -> str | None:
    for turn in reversed(session.conversation_history):
        if turn.role == 'assistant':
            return turn.message
    return None


def _summarize_message(text: str, max_len: int = 140) -> str:
    clean = re.sub(r'\s+', ' ', text).strip()
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1].rstrip() + '…'


def _answer_from_conversation_history(session: SessionState, message: str) -> str:
    normalized = _normalize_text(message)
    user_messages = _recent_user_messages(session, exclude_last=message)
    if 'что я' in normalized and ('спрашивал' in normalized or 'говорил' in normalized):
        if not user_messages:
            return 'Пока ты ещё ничего не спрашивал в этой сессии.'
        lines = ['Вот последние вопросы в этой сессии:']
        for item in user_messages:
            lines.append(f'- {_summarize_message(item)}')
        return '\n'.join(lines)
    if 'в первый раз' in normalized or 'первый' in normalized:
        first_reply = _first_agent_recommendation(session)
        if first_reply:
            return f'В первый раз я советовал вот это:\n{first_reply}'
        return 'Не вижу в истории первой подборки, на которую можно точно сослаться.'
    if 'остановились' in normalized:
        last_reply = _last_assistant_message(session)
        if last_reply:
            return f'Мы остановились на этом:\n{last_reply}'
        return 'Пока не на чем останавливаться — в истории ещё нет прошлого ответа.'
    if 'прошлую подборку' in normalized or 'напомни подборку' in normalized:
        last_reply = _last_assistant_message(session)
        if last_reply:
            return f'Напоминаю прошлую подборку:\n{last_reply}'
        return 'Не вижу сохранённой прошлой подборки в этой сессии.'
    if user_messages:
        lines = ['Коротко по истории текущего чата:']
        for item in user_messages:
            lines.append(f'- {_summarize_message(item)}')
        return '\n'.join(lines)
    return 'Пока в этой сессии нет истории, на которую можно опереться.'


def _extract_brands(text: str) -> list[str]:
    normalized = _normalize_text(text)
    brand_map = _catalog_index()["brand_map"]
    hits = [brand for key, brand in brand_map.items() if key in normalized]
    return list(dict.fromkeys(hits))


def _extract_excluded_ingredients(text: str) -> list[str]:
    normalized = _normalize_text(text)
    matches: list[str] = []
    for pattern in EXCLUDE_PATTERNS:
        for match in pattern.findall(normalized):
            matches.append(match.lower())
    if matches:
        return list(dict.fromkeys(matches))
    ingredients = _catalog_index()["ingredients"]
    if any(token in normalized for token in ["без", "исключ", "exclude", "no", "avoid"]):
        return [ingredient for ingredient in ingredients if ingredient in normalized]
    return []


def _extract_feedback(text: str) -> str | None:
    normalized = _normalize_text(text)
    if any(token in normalized for token in NEGATIVE_FEEDBACK):
        return "reject"
    if any(token in normalized for token in POSITIVE_FEEDBACK):
        return "accept"
    return None


def _extract_products(text: str) -> list[str]:
    normalized = _normalize_text(text)
    title_map = _catalog_index()["title_map"]
    hits = [sku for title, sku in title_map.items() if title and title in normalized]
    return list(dict.fromkeys(hits))


COVERAGE_LABELS = {
    "sheer": "очень легкое покрытие",
    "light": "легкое покрытие",
    "medium": "среднее покрытие",
    "full": "плотное покрытие",
}
FINISH_LABELS = {
    "radiant": "сияющий финиш",
    "matte": "матовый финиш",
    "natural": "естественный финиш",
    "satin": "сатиновый финиш",
}


def _mock_photo_analysis(request: AnalyzePhotoRequest) -> PhotoAnalysisResult:
    seed = (request.image_url or "") + (request.photo_b64 or "") + (request.user_context.goal or "")
    score = sum(ord(ch) for ch in seed) % 100 if seed else 42
    redness = round(min(1.0, 0.3 + (score % 30) / 100), 2)
    breakouts = round(min(1.0, 0.2 + ((score * 3) % 40) / 100), 2)
    oiliness = round(min(1.0, 0.25 + ((score * 5) % 35) / 100), 2)
    dryness = round(max(0.0, 0.55 - oiliness / 2), 2)
    sensitivity = round(min(1.0, redness * 0.7), 2)
    tone_cycle = [SkinTone.fair, SkinTone.light, SkinTone.light_medium, SkinTone.medium, SkinTone.tan, SkinTone.deep]
    undertone_cycle = [Undertone.neutral, Undertone.warm, Undertone.cool, Undertone.olive]
    return PhotoAnalysisResult(
        signals=PhotoSignals(
            oiliness=oiliness,
            dryness=dryness,
            redness=redness,
            breakouts=breakouts,
            tone_evenness=round(max(0.0, 1 - redness), 2),
            sensitivity_signs=sensitivity,
        ),
        complexion={
            "skin_tone": tone_cycle[score % len(tone_cycle)],
            "undertone": undertone_cycle[(score // 7) % len(undertone_cycle)],
            "under_eye_darkness": round(min(1.0, 0.15 + ((score * 2) % 35) / 100), 2),
            "visible_shine": oiliness,
            "texture_visibility": round(min(1.0, 0.2 + ((score * 4) % 30) / 100), 2),
        },
        confidence=0.62,
        limitations=["single-angle-only", "undertone-is-an-approximation"],
        source="mock",
    )


async def analyze_photo(request: AnalyzePhotoRequest, store: SessionStore, gemini: GeminiClient) -> AnalyzePhotoResponse:
    analysis = None
    if request.photo_b64 and is_probably_base64_image(request.photo_b64):
        analysis = await gemini.analyze_photo(request.photo_b64)
    if analysis is None:
        analysis = _mock_photo_analysis(request)

    profile = build_skin_profile(analysis, request.user_context.goal)
    context = _merge_context_preferences(request.user_context, profile)
    plan = build_plan(profile, context)
    recommendations = retrieve_products(profile, plan, context)
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
        dialog_context={
            "current_recommendations": {item.category: item.sku for item in recommendations},
            "active_domains": [domain.value for domain in plan.product_domains],
        },
        conversation_history=[ConversationTurn(role='assistant', message=answer_text)],
    )
    store.save(session)
    return AnalyzePhotoResponse(
        session_id=session.session_id,
        photo_analysis_result=analysis,
        skin_profile=profile,
        recommendation_plan=plan,
        recommendations=recommendations,
        answer_text=answer_text,
    )


def build_skin_profile(analysis: PhotoAnalysisResult, goal: str | None = None) -> SkinProfile:
    s = analysis.signals
    if s.oiliness > 0.6 and s.dryness < 0.35:
        skin_type = SkinType.oily
    elif s.dryness > 0.6 and s.oiliness < 0.35:
        skin_type = SkinType.dry
    elif s.sensitivity_signs > 0.65:
        skin_type = SkinType.sensitive
    elif 0.35 <= s.oiliness <= 0.7 and 0.2 <= s.dryness <= 0.6:
        skin_type = SkinType.combination
    else:
        skin_type = SkinType.normal

    concerns = []
    if s.redness >= 0.45:
        concerns.append("redness")
    if s.breakouts >= 0.45:
        concerns.append("breakouts")
    if s.dryness >= 0.45:
        concerns.append("dryness")
    if s.oiliness >= 0.55:
        concerns.append("oiliness")
    if not concerns:
        concerns.append("maintenance")

    inferred = infer_preferences_from_goal(goal)
    complexion = ComplexionProfile(
        skin_tone=analysis.complexion.skin_tone,
        undertone=analysis.complexion.undertone,
        preferred_finish=inferred["finishes"],
        preferred_coverage=inferred["coverages"],
        needs_under_eye_concealer=analysis.complexion.under_eye_darkness >= 0.45 or inferred["needs_under_eye_concealer"],
        complexion_constraints=[item for item, active in {
            "prefer_non_cakey": analysis.complexion.texture_visibility >= 0.45,
            "prefer_shine_control": analysis.complexion.visible_shine >= 0.55,
        }.items() if active],
    )
    return SkinProfile(
        skin_type=skin_type,
        primary_concerns=concerns[:2],
        secondary_concerns=concerns[2:],
        cautions=["avoid_aggressive_actives"] if s.sensitivity_signs >= 0.45 else [],
        complexion=complexion,
        confidence_overall=round(min(analysis.confidence, 0.95), 2),
    )


def infer_preferences_from_goal(goal: str | None) -> dict[str, object]:
    text = (goal or "").lower()
    finishes: list[FinishType] = []
    coverages: list[CoverageLevel] = []
    if any(token in text for token in ["сия", "glow", "radiant", "dewy"]):
        finishes.append(FinishType.radiant)
    if any(token in text for token in ["мат", "matte"]):
        finishes.append(FinishType.matte)
    if any(token in text for token in ["natural", "естест", "натурал", "second skin"]):
        finishes.append(FinishType.natural)
    if any(token in text for token in ["сатин", "satin"]):
        finishes.append(FinishType.satin)
    if any(token in text for token in ["легк", "sheer", "light coverage", "skin tint"]):
        coverages.extend([CoverageLevel.sheer, CoverageLevel.light])
    if any(token in text for token in ["средн", "medium coverage"]):
        coverages.append(CoverageLevel.medium)
    if any(token in text for token in ["плот", "full coverage"]):
        coverages.append(CoverageLevel.full)
    return {
        "finishes": list(dict.fromkeys(finishes)),
        "coverages": list(dict.fromkeys(coverages)),
        "needs_under_eye_concealer": any(token in text for token in ["под глаза", "under eye", "консилер"]),
    }


def _detect_category(text: str) -> str | None:
    categories = _detect_categories(text)
    return categories[0] if categories else None


def _detect_categories(text: str) -> list[str]:
    normalized = _normalize_text(text)
    hits: list[tuple[int, str]] = []
    for category, hints in CATEGORY_HINTS.items():
        for hint in hints:
            idx = normalized.find(hint)
            if idx >= 0:
                hits.append((idx, category))
                break
    hits.sort(key=lambda item: item[0])
    ordered: list[str] = []
    for _, category in hits:
        if category not in ordered:
            ordered.append(category)
    return ordered


def _detect_domain(text: str) -> IntentDomain:
    normalized = _normalize_text(text)
    categories = _detect_categories(normalized)
    has_makeup = any(cat in MAKEUP_CATEGORIES for cat in categories)
    has_skincare = any(cat in SKINCARE_CATEGORIES for cat in categories)
    has_skincare = has_skincare or any(token in normalized for token in DOMAIN_HINTS[IntentDomain.skincare])
    has_makeup = has_makeup or any(token in normalized for token in DOMAIN_HINTS[IntentDomain.makeup])
    if has_makeup and has_skincare:
        return IntentDomain.hybrid
    if has_makeup:
        return IntentDomain.makeup
    return IntentDomain.skincare


def _domains_to_products(domain: IntentDomain) -> list[ProductDomain]:
    if domain == IntentDomain.hybrid:
        return [ProductDomain.skincare, ProductDomain.makeup]
    return [ProductDomain(domain.value)]


def _intent_name(action: IntentAction, text: str) -> str:
    if action == IntentAction.cheaper:
        return "cheaper_alternative"
    if action == IntentAction.replace:
        return "replace_product"
    if action == IntentAction.compare:
        return "compare_products"
    if action == IntentAction.explain:
        return "explain_product"
    if action == IntentAction.simplify:
        return "simplify_routine"
    if "бренд" in text:
        return "change_brand"
    if "без " in text or "исключ" in text:
        return "exclude_ingredient"
    return "general_advice"


def _detect_action(text: str) -> IntentAction:
    normalized = _normalize_text(text)
    for action, hints in ACTION_HINTS.items():
        if any(hint in normalized for hint in hints):
            return action
    return IntentAction.recommend


def _extract_preference_updates(text: str) -> dict[str, object]:
    updates: dict[str, object] = {}
    normalized = _normalize_text(text)
    inferred = infer_preferences_from_goal(normalized)
    if inferred["finishes"]:
        updates["preferred_finish"] = [item.value for item in inferred["finishes"]]
    if inferred["coverages"]:
        updates["preferred_coverage"] = [item.value for item in inferred["coverages"]]
    if inferred["needs_under_eye_concealer"]:
        updates["needs_under_eye_concealer"] = True
    if any(token in normalized for token in ["подешев", "дешев", "эконом", "бюджет"]):
        updates["budget_direction"] = BudgetDirection.cheaper.value
    if any(token in normalized for token in ["преми", "люкс", "подороже", "дороже"]):
        updates["budget_direction"] = BudgetDirection.premium.value
    if any(token in normalized for token in ["минимал", "короче", "minimal", "short"]):
        updates["routine_size"] = RoutineSize.minimal.value
    if any(token in normalized for token in ["расшир", "добавь", "полный уход", "extended"]):
        updates["routine_size"] = RoutineSize.extended.value
    brands = _extract_brands(normalized)
    if brands:
        updates["preferred_brands"] = brands
    return updates


def _extract_constraint_updates(text: str) -> dict[str, object]:
    updates: dict[str, object] = {}
    normalized = _normalize_text(text)
    if any(token in normalized for token in ["дешев", "эконом", "бюджет"]):
        updates["budget_segment"] = PriceSegment.budget.value
    if any(token in normalized for token in ["преми", "люкс"]):
        updates["budget_segment"] = PriceSegment.premium.value
    if any(token in normalized for token in ["средн", "mid"]):
        updates["budget_segment"] = PriceSegment.mid.value
    excluded = _extract_excluded_ingredients(normalized)
    if excluded:
        updates["excluded_ingredients"] = excluded
    if any(token in normalized for token in ["комбинирован", "combination"]):
        updates["skin_type"] = SkinType.combination.value
    if any(token in normalized for token in ["жирн", "oily"]):
        updates["skin_type"] = SkinType.oily.value
    if any(token in normalized for token in ["сух", "dry"]):
        updates["skin_type"] = SkinType.dry.value
    for tone in SkinTone:
        if tone.value.replace("_", " ") in normalized or tone.value in normalized:
            updates["skin_tone"] = tone.value
    for ru, tone in [("светл", SkinTone.light.value), ("средн", SkinTone.medium.value), ("темн", SkinTone.deep.value)]:
        if ru in normalized and "skin_tone" not in updates:
            updates["skin_tone"] = tone
    for ru, undertone in [("нейтр", Undertone.neutral.value), ("тепл", Undertone.warm.value), ("холод", Undertone.cool.value), ("олив", Undertone.olive.value)]:
        if ru in normalized:
            updates["undertone"] = undertone
    return updates


def _heuristic_intent(message: str, session: SessionState | None = None) -> DialogIntent:
    normalized = _normalize_text(message)
    categories = _detect_categories(normalized)
    action = _detect_action(normalized)
    domain = _detect_domain(normalized)
    preference_updates = _extract_preference_updates(normalized)
    constraints_update = _extract_constraint_updates(normalized)
    feedback = _extract_feedback(normalized)
    if feedback:
        constraints_update["feedback"] = feedback

    target_categories = list(categories)
    if not target_categories and session:
        last_target = session.dialog_context.get("last_target_category")
        if last_target:
            target_categories = [last_target]
        else:
            current_map = session.dialog_context.get("current_recommendations") or {}
            if len(current_map) == 1:
                target_categories = list(current_map.keys())
    if action == IntentAction.compare and not target_categories and session:
        current_map = session.dialog_context.get("current_recommendations") or {}
        target_categories = list(current_map.keys())[:2]

    target = target_categories[0] if target_categories else None
    target_domain = None
    if target in MAKEUP_CATEGORIES:
        target_domain = ProductDomain.makeup
    elif target:
        target_domain = ProductDomain.skincare

    if action == IntentAction.recommend and (preference_updates or constraints_update or feedback) and not target_categories:
        action = IntentAction.refine
    intent_name = _intent_name(action, normalized)
    if "excluded_ingredients" in constraints_update:
        intent_name = "exclude_ingredient"

    if action not in {IntentAction.compare, IntentAction.explain}:
        constraints_update.setdefault("goal", message)

    target_products = _extract_products(normalized)
    return DialogIntent(
        intent=intent_name,
        action=action,
        domain=domain,
        target_category=target,
        target_categories=target_categories,
        target_product=target_products[0] if target_products else None,
        target_products=target_products,
        target_domain=target_domain,
        preference_updates=preference_updates,
        constraints_update=constraints_update,
        confidence=0.8,
    )


def _merge_context_preferences(context: UserContext, profile: SkinProfile) -> UserContext:
    merged = context.model_copy(deep=True)
    if not merged.preferred_finish:
        merged.preferred_finish = list(profile.complexion.preferred_finish)
    if not merged.preferred_coverage:
        merged.preferred_coverage = list(profile.complexion.preferred_coverage)
    return merged


def build_plan(profile: SkinProfile, context: UserContext, intent: DialogIntent | None = None) -> RecommendationPlan:
    goal_text = _normalize_text(context.goal or "")
    detected = _detect_categories(goal_text)
    if intent and intent.target_categories:
        detected = [*intent.target_categories, *[cat for cat in detected if cat not in intent.target_categories]]

    domain = intent.domain if intent else _detect_domain(goal_text)
    if intent and intent.target_categories:
        has_makeup = any(cat in MAKEUP_CATEGORIES for cat in intent.target_categories)
        has_skincare = any(cat in SKINCARE_CATEGORIES for cat in intent.target_categories)
        if has_makeup and has_skincare:
            domain = IntentDomain.hybrid
        elif has_makeup:
            domain = IntentDomain.makeup
        elif has_skincare:
            domain = IntentDomain.skincare
    domains = _domains_to_products(domain)

    categories: list[str] = []
    if ProductDomain.skincare in domains:
        categories.extend(["cleanser", "moisturizer", "spf"])
        if context.routine_size != RoutineSize.minimal and any(
            c in profile.primary_concerns for c in ["redness", "breakouts", "dryness", "oiliness"]
        ):
            categories.insert(1, "serum")
        if "serum" in detected and "serum" not in categories:
            categories.insert(1, "serum")
        if context.routine_size == RoutineSize.extended:
            if "toner" in detected or any(c in profile.primary_concerns for c in ["redness", "dryness"]):
                categories.append("toner")
            if "spot_treatment" in detected or "breakouts" in profile.primary_concerns:
                categories.append("spot_treatment")

    if ProductDomain.makeup in domains:
        explicit_makeup = [cat for cat in detected if cat in MAKEUP_CATEGORIES]
        if explicit_makeup:
            makeup_categories = list(explicit_makeup)
        elif "foundation" in detected:
            makeup_categories = ["foundation", "concealer", "powder"]
        elif "skin_tint" in detected:
            makeup_categories = ["skin_tint", "concealer", "powder"]
        elif "concealer" in detected:
            makeup_categories = ["concealer"]
        elif "powder" in detected:
            makeup_categories = ["powder"]
        else:
            makeup_categories = ["foundation", "concealer", "powder"]

        if profile.complexion.needs_under_eye_concealer and "concealer" not in makeup_categories:
            makeup_categories.append("concealer")
        if "prefer_shine_control" in profile.complexion.complexion_constraints and "powder" not in makeup_categories:
            makeup_categories.append("powder")
        if ProductDomain.skincare in domains and context.routine_size == RoutineSize.minimal:
            makeup_categories = explicit_makeup or makeup_categories[:1]
        categories.extend(makeup_categories)

    if intent and intent.target_categories:
        ordered: list[str] = []
        for cat in intent.target_categories:
            if cat not in ordered:
                ordered.append(cat)
        for cat in categories:
            if cat not in ordered:
                ordered.append(cat)
        categories = ordered

    preferred_finishes = [item.value for item in (context.preferred_finish or profile.complexion.preferred_finish)]
    preferred_coverages = [item.value for item in (context.preferred_coverage or profile.complexion.preferred_coverage)]

    preferred_tags: list[str] = []
    if ProductDomain.skincare in domains:
        preferred_tags.extend(["gentle", "barrier-support"])
        if "redness" in profile.primary_concerns:
            preferred_tags.append("soothing")
        if "breakouts" in profile.primary_concerns:
            preferred_tags.append("non-comedogenic")
    if ProductDomain.makeup in domains:
        preferred_tags.extend(["shade-match", "complexion-friendly"])
    if context.budget_direction == BudgetDirection.cheaper:
        preferred_tags.append("value")

    return RecommendationPlan(
        required_categories=list(dict.fromkeys(categories)),
        preferred_tags=sorted(set(preferred_tags)),
        exclude_tags=["high-irritation"],
        preferred_skin_types=[profile.skin_type.value],
        preferred_tones=[profile.complexion.skin_tone.value] if profile.complexion.skin_tone else [],
        preferred_undertones=[profile.complexion.undertone.value] if profile.complexion.undertone else [],
        preferred_finishes=preferred_finishes,
        preferred_coverages=preferred_coverages,
        product_domains=domains,
        planning_notes=[f"goal:{context.goal}"] if context.goal else [],
    )


def _session_summary(session: SessionState) -> str:
    return (
        f"skin_type={session.skin_profile.skin_type.value}; concerns={','.join(session.skin_profile.primary_concerns)}; "
        f"tone={session.skin_profile.complexion.skin_tone.value if session.skin_profile.complexion.skin_tone else ''}; "
        f"undertone={session.skin_profile.complexion.undertone.value if session.skin_profile.complexion.undertone else ''}; "
        f"finish={','.join(item.value for item in session.user_preferences.preferred_finish)}; "
        f"coverage={','.join(item.value for item in session.user_preferences.preferred_coverage)}; "
        f"brands={','.join(session.user_preferences.preferred_brands)}; excluded={','.join(session.user_preferences.excluded_ingredients)}; "
        f"budget={session.user_preferences.budget_segment.value}; budget_direction={session.user_preferences.budget_direction.value}; "
        f"routine={session.user_preferences.routine_size.value}; accepted={','.join(session.accepted_products)}; rejected={','.join(session.rejected_products)}"
    )


def _merge_update_dicts(primary: dict[str, object] | None, secondary: dict[str, object] | None) -> dict[str, object]:
    merged: dict[str, object] = {}
    for source in [secondary or {}, primary or {}]:
        for key, value in source.items():
            if isinstance(value, list) and isinstance(merged.get(key), list):
                merged[key] = list(dict.fromkeys([*merged[key], *value]))
            else:
                merged[key] = value
    return merged


def _merge_intents(primary: DialogIntent | None, fallback: DialogIntent | None) -> DialogIntent:
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
    merged.preference_updates = _merge_update_dicts(base.preference_updates, other.preference_updates)
    merged.constraints_update = _merge_update_dicts(base.constraints_update, other.constraints_update)
    if merged.domain == IntentDomain.skincare and other.domain == IntentDomain.hybrid:
        merged.domain = other.domain
    if merged.domain == IntentDomain.skincare and other.domain == IntentDomain.makeup and other.target_categories:
        merged.domain = other.domain
    return merged


def _recommendations_from_current(session: SessionState, target_categories: list[str] | None = None) -> list[RecommendationItem]:
    selection = session.dialog_context.get("current_recommendations") or {}
    categories = target_categories or session.current_plan.required_categories
    catalog = _catalog_index()["by_sku"]
    items: list[RecommendationItem] = []
    for category in categories:
        sku = selection.get(category)
        if not sku:
            continue
        product = catalog.get(sku)
        if not product:
            continue
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


def _needs_recommendation_refresh(session: SessionState, intent: DialogIntent) -> bool:
    if intent.action in {IntentAction.compare, IntentAction.explain}:
        non_refresh = {"feedback", "accepted_products", "rejected_products"}
        extra_updates = [key for key in intent.constraints_update if key not in non_refresh]
        if intent.preference_updates or extra_updates:
            return True
        current_map = session.dialog_context.get("current_recommendations") or {}
        if intent.target_categories and any(cat not in current_map for cat in intent.target_categories):
            return True
        return False
    return True


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
        prefs.routine_size = RoutineSize(merged["routine_size"])
    if merged.get("preferred_brands"):
        prefs.preferred_brands = list(dict.fromkeys([*prefs.preferred_brands, *merged["preferred_brands"]]))
    if merged.get("excluded_ingredients"):
        prefs.excluded_ingredients = list(dict.fromkeys([*prefs.excluded_ingredients, *merged["excluded_ingredients"]]))
    if constraint_updates.get("goal") and intent.action not in {IntentAction.compare, IntentAction.explain}:
        prefs.goal = str(constraint_updates["goal"])
    if merged.get("preferred_finish"):
        prefs.preferred_finish = [FinishType(item) for item in merged["preferred_finish"]]
        profile.complexion.preferred_finish = [FinishType(item) for item in merged["preferred_finish"]]
    if merged.get("preferred_coverage"):
        prefs.preferred_coverage = [CoverageLevel(item) for item in merged["preferred_coverage"]]
        profile.complexion.preferred_coverage = [CoverageLevel(item) for item in merged["preferred_coverage"]]
    if merged.get("needs_under_eye_concealer"):
        profile.complexion.needs_under_eye_concealer = True
    if merged.get("skin_type"):
        profile.skin_type = SkinType(merged["skin_type"])
    if merged.get("skin_tone"):
        profile.complexion.skin_tone = SkinTone(merged["skin_tone"])
    if merged.get("undertone"):
        profile.complexion.undertone = Undertone(merged["undertone"])

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

    current = updated.dialog_context.get("current_recommendations") or {}
    target_for_feedback = intent.target_category or updated.dialog_context.get("last_target_category")
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
    updated.dialog_context.update({
        "last_intent": intent.intent,
        "last_action": intent.action.value,
        "last_domain": intent.domain.value,
        "last_target_category": intent.target_category,
        "last_target_categories": intent.target_categories,
        "last_target_products": intent.target_products,
        "active_domains": [domain.value for domain in updated.current_plan.product_domains],
    })
    return updated


async def handle_message(message: str, store: SessionStore, session_id: str, gemini: GeminiClient) -> SessionMessageResponse:
    session = store.get(session_id)
    if not session:
        raise KeyError(session_id)

    if _is_memory_question(message):
        updated = session.model_copy(deep=True)
        _append_conversation_turn(updated, 'user', message)
        answer_text = _answer_from_conversation_history(updated, message)
        _append_conversation_turn(updated, 'assistant', answer_text)
        store.save(updated)
        return SessionMessageResponse(
            intent=DialogIntent(intent='conversation_memory', action=IntentAction.explain, confidence=1.0),
            updated_session_state=updated,
            recommendations=_recommendations_from_current(updated),
            answer_text=answer_text,
        )

    model_intent = await gemini.parse_intent(message, _session_summary(session))
    heuristic_intent = _heuristic_intent(message, session=session)
    intent = _merge_intents(model_intent, heuristic_intent)
    updated = apply_intent(session, intent)
    _append_conversation_turn(updated, 'user', message)

    if _needs_recommendation_refresh(updated, intent):
        recommendations = retrieve_products(updated.skin_profile, updated.current_plan, updated.user_preferences, session=updated, intent=intent)
        new_skus = [item.sku for item in recommendations]
        updated.shown_products = sorted(set(updated.shown_products + new_skus))
        updated.accepted_products = list(dict.fromkeys([*updated.accepted_products, *new_skus]))
        updated.accepted_products = [sku for sku in updated.accepted_products if sku not in updated.rejected_products]
        updated.user_preferences.accepted_products = list(updated.accepted_products)
        updated.user_preferences.rejected_products = list(updated.rejected_products)
        updated.dialog_context["current_recommendations"] = {item.category: item.sku for item in recommendations}
    else:
        target_categories = intent.target_categories or ([intent.target_category] if intent.target_category else None)
        recommendations = _recommendations_from_current(updated, target_categories)
        updated.user_preferences.accepted_products = list(updated.accepted_products)
        updated.user_preferences.rejected_products = list(updated.rejected_products)

    reply = await gemini.generate_agent_reply(build_reply_prompt(updated, intent, recommendations, message))
    answer_text = _sanitize_agent_text(reply) if reply else compose_followup_response(updated, intent, recommendations, message)
    _append_conversation_turn(updated, 'assistant', answer_text)
    store.save(updated)
    return SessionMessageResponse(intent=intent, updated_session_state=updated, recommendations=recommendations, answer_text=answer_text)


def _humanize_shade_token(value: str) -> str:
    parts = value.replace('-', '_').split('_')
    mapping = {
        'fair': 'очень светлый',
        'light': 'светлый',
        'medium': 'средний',
        'tan': 'загорелый',
        'deep': 'глубокий',
        'neutral': 'нейтральный',
        'warm': 'тёплый',
        'cool': 'холодный',
        'olive': 'оливковый',
    }
    human = [mapping.get(part.lower(), part.lower()) for part in parts if part]
    return ' '.join(human).strip()


def _pretty_product_title(title: str) -> str:
    match = re.search(r'\b([A-Z]+(?:_[A-Z]+)+)\b', title)
    if not match:
        return title
    shade = match.group(1)
    human_shade = _humanize_shade_token(shade)
    return title.replace(shade, human_shade)


def _sanitize_agent_text(text: str) -> str:
    cleaned = text.replace('**', '').replace('__', '')
    cleaned = re.sub(r'(?m)^\s*#{1,6}\s*', '', cleaned)
    cleaned = re.sub(r'`+', '', cleaned)
    return cleaned.strip()


def compose_initial_response(profile: SkinProfile, recommendations: list[RecommendationItem], plan: RecommendationPlan) -> str:
    concerns = ", ".join(CONCERN_LABELS.get(c, c) for c in profile.primary_concerns)
    skin = SKIN_TYPE_LABELS.get(profile.skin_type.value, profile.skin_type.value)
    lines = [f"По фото в первую очередь вижу {concerns}. Тип кожи сейчас ближе к {skin}."]
    if ProductDomain.makeup in plan.product_domains:
        lines.append("Параллельно могу помочь не только с уходом, но и с подбором тона, консилера и других complexion-средств.")
    if recommendations:
        lines.append("Вот что выглядит удачно на старте:")
        for item in recommendations[:4]:
            pretty_title = _pretty_product_title(item.title)
            lines.append(f"- {CATEGORY_LABELS.get(item.category, item.category)}: {pretty_title} ({item.brand}) — {item.why}.")
    lines.append("Дальше можно просто писать по-человечески: сравнить варианты, сделать дешевле, упростить рутину или подобрать что-то под другой запрос.")
    return "\n".join(lines)


def build_reply_prompt(session: SessionState, intent: DialogIntent, recommendations: list[RecommendationItem], message: str) -> str:
    rec_lines = "\n".join(f"- {_pretty_product_title(item.title)} ({item.brand}, {item.category}, {item.price_value} ₽): {item.why}" for item in recommendations)
    return f"""
Ты — дружелюбный Golden Apple beauty advisor.
Отвечай по-русски, естественно, предметно и приятно для пользователя.
Тон ответа должен быть тёплый, уверенный и product-facing: так, чтобы пользователю хотелось попробовать вариант, но без навязчивости и без агрессивного давления.
Нельзя использовать markdown-оформление: не ставь звёздочки, не выделяй жирным, не используй заголовки с #.
Не показывай сырые shade-коды вроде LIGHT_NEUTRAL или MEDIUM_WARM. Если упоминаешь оттенок, пиши его по-человечески: например «светлый нейтральный» или «средний тёплый».
Если запрос на compare — сравни продукты простым человеческим языком.
Если запрос на explain — объясни, почему продукт или категория подходят именно этому пользователю.
Если запрос смешанный, помоги и по уходу, и по complexion makeup в одном ответе.
Сообщение пользователя: {message}
Action={intent.action.value}; domain={intent.domain.value}; target={intent.target_category};
Подборка:
{rec_lines}
""".strip()


def _pick_label(values: list[str], labels: dict[str, str]) -> str | None:
    for value in values:
        label = labels.get(value)
        if label:
            return label
    return None


def _describe_item(item: RecommendationItem, session: SessionState) -> str:
    catalog = _catalog_index()["by_sku"]
    product = catalog.get(item.sku)
    if not product:
        return item.why
    bits: list[str] = []
    if product.domain == ProductDomain.makeup:
        coverage = _pick_label(product.coverage_levels, COVERAGE_LABELS)
        finish = _pick_label(product.finishes, FINISH_LABELS)
        if coverage:
            bits.append(coverage)
        if finish:
            bits.append(finish)
        if product.tones and session.current_plan.preferred_tones and set(product.tones) & set(session.current_plan.preferred_tones):
            bits.append('попадает в нужный тон кожи')
        if product.undertones and session.current_plan.preferred_undertones and set(product.undertones) & set(session.current_plan.preferred_undertones):
            bits.append('совпадает по подтону')
    else:
        concerns = [CONCERN_LABELS.get(c, c) for c in product.concerns[:2]]
        if concerns:
            bits.append(f"подходит под {', '.join(concerns)}")
        if 'soothing' in product.tags:
            bits.append('работает мягко и комфортно')
        if 'non-comedogenic' in product.tags:
            bits.append('не должен перегружать кожу')
    details = ', '.join(bits[:2]) if bits else ''
    if details:
        return f"{item.why}, {details}"
    return item.why


def _find_item_for_category(
    session: SessionState,
    recommendations: list[RecommendationItem],
    category: str,
) -> RecommendationItem | None:
    for item in recommendations:
        if item.category == category:
            return item
    selection = session.dialog_context.get('current_recommendations') or {}
    sku = selection.get(category)
    if not sku:
        return None
    product = _catalog_index()["by_sku"].get(sku)
    if not product:
        return None
    return RecommendationItem(
        sku=product.sku,
        title=product.title,
        brand=product.brand,
        category=product.category,
        domain=product.domain,
        price_segment=product.price_segment,
        price_value=product.price_value,
        why='текущий вариант',
        vector_score=0.0,
        rule_score=0.0,
        final_score=0.0,
    )


def _alternative_for_category(session: SessionState, category: str, intent: DialogIntent) -> RecommendationItem | None:
    alt_intent = DialogIntent(
        intent='replace_product',
        action=IntentAction.replace,
        domain=intent.domain,
        target_category=category,
        target_categories=[category],
        confidence=0.4,
    )
    alt = retrieve_products(
        session.skin_profile,
        session.current_plan,
        session.user_preferences,
        session=session,
        intent=alt_intent,
    )
    for item in alt:
        if item.category == category:
            return item
    return None


def compose_compare_response(session: SessionState, intent: DialogIntent, recommendations: list[RecommendationItem]) -> str:
    target_categories = intent.target_categories or ([intent.target_category] if intent.target_category else [])
    items: list[RecommendationItem] = []
    if target_categories:
        for category in target_categories:
            item = _find_item_for_category(session, recommendations, category)
            if item:
                items.append(item)
    else:
        items = recommendations[:2]
    if len(target_categories) == 1:
        alt = _alternative_for_category(session, target_categories[0], intent)
        if alt:
            items.append(alt)
    if len(items) < 2:
        return 'Пока не вижу двух сильных вариантов для честного сравнения. Скажи, что именно сравнить — например тональный и skin tint.'
    lines = ['Сравню коротко и по делу:']
    for item in items[:2]:
        pretty_title = _pretty_product_title(item.title)
        lines.append(f"- {pretty_title} ({item.brand}) — {_describe_item(item, session)}. Цена {item.price_value} ₽.")
    lines.append('Если хочешь, дальше могу сказать, какой из них выглядит более удачным именно под твой запрос.')
    return "\n".join(lines)


def compose_explain_response(session: SessionState, intent: DialogIntent, recommendations: list[RecommendationItem]) -> str:
    target = intent.target_category or (intent.target_categories[0] if intent.target_categories else None)
    focus = _find_item_for_category(session, recommendations, target) if target else (recommendations[0] if recommendations else None)
    if not focus:
        return 'Сейчас не вижу явного варианта, который можно объяснить отдельно. Скажи, какой именно продукт разобрать.'
    pretty_title = _pretty_product_title(focus.title)
    lines = [f"Почему я бы оставил {pretty_title}:"]
    lines.append(f"- {_describe_item(focus, session)}.")
    lines.append(f"- Бренд {focus.brand}, цена {focus.price_value} ₽.")
    if focus.domain == ProductDomain.makeup:
        lines.append('Это тот вариант, который должен смотреться аккуратно, современно и без ощущения тяжёлой маски.')
    return "\n".join(lines)


def compose_followup_response(session: SessionState, intent: DialogIntent, recommendations: list[RecommendationItem], message: str) -> str:
    if intent.action == IntentAction.compare:
        return compose_compare_response(session, intent, recommendations)
    if intent.action == IntentAction.explain:
        return compose_explain_response(session, intent, recommendations)
    preface = {
        "cheaper_alternative": "Нашёл вариант поразумнее по цене — без сильной просадки по качеству впечатления.",
        "replace_product": "Обновил подборку и нашёл более удачную замену.",
        "exclude_ingredient": "Учёл ограничение по составу и пересобрал варианты.",
        "simplify_routine": "Сделал подборку проще и чище по шагам.",
        "general_advice": "Вот что сейчас выглядит наиболее удачно под твой запрос.",
    }.get(intent.intent, "Подборку обновил.")
    lines = [preface]
    if intent.domain == IntentDomain.hybrid:
        lines.append("Собрал связку так, чтобы уход и тон работали вместе и не спорили между собой.")
    for item in recommendations[:4]:
        if intent.target_category and intent.action in {IntentAction.replace, IntentAction.cheaper} and item.category != intent.target_category:
            continue
        pretty_title = _pretty_product_title(item.title)
        lines.append(f"- {CATEGORY_LABELS.get(item.category, item.category)}: {pretty_title} ({item.brand}, {item.price_value} ₽) — {item.why}.")
    lines.append("Если хочешь, дальше могу сделать ещё более сияющий, более лёгкий или более бюджетный вариант.")
    return "\n".join(lines)
