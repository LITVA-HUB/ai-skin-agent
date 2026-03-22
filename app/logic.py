from __future__ import annotations

import uuid

from .gemini_client import GeminiClient, is_probably_base64_image
from .models import (
    AnalyzePhotoRequest,
    AnalyzePhotoResponse,
    ComplexionProfile,
    DialogIntent,
    FinishType,
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
    CoverageLevel,
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
    "foundation": "тональный крем",
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
    "under_eye": "зона под глазами",
    "tone_match": "совпадение с тоном кожи",
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


MAKEUP_KEYWORDS = {
    "foundation": ["тональ", "тональник", "foundation", "тональный"],
    "skin_tint": ["тинт", "skin tint", "легкое покрытие", "лёгкое покрытие"],
    "concealer": ["консилер", "concealer", "под глаза", "under eye"],
    "powder": ["пудра", "powder"],
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
    skin_tone = tone_cycle[score % len(tone_cycle)]
    undertone = undertone_cycle[(score // 7) % len(undertone_cycle)]
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
            "skin_tone": skin_tone,
            "undertone": undertone,
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
    plan = build_plan(profile, request.user_context)
    recommendations = retrieve_products(profile, plan, request.user_context)
    session = SessionState(
        session_id=str(uuid.uuid4()),
        photo_analysis=analysis,
        skin_profile=profile,
        current_plan=plan,
        user_preferences=request.user_context,
        shown_products=[item.sku for item in recommendations],
        accepted_products=[item.sku for item in recommendations],
        dialog_context={
            "llm_photo_analysis": analysis.source == "gemini",
            "current_recommendations": {item.category: item.sku for item in recommendations},
            "active_domains": [domain.value for domain in plan.product_domains],
        },
    )
    store.save(session)
    return AnalyzePhotoResponse(
        session_id=session.session_id,
        photo_analysis_result=analysis,
        skin_profile=profile,
        recommendation_plan=plan,
        recommendations=recommendations,
        answer_text=compose_initial_response(profile, recommendations, plan),
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

    cautions = []
    if s.sensitivity_signs >= 0.45 or "redness" in concerns:
        cautions.append("avoid_aggressive_actives")
    if "dryness" in concerns:
        cautions.append("avoid_overdrying")

    complexion = ComplexionProfile(
        skin_tone=analysis.complexion.skin_tone,
        undertone=analysis.complexion.undertone,
        needs_under_eye_concealer=analysis.complexion.under_eye_darkness >= 0.45,
        complexion_constraints=[
            item
            for item, active in {
                "prefer_non_cakey": analysis.complexion.texture_visibility >= 0.45,
                "prefer_shine_control": analysis.complexion.visible_shine >= 0.55,
                "sensitive_skin_base": skin_type in {SkinType.sensitive, SkinType.dry} or "redness" in concerns,
            }.items()
            if active
        ],
    )

    inferred = infer_preferences_from_goal(goal)
    complexion.preferred_finish = inferred["finishes"]
    complexion.preferred_coverage = inferred["coverages"]
    if inferred["needs_under_eye_concealer"]:
        complexion.needs_under_eye_concealer = True

    return SkinProfile(
        skin_type=skin_type,
        primary_concerns=concerns[:2],
        secondary_concerns=concerns[2:],
        cautions=cautions,
        complexion=complexion,
        confidence_overall=round(min(analysis.confidence, 0.95), 2),
    )


def infer_preferences_from_goal(goal: str | None) -> dict[str, object]:
    text = (goal or "").lower()
    finishes: list[FinishType] = []
    coverages: list[CoverageLevel] = []
    if any(token in text for token in ["сия", "glow", "radiant"]):
        finishes.append(FinishType.radiant)
    if any(token in text for token in ["мат", "matte"]):
        finishes.append(FinishType.matte)
    if any(token in text for token in ["natural", "естест", "натурал", "second skin"]):
        finishes.append(FinishType.natural)
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


def _detect_domains(text: str) -> list[ProductDomain]:
    has_makeup = any(keyword in text for words in MAKEUP_KEYWORDS.values() for keyword in words)
    has_skincare = any(keyword in text for keyword in ["уход", "кожа", "сывор", "крем", "spf", "санскрин", "очищ"])
    if has_makeup and has_skincare:
        return [ProductDomain.skincare, ProductDomain.makeup]
    if has_makeup:
        return [ProductDomain.makeup]
    return [ProductDomain.skincare]


def build_plan(profile: SkinProfile, context: UserContext) -> RecommendationPlan:
    goal_text = (context.goal or "").lower()
    domains = _detect_domains(goal_text)
    categories: list[str] = []
    preferred_tags = ["gentle", "barrier-support"]
    if ProductDomain.skincare in domains:
        categories = ["cleanser", "moisturizer", "spf"]
        if any(c in profile.primary_concerns for c in ["redness", "breakouts", "dryness", "oiliness"]):
            categories.insert(1, "serum")
        if context.routine_size == RoutineSize.extended:
            if "serum" not in categories:
                categories.insert(1, "serum")
            if any(c in profile.primary_concerns for c in ["redness", "dryness"]):
                categories.append("toner")
            if "breakouts" in profile.primary_concerns:
                categories.append("spot_treatment")
    if ProductDomain.makeup in domains:
        makeup_categories = ["foundation", "skin_tint", "concealer", "powder"]
        if any(token in goal_text for token in ["тональ", "foundation", "тональный"]):
            makeup_categories = ["foundation", "concealer", "powder"]
        elif any(token in goal_text for token in ["тинт", "легкое покрытие", "лёгкое покрытие"]):
            makeup_categories = ["skin_tint", "concealer", "powder"]
        elif any(token in goal_text for token in ["консилер", "под глаза"]):
            makeup_categories = ["concealer"]
        elif any(token in goal_text for token in ["пудра", "powder"]):
            makeup_categories = ["powder"]
        categories.extend(makeup_categories)
        preferred_tags.extend(["shade-match", "complexion-friendly"])

    if "redness" in profile.primary_concerns:
        preferred_tags.append("soothing")
    if "breakouts" in profile.primary_concerns:
        preferred_tags.append("non-comedogenic")
    if profile.complexion.needs_under_eye_concealer:
        preferred_tags.append("brightening")
    if "prefer_shine_control" in profile.complexion.complexion_constraints:
        preferred_tags.append("shine-control")
    if FinishType.radiant in profile.complexion.preferred_finish:
        preferred_tags.append("radiant")
    if FinishType.matte in profile.complexion.preferred_finish:
        preferred_tags.append("matte")
    if CoverageLevel.light in profile.complexion.preferred_coverage or CoverageLevel.sheer in profile.complexion.preferred_coverage:
        preferred_tags.append("lightweight")

    return RecommendationPlan(
        required_categories=list(dict.fromkeys(categories)),
        preferred_tags=sorted(set(preferred_tags)),
        exclude_tags=["high-irritation"],
        preferred_skin_types=sorted(set([profile.skin_type.value, "sensitive"] if "redness" in profile.primary_concerns else [profile.skin_type.value])),
        preferred_tones=[profile.complexion.skin_tone.value] if profile.complexion.skin_tone else [],
        preferred_undertones=[profile.complexion.undertone.value] if profile.complexion.undertone else [],
        preferred_finishes=[item.value for item in profile.complexion.preferred_finish],
        preferred_coverages=[item.value for item in profile.complexion.preferred_coverage],
        product_domains=domains,
        planning_notes=[f"goal:{context.goal}"] if context.goal else [],
    )


def _detect_category(text: str) -> str | None:
    mapping = {
        "сывор": "serum",
        "крем": "moisturizer",
        "очищ": "cleanser",
        "умыва": "cleanser",
        "spf": "spf",
        "санск": "spf",
        "тонер": "toner",
        "маск": "mask",
        "патч": "spot_treatment",
        "точеч": "spot_treatment",
        "тональ": "foundation",
        "тональн": "foundation",
        "foundation": "foundation",
        "тинт": "skin_tint",
        "консил": "concealer",
        "под глаза": "concealer",
        "пудр": "powder",
    }
    for key, value in mapping.items():
        if key in text:
            return value
    return None


def _heuristic_intent(message: str) -> DialogIntent:
    text = message.lower()
    target = _detect_category(text)
    domains = _detect_domains(text)
    domain = domains[-1] if domains else None
    updates: dict[str, object] = {}

    if any(token in text for token in ["сия", "radiant", "glow"]):
        updates["preferred_finish"] = [FinishType.radiant.value]
    if any(token in text for token in ["мат", "matte"]):
        updates["preferred_finish"] = [FinishType.matte.value]
    if any(token in text for token in ["легк", "light coverage", "sheer"]):
        updates["preferred_coverage"] = [CoverageLevel.sheer.value, CoverageLevel.light.value]
    if any(token in text for token in ["средн", "medium coverage"]):
        updates["preferred_coverage"] = [CoverageLevel.medium.value]
    if any(token in text for token in ["плот", "full coverage"]):
        updates["preferred_coverage"] = [CoverageLevel.full.value]
    for tone in SkinTone:
        if tone.value.replace("_", " ") in text or tone.value in text:
            updates["skin_tone"] = tone.value
    for ru, tone in [("светл", SkinTone.light.value), ("средн", SkinTone.medium.value), ("тёмн", SkinTone.deep.value)]:
        if ru in text and "skin_tone" not in updates:
            updates["skin_tone"] = tone
    for ru, undertone in [("нейтрал", Undertone.neutral.value), ("тепл", Undertone.warm.value), ("тёпл", Undertone.warm.value), ("холод", Undertone.cool.value), ("олив", Undertone.olive.value)]:
        if ru in text:
            updates["undertone"] = undertone
    if any(token in text for token in ["комбинирован", "combination"]):
        updates["skin_type"] = SkinType.combination.value
    if any(token in text for token in ["жирн", "oily"]):
        updates["skin_type"] = SkinType.oily.value
    if any(token in text for token in ["сух", "dry"]):
        updates["skin_type"] = SkinType.dry.value
    if "под глаза" in text and target is None:
        target = "concealer"

    if "дешев" in text:
        return DialogIntent(intent="cheaper_alternative", target_category=target, target_domain=domain, constraints_update={**updates, "budget_segment": "budget"}, confidence=0.92)
    if "замени" in text or "друг" in text:
        return DialogIntent(intent="replace_product", target_category=target, target_domain=domain, constraints_update={**updates, "replace": True}, confidence=0.87)
    if "без " in text or "исключ" in text:
        ingredient = text.split("без ", 1)[1].split()[0] if "без " in text else None
        return DialogIntent(intent="exclude_ingredient", target_category=target, target_domain=domain, constraints_update={**updates, "excluded_ingredients": [ingredient] if ingredient else []}, confidence=0.88)
    if "бренд" in text:
        return DialogIntent(intent="change_brand", target_category=target, target_domain=domain, constraints_update=updates, confidence=0.7)
    if "короч" in text or "упрост" in text:
        return DialogIntent(intent="simplify_routine", target_domain=domain, constraints_update={**updates, "routine_size": "minimal"}, confidence=0.9)
    if any(token in text for token in ["подобрать", "нужен", "хочу", "тональ", "консил", "пудр", "тинт"]):
        return DialogIntent(intent="general_advice", target_category=target, target_domain=domain, constraints_update={**updates, "goal": message}, confidence=0.75)
    return DialogIntent(intent="general_advice", target_category=target, target_domain=domain, constraints_update={**updates, "goal": message}, confidence=0.55)


def _session_summary(session: SessionState) -> str:
    return (
        f"skin_type={session.skin_profile.skin_type.value}; "
        f"primary_concerns={','.join(session.skin_profile.primary_concerns)}; "
        f"skin_tone={session.skin_profile.complexion.skin_tone.value if session.skin_profile.complexion.skin_tone else ''}; "
        f"undertone={session.skin_profile.complexion.undertone.value if session.skin_profile.complexion.undertone else ''}; "
        f"shown_products={','.join(session.shown_products)}; "
        f"budget={session.user_preferences.budget_segment.value}; "
        f"routine={session.user_preferences.routine_size.value}; "
        f"goal={session.user_preferences.goal or ''}"
    )


def apply_intent(session: SessionState, intent: DialogIntent) -> SessionState:
    prefs = session.user_preferences.model_copy(deep=True)
    profile = session.skin_profile.model_copy(deep=True)
    if "budget_segment" in intent.constraints_update and intent.constraints_update["budget_segment"]:
        prefs.budget_segment = PriceSegment(intent.constraints_update["budget_segment"])
    if "routine_size" in intent.constraints_update and intent.constraints_update["routine_size"]:
        prefs.routine_size = RoutineSize(intent.constraints_update["routine_size"])
    if intent.constraints_update.get("excluded_ingredients"):
        prefs.excluded_ingredients = sorted(set(prefs.excluded_ingredients + intent.constraints_update["excluded_ingredients"]))
    if intent.constraints_update.get("goal"):
        prefs.goal = str(intent.constraints_update["goal"])
    if intent.constraints_update.get("preferred_brands"):
        prefs.preferred_brands = list(intent.constraints_update["preferred_brands"])
    if intent.constraints_update.get("skin_type"):
        profile.skin_type = SkinType(intent.constraints_update["skin_type"])
    if intent.constraints_update.get("skin_tone"):
        profile.complexion.skin_tone = SkinTone(intent.constraints_update["skin_tone"])
    if intent.constraints_update.get("undertone"):
        profile.complexion.undertone = Undertone(intent.constraints_update["undertone"])
    if intent.constraints_update.get("preferred_finish"):
        profile.complexion.preferred_finish = [FinishType(item) for item in intent.constraints_update["preferred_finish"]]
    if intent.constraints_update.get("preferred_coverage"):
        profile.complexion.preferred_coverage = [CoverageLevel(item) for item in intent.constraints_update["preferred_coverage"]]

    plan = build_plan(profile, prefs)
    updated = session.model_copy(deep=True)
    updated.user_preferences = prefs
    updated.skin_profile = profile
    updated.current_plan = plan
    updated.dialog_context.update({
        "last_intent": intent.intent,
        "last_target_category": intent.target_category,
        "active_domains": [domain.value for domain in plan.product_domains],
    })
    current_recommendations = updated.dialog_context.get("current_recommendations") or {}
    if intent.intent in {"replace_product", "cheaper_alternative"} and intent.target_category:
        current_sku = current_recommendations.get(intent.target_category)
        if current_sku and current_sku not in updated.rejected_products:
            updated.rejected_products.append(current_sku)
    return updated


async def handle_message(message: str, store: SessionStore, session_id: str, gemini: GeminiClient) -> SessionMessageResponse:
    session = store.get(session_id)
    if not session:
        raise KeyError(session_id)

    intent = await gemini.parse_intent(message, _session_summary(session)) or _heuristic_intent(message)
    updated = apply_intent(session, intent)
    recommendations = retrieve_products(updated.skin_profile, updated.current_plan, updated.user_preferences, session=updated, intent=intent)
    updated.shown_products = sorted(set(updated.shown_products + [item.sku for item in recommendations]))
    updated.accepted_products = [item.sku for item in recommendations]
    updated.dialog_context["current_recommendations"] = {item.category: item.sku for item in recommendations}
    store.save(updated)

    reply = await gemini.generate_agent_reply(build_reply_prompt(updated, intent, recommendations, message))
    answer_text = reply or compose_followup_response(updated, intent, recommendations, message)
    return SessionMessageResponse(
        intent=intent,
        updated_session_state=updated,
        recommendations=recommendations,
        answer_text=answer_text,
    )


def compose_initial_response(profile: SkinProfile, recommendations: list[RecommendationItem], plan: RecommendationPlan) -> str:
    concerns = ", ".join(CONCERN_LABELS.get(c, c) for c in profile.primary_concerns)
    skin = SKIN_TYPE_LABELS.get(profile.skin_type.value, profile.skin_type.value)
    lines = [f"По фото вижу прежде всего {concerns}. Сейчас кожа ближе к {skin}."]
    if profile.complexion.skin_tone:
        tone = SKIN_TONE_LABELS.get(profile.complexion.skin_tone.value, profile.complexion.skin_tone.value)
        undertone = UNDERTONE_LABELS.get(profile.complexion.undertone.value, profile.complexion.undertone.value) if profile.complexion.undertone else "неопределённый"
        lines.append(f"Для complexion-подбора беру как рабочую гипотезу {tone} тон кожи и {undertone} подтон.")
    if ProductDomain.makeup in plan.product_domains:
        lines.append("Могу вести и уход, и complexion makeup: тон, скин тинт, консилер, пудру.")
    if recommendations:
        lines.append("Собрал стартовую подборку:")
        for item in recommendations:
            lines.append(f"- {CATEGORY_LABELS.get(item.category, item.category)}: {item.title} ({item.brand}) — {item.why}.")
    lines.append("Можно писать по-человечески: «подбери тональник под мой тон кожи», «хочу лёгкое покрытие», «нужен сияющий финиш», «нужен консилер под глаза», «сделай уход проще». ")
    return "\n".join(lines)


def build_reply_prompt(session: SessionState, intent: DialogIntent, recommendations: list[RecommendationItem], message: str) -> str:
    rec_lines = "\n".join(
        f"- {CATEGORY_LABELS.get(item.category, item.category)}: {item.title} ({item.brand}, {item.price_value} ₽) — {item.why}"
        for item in recommendations
    )
    return f"""
Ты — дружелюбный, профессиональный Golden Apple beauty advisor.
Отвечай по-русски, естественно и коротко.
Не ставь диагнозов. Не упоминай внутренние score, retrieval, session_state, intent parsing или JSON.
Можно рекомендовать и skincare, и complexion makeup.
Если точное совпадение оттенка по фото невозможно гарантировать, честно скажи, что это ориентир и лучше проверить свотч/оттенок офлайн.

Профиль кожи: тип={session.skin_profile.skin_type.value}; concerns={','.join(session.skin_profile.primary_concerns)}
Тон кожи={session.skin_profile.complexion.skin_tone.value if session.skin_profile.complexion.skin_tone else ''}; подтон={session.skin_profile.complexion.undertone.value if session.skin_profile.complexion.undertone else ''}
Текущее намерение пользователя: {intent.intent}
Сообщение пользователя: {message}
Текущая подборка:
{rec_lines}

Сформируй удобный ответ для пользователя. Если есть рекомендации, перечисли их аккуратно списком.
""".strip()


def compose_followup_response(session: SessionState, intent: DialogIntent, recommendations: list[RecommendationItem], message: str) -> str:
    preface = {
        "cheaper_alternative": "Ок, пересобрал вариант под более низкий бюджет.",
        "replace_product": "Ок, заменил позицию и обновил подборку.",
        "exclude_ingredient": "Учёл ограничение по ингредиенту и обновил подборку.",
        "simplify_routine": "Сделал подбор проще и короче.",
        "change_brand": "Обновил подборку по брендовым предпочтениям.",
        "explain_product": "Вот как я это вижу.",
        "general_advice": "Понял запрос и обновил подбор под него.",
    }.get(intent.intent, "Подборка обновлена.")
    body = [preface]
    if session.skin_profile.complexion.skin_tone:
        tone = SKIN_TONE_LABELS.get(session.skin_profile.complexion.skin_tone.value, session.skin_profile.complexion.skin_tone.value)
        undertone = UNDERTONE_LABELS.get(session.skin_profile.complexion.undertone.value, session.skin_profile.complexion.undertone.value) if session.skin_profile.complexion.undertone else "неопределённый"
        body.append(f"Ориентируюсь на {tone} тон кожи и {undertone} подтон. Для точного shade match это всё ещё демо-гипотеза по фото.")
    for item in recommendations:
        if intent.target_category and item.category != intent.target_category and intent.intent not in {"simplify_routine", "general_advice"}:
            continue
        body.append(f"- {CATEGORY_LABELS.get(item.category, item.category)}: {item.title} ({item.brand}, {item.price_value} ₽) — {item.why}.")
    return "\n".join(body)
