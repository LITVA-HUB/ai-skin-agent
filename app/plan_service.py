from __future__ import annotations

from .beauty_modes import detect_mode, mode_categories
from .look_rules import enforce_look_categories
from .models import (
    BudgetDirection,
    DialogIntent,
    IntentDomain,
    ProductCategory,
    ProductDomain,
    RecommendationPlan,
    RoutineSize,
    SkinProfile,
    UserContext,
)
from .intent_service import detect_categories, detect_domain

MAKEUP_CATEGORIES = {
    ProductCategory.foundation,
    ProductCategory.skin_tint,
    ProductCategory.concealer,
    ProductCategory.powder,
    ProductCategory.lipstick,
    ProductCategory.lip_tint,
    ProductCategory.lip_gloss,
    ProductCategory.lip_liner,
    ProductCategory.lip_balm,
    ProductCategory.mascara,
    ProductCategory.eyeliner,
    ProductCategory.eyeshadow_palette,
    ProductCategory.brow_pencil,
    ProductCategory.brow_gel,
    ProductCategory.blush,
    ProductCategory.bronzer,
    ProductCategory.highlighter,
    ProductCategory.contour,
    ProductCategory.primer,
    ProductCategory.setting_spray,
}
SKINCARE_CATEGORIES = {
    ProductCategory.cleanser,
    ProductCategory.serum,
    ProductCategory.moisturizer,
    ProductCategory.spf,
    ProductCategory.toner,
    ProductCategory.spot_treatment,
    ProductCategory.mask,
    ProductCategory.makeup_remover,
}
LIP_CATEGORIES = {ProductCategory.lipstick, ProductCategory.lip_tint, ProductCategory.lip_gloss, ProductCategory.lip_liner, ProductCategory.lip_balm}
EYE_CATEGORIES = {ProductCategory.mascara, ProductCategory.eyeliner, ProductCategory.eyeshadow_palette, ProductCategory.brow_pencil, ProductCategory.brow_gel}
CHEEK_CATEGORIES = {ProductCategory.blush, ProductCategory.bronzer, ProductCategory.highlighter, ProductCategory.contour}


def domains_to_products(domain: IntentDomain) -> list[ProductDomain]:
    if domain == IntentDomain.hybrid:
        return [ProductDomain.skincare, ProductDomain.makeup]
    return [ProductDomain(domain.value)]


def _look_strategy(goal_text: str, context: UserContext) -> tuple[str, str, list[str]]:
    focus_features: list[str] = []
    if any(token in goal_text for token in ["губ", "lip", "помад", "блеск"]):
        focus_features.append("lips")
    if any(token in goal_text for token in ["глаз", "eye", "ресниц", "бров"]):
        focus_features.append("eyes")
    if any(token in goal_text for token in ["румян", "blush", "cheek"]):
        focus_features.append("cheeks")

    style_values = {item.value for item in context.preferred_styles}
    if any(token in goal_text for token in ["sexy", "сексу", "дерзк", "соблазн"]) or 'sexy' in style_values:
        return "sensual", "feature_focus", focus_features or ["lips"]
    if any(token in goal_text for token in ["soft luxury", "тихая роскошь", "дорого", "luxury"]) or 'soft_luxury' in style_values:
        return "soft_luxury", "balanced", focus_features
    if any(token in goal_text for token in ["вечер", "glam", "party"]) or 'glam' in style_values or 'evening' in style_values:
        return "glam", "balanced", focus_features or ["eyes"]
    if any(token in goal_text for token in ["clean girl", "дневн", "quick", "office", "fresh"]) or 'clean_girl' in style_values:
        return "fresh", "soft", focus_features
    return "balanced", "balanced", focus_features


def _beauty_categories_from_goal(goal_text: str, detected: list[ProductCategory], context: UserContext) -> tuple[list[ProductCategory], str, str, list[str]]:
    categories: list[ProductCategory] = []
    explicit = [cat for cat in detected if cat in MAKEUP_CATEGORIES]
    strategy, balance, focus_features = _look_strategy(goal_text, context)
    if explicit:
        if strategy == 'sensual' and ProductCategory.lipstick not in explicit:
            explicit.insert(0, ProductCategory.lipstick)
        if strategy in {'glam', 'sensual'} and 'eyes' in focus_features and ProductCategory.eyeliner not in explicit:
            explicit.append(ProductCategory.eyeliner)
        return list(dict.fromkeys(explicit)), strategy, balance, focus_features

    if any(token in goal_text for token in ["полный образ", "full look", "макияж на вечер", "макияж"]):
        categories.extend([ProductCategory.primer, ProductCategory.foundation, ProductCategory.concealer, ProductCategory.blush, ProductCategory.mascara])
        if "lips" in focus_features or strategy in {"sensual", "soft_luxury"}:
            categories.append(ProductCategory.lipstick)
        else:
            categories.append(ProductCategory.lip_tint)
        if strategy in {"glam", "sensual"} or context.routine_size == RoutineSize.extended:
            categories.extend([ProductCategory.eyeshadow_palette, ProductCategory.brow_gel, ProductCategory.setting_spray])
        if strategy in {"soft_luxury", "glam"}:
            categories.append(ProductCategory.highlighter)
        return list(dict.fromkeys(categories)), strategy, balance, focus_features

    if strategy == "sensual":
        categories.extend([ProductCategory.lipstick, ProductCategory.mascara, ProductCategory.foundation])
        if 'eyes' in focus_features:
            categories.extend([ProductCategory.eyeliner, ProductCategory.eyeshadow_palette])
        if 'lips' in focus_features or not focus_features:
            categories.append(ProductCategory.lip_liner)
        categories.append(ProductCategory.concealer)
    if strategy == "soft_luxury":
        categories.extend([ProductCategory.primer, ProductCategory.foundation, ProductCategory.blush, ProductCategory.highlighter])
        if 'lips' in focus_features:
            categories.append(ProductCategory.lipstick)
        else:
            categories.append(ProductCategory.lip_tint)
    if strategy == "fresh":
        categories.extend([ProductCategory.skin_tint, ProductCategory.blush, ProductCategory.brow_gel, ProductCategory.lip_tint, ProductCategory.mascara])

    if "lips" in focus_features:
        categories.extend([ProductCategory.lipstick, ProductCategory.lip_tint, ProductCategory.lip_gloss])
    if "eyes" in focus_features:
        categories.extend([ProductCategory.mascara, ProductCategory.brow_gel])
        if strategy in {"glam", "sensual"} or context.routine_size != RoutineSize.minimal:
            categories.append(ProductCategory.eyeliner)
    if "cheeks" in focus_features or any(token in goal_text for token in ["свежий образ"]):
        categories.extend([ProductCategory.blush, ProductCategory.highlighter])
    if any(token in goal_text for token in ["быстрый", "quick", "office", "дневной"]):
        categories.extend([ProductCategory.skin_tint, ProductCategory.mascara, ProductCategory.blush, ProductCategory.lip_tint])
    if not categories:
        categories.extend([ProductCategory.foundation, ProductCategory.concealer, ProductCategory.powder])
    return list(dict.fromkeys(categories)), strategy, balance, focus_features


def build_plan(profile: SkinProfile, context: UserContext, intent: DialogIntent | None = None) -> RecommendationPlan:
    goal_text = (context.goal or "").lower().strip()
    mode = detect_mode(goal_text)
    detected = detect_categories(goal_text)
    if intent and intent.target_categories:
        detected = [*intent.target_categories, *[cat for cat in detected if cat not in intent.target_categories]]

    domain = intent.domain if intent else detect_domain(goal_text)
    if intent and intent.target_categories:
        has_makeup = any(cat in MAKEUP_CATEGORIES for cat in intent.target_categories)
        has_skincare = any(cat in SKINCARE_CATEGORIES for cat in intent.target_categories)
        if has_makeup and has_skincare:
            domain = IntentDomain.hybrid
        elif has_makeup:
            domain = IntentDomain.makeup
        elif has_skincare:
            domain = IntentDomain.skincare
    domains = domains_to_products(domain)

    categories: list[ProductCategory] = []
    explicit_skincare_goal = any(token in goal_text for token in ["уход", "skin care", "skincare", "очищ", "крем", "serum", "spf"])
    makeup_first_goal = (any(token in goal_text for token in ["макияж", "look", "образ", "губ", "lip", "глаз", "eye", "румян", "blush", "sexy", "glam", "luxury", "вечер"]) or (domain == IntentDomain.makeup)) and not explicit_skincare_goal
    if ProductDomain.skincare in domains and not makeup_first_goal:
        skincare_bundle = mode_categories(mode) if mode in {'skincare_core', 'hybrid_core'} else [ProductCategory.cleanser, ProductCategory.moisturizer, ProductCategory.spf]
        categories.extend(skincare_bundle)
        if context.routine_size != RoutineSize.minimal and any(c.value in ["redness", "breakouts", "dryness", "oiliness"] for c in profile.primary_concerns):
            categories.insert(1, ProductCategory.serum)
        if ProductCategory.serum in detected and ProductCategory.serum not in categories:
            categories.insert(1, ProductCategory.serum)
        if context.routine_size == RoutineSize.extended:
            if ProductCategory.toner in detected or any(c.value in ["redness", "dryness"] for c in profile.primary_concerns):
                categories.append(ProductCategory.toner)
            if ProductCategory.spot_treatment in detected or any(c.value == "breakouts" for c in profile.primary_concerns):
                categories.append(ProductCategory.spot_treatment)
        if any(token in goal_text for token in ["снять макияж", "makeup remover", "мицелляр"]):
            categories.append(ProductCategory.makeup_remover)

    look_strategy = None
    accent_balance = None
    focus_features: list[str] = []
    if ProductDomain.makeup in domains:
        base_bundle = mode_categories(mode)
        makeup_categories, look_strategy, accent_balance, focus_features = _beauty_categories_from_goal(goal_text, detected, context)
        makeup_categories = [*base_bundle, *[cat for cat in makeup_categories if cat not in base_bundle]]
        if profile.complexion.needs_under_eye_concealer and ProductCategory.concealer not in makeup_categories and any(cat in makeup_categories for cat in {ProductCategory.foundation, ProductCategory.skin_tint}):
            makeup_categories.append(ProductCategory.concealer)
        if "prefer_shine_control" in profile.complexion.complexion_constraints and ProductCategory.powder not in makeup_categories and any(cat in makeup_categories for cat in {ProductCategory.foundation, ProductCategory.skin_tint}):
            makeup_categories.append(ProductCategory.powder)
        if ProductDomain.skincare in domains and context.routine_size == RoutineSize.minimal:
            makeup_categories = makeup_categories[: max(1, min(2, len(makeup_categories)))]
        categories.extend(makeup_categories)

    if intent and intent.target_categories:
        ordered: list[ProductCategory] = []
        for cat in intent.target_categories:
            if cat not in ordered:
                ordered.append(cat)
        for cat in categories:
            if cat not in ordered:
                ordered.append(cat)
        categories = ordered

    categories = enforce_look_categories(categories, RecommendationPlan(required_categories=list(dict.fromkeys(categories)), focus_features=focus_features, look_strategy=look_strategy, accent_balance=accent_balance))

    preferred_finishes = [item.value for item in (context.preferred_finish or profile.complexion.preferred_finish)]
    preferred_coverages = [item.value for item in (context.preferred_coverage or profile.complexion.preferred_coverage)]
    preferred_color_families = [item.value for item in (context.preferred_color_families or profile.makeup_profile.preferred_color_families)]
    preferred_styles = [item.value for item in (context.preferred_styles or profile.makeup_profile.preferred_styles)]

    preferred_tags: list[str] = []
    if ProductDomain.skincare in domains:
        preferred_tags.extend(["gentle", "barrier-support"])
        if any(c.value == "redness" for c in profile.primary_concerns):
            preferred_tags.append("soothing")
        if any(c.value == "breakouts" for c in profile.primary_concerns):
            preferred_tags.append("non-comedogenic")
    if ProductDomain.makeup in domains:
        preferred_tags.extend(["shade-match", "complexion-friendly"])
        if any(cat in categories for cat in LIP_CATEGORIES):
            preferred_tags.append("lip-friendly")
        if any(cat in categories for cat in EYE_CATEGORIES):
            preferred_tags.append("eye-enhancing")
        if any(cat in categories for cat in CHEEK_CATEGORIES):
            preferred_tags.append("face-color")
        if context.occasion and context.occasion.value in {"party", "wedding"}:
            preferred_tags.append("longwear")
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
        preferred_color_families=preferred_color_families,
        preferred_styles=preferred_styles,
        focus_features=focus_features,
        look_strategy=look_strategy,
        accent_balance=accent_balance,
        product_domains=domains,
        planning_notes=[f"goal:{context.goal}"] if context.goal else [],
    )
