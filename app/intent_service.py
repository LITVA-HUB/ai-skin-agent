from __future__ import annotations

import re
from functools import lru_cache

from .catalog import load_catalog
from .models import (
    BudgetDirection,
    DialogIntent,
    IntentAction,
    IntentDomain,
    PriceSegment,
    ProductCategory,
    ProductDomain,
    RoutineSize,
    SessionState,
    SkinTone,
    SkinType,
    Undertone,
)
from .profile_service import infer_preferences_from_goal

CATEGORY_HINTS = {
    ProductCategory.cleanser: ["очищ", "умыва", "cleanser", "wash", "foam"],
    ProductCategory.serum: ["сывор", "serum", "ampoule"],
    ProductCategory.moisturizer: ["крем", "moistur", "cream"],
    ProductCategory.spf: ["spf", "санск", "sunscreen", "sun"],
    ProductCategory.toner: ["тонер", "essence", "mist"],
    ProductCategory.spot_treatment: ["точеч", "spot", "patch"],
    ProductCategory.foundation: ["тональ", "foundation", "тональный", "base makeup"],
    ProductCategory.skin_tint: ["тинт", "skin tint", "sheer", "light coverage"],
    ProductCategory.concealer: ["консил", "под глаза", "concealer"],
    ProductCategory.powder: ["пудр", "powder", "setting"],
    ProductCategory.lipstick: ["помад", "lipstick"],
    ProductCategory.lip_tint: ["lip tint", "тинт для губ"],
    ProductCategory.lip_gloss: ["блеск", "gloss"],
    ProductCategory.lip_liner: ["карандаш для губ", "lip liner"],
    ProductCategory.lip_balm: ["бальзам для губ", "lip balm"],
    ProductCategory.mascara: ["туш", "mascara"],
    ProductCategory.eyeliner: ["подводк", "eyeliner"],
    ProductCategory.eyeshadow_palette: ["тени", "палетка", "eyeshadow"],
    ProductCategory.brow_pencil: ["карандаш для бров", "brow pencil"],
    ProductCategory.brow_gel: ["гель для бров", "brow gel"],
    ProductCategory.blush: ["румян", "blush"],
    ProductCategory.bronzer: ["бронзер", "bronzer"],
    ProductCategory.highlighter: ["хайлайтер", "highlighter"],
    ProductCategory.contour: ["контур", "contour"],
    ProductCategory.primer: ["праймер", "primer"],
    ProductCategory.setting_spray: ["фиксирующий спрей", "setting spray"],
    ProductCategory.makeup_remover: ["снятие макияжа", "makeup remover", "micellar"],
}
DOMAIN_HINTS = {
    IntentDomain.skincare: ["уход", "skin care", "skincare", "routine", "кожа", "cream", "serum", "spf"],
    IntentDomain.makeup: [
        "makeup", "tone", "complexion", "skin tint", "foundation", "concealer", "powder", "тон", "тинт", "консил", "пудр", "макияж",
        "помада", "тушь", "тени", "румяна", "брови", "глаза", "губы", "lip", "eye", "blush", "primer"
    ],
}
ACTION_HINTS = {
    IntentAction.compare: ["срав", "compare", "что лучше", "vs", "против"],
    IntentAction.explain: ["почему", "объяс", "explain", "зачем", "расскажи"],
    IntentAction.cheaper: ["дешев", "бюджетн", "cheaper", "подешев"],
    IntentAction.replace: ["замени", "другой", "вместо", "replacement", "альтернатива"],
    IntentAction.simplify: ["упрост", "короче", "минимал", "simplify", "short", "быстрый макияж"],
    IntentAction.refine: ["уточни", "refine", "чуть", "более", "менее", "подстрой", "собери образ", "полный образ"],
}
POSITIVE_FEEDBACK = ["нрав", "устраивает", "подходит", "leave", "keep", "ok"]
NEGATIVE_FEEDBACK = ["не нрав", "не подход", "убери", "не то", "too much", "not working", "replace"]
INGREDIENT_HINTS = ["niacinamide", "retinol", "acids", "fragrance", "alcohol", "acid", "bha", "aha"]
EXCLUDE_PATTERNS = [
    re.compile(r"(?:без|исключи|исключить|exclude|no|avoid)\s+([a-zа-я0-9_-]+)", re.IGNORECASE),
    re.compile(r"(?:аллергия на|не переношу)\s+([a-zа-я0-9_-]+)", re.IGNORECASE),
]
MAKEUP_CATEGORIES = {
    ProductCategory.foundation, ProductCategory.skin_tint, ProductCategory.concealer, ProductCategory.powder,
    ProductCategory.lipstick, ProductCategory.lip_tint, ProductCategory.lip_gloss, ProductCategory.lip_liner, ProductCategory.lip_balm,
    ProductCategory.mascara, ProductCategory.eyeliner, ProductCategory.eyeshadow_palette, ProductCategory.brow_pencil, ProductCategory.brow_gel,
    ProductCategory.blush, ProductCategory.bronzer, ProductCategory.highlighter, ProductCategory.contour,
    ProductCategory.primer, ProductCategory.setting_spray,
}
SKINCARE_CATEGORIES = {
    ProductCategory.cleanser, ProductCategory.serum, ProductCategory.moisturizer, ProductCategory.spf,
    ProductCategory.toner, ProductCategory.spot_treatment, ProductCategory.mask, ProductCategory.makeup_remover,
}


@lru_cache(maxsize=1)
def catalog_index() -> dict[str, object]:
    products = load_catalog()
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
        "brand_map": brand_map,
        "ingredients": sorted(ingredients, key=len, reverse=True),
        "title_map": title_map,
    }


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def detect_categories(text: str) -> list[ProductCategory]:
    normalized = normalize_text(text)
    hits: list[tuple[int, ProductCategory]] = []
    for category, hints in CATEGORY_HINTS.items():
        for hint in hints:
            idx = normalized.find(hint)
            if idx >= 0:
                hits.append((idx, category))
                break
    hits.sort(key=lambda item: item[0])
    ordered: list[ProductCategory] = []
    for _, category in hits:
        if category not in ordered:
            ordered.append(category)
    return ordered


def detect_domain(text: str) -> IntentDomain:
    normalized = normalize_text(text)
    categories = detect_categories(normalized)
    has_makeup = any(cat in MAKEUP_CATEGORIES for cat in categories)
    has_skincare = any(cat in SKINCARE_CATEGORIES for cat in categories)
    has_skincare = has_skincare or any(token in normalized for token in DOMAIN_HINTS[IntentDomain.skincare])
    has_makeup = has_makeup or any(token in normalized for token in DOMAIN_HINTS[IntentDomain.makeup])
    if has_makeup and has_skincare:
        return IntentDomain.hybrid
    if has_makeup:
        return IntentDomain.makeup
    return IntentDomain.skincare


def detect_action(text: str) -> IntentAction:
    normalized = normalize_text(text)
    for action, hints in ACTION_HINTS.items():
        if any(hint in normalized for hint in hints):
            return action
    return IntentAction.recommend


def extract_brands(text: str) -> list[str]:
    normalized = normalize_text(text)
    brand_map = catalog_index()["brand_map"]
    hits = [brand for key, brand in brand_map.items() if key in normalized]
    return list(dict.fromkeys(hits))


def extract_excluded_ingredients(text: str) -> list[str]:
    normalized = normalize_text(text)
    matches: list[str] = []
    for pattern in EXCLUDE_PATTERNS:
        for match in pattern.findall(normalized):
            matches.append(match.lower())
    if matches:
        return list(dict.fromkeys(matches))
    ingredients = catalog_index()["ingredients"]
    if any(token in normalized for token in ["без", "исключ", "exclude", "no", "avoid"]):
        return [ingredient for ingredient in ingredients if ingredient in normalized]
    return []


def extract_feedback(text: str) -> str | None:
    normalized = normalize_text(text)
    if any(token in normalized for token in NEGATIVE_FEEDBACK):
        return "reject"
    if any(token in normalized for token in POSITIVE_FEEDBACK):
        return "accept"
    return None


def extract_products(text: str) -> list[str]:
    normalized = normalize_text(text)
    title_map = catalog_index()["title_map"]
    hits = [sku for title, sku in title_map.items() if title and title in normalized]
    return list(dict.fromkeys(hits))


def extract_preference_updates(text: str) -> dict[str, object]:
    updates: dict[str, object] = {}
    normalized = normalize_text(text)
    inferred = infer_preferences_from_goal(normalized)
    if inferred["finishes"]:
        updates["preferred_finish"] = [item.value for item in inferred["finishes"]]
    if inferred["coverages"]:
        updates["preferred_coverage"] = [item.value for item in inferred["coverages"]]
    if inferred["colors"]:
        updates["preferred_color_families"] = [item.value for item in inferred["colors"]]
    if inferred["styles"]:
        updates["preferred_styles"] = [item.value for item in inferred["styles"]]
    if inferred["occasion"]:
        updates["occasion"] = inferred["occasion"].value
    if inferred["needs_under_eye_concealer"]:
        updates["needs_under_eye_concealer"] = True
    if any(token in normalized for token in ["подешев", "дешев", "эконом", "бюджет"]):
        updates["budget_direction"] = BudgetDirection.cheaper.value
    if any(token in normalized for token in ["преми", "люкс", "подороже", "дороже"]):
        updates["budget_direction"] = BudgetDirection.premium.value
    if any(token in normalized for token in ["минимал", "короче", "minimal", "short"]):
        updates["routine_size"] = RoutineSize.minimal.value
    if any(token in normalized for token in ["расшир", "добавь", "полный уход", "extended", "полный образ"]):
        updates["routine_size"] = RoutineSize.extended.value
    if any(token in normalized for token in ["soft luxury", "тихая роскошь", "дорого", "luxury"]):
        updates.setdefault("preferred_styles", [])
        updates["preferred_styles"] = list(dict.fromkeys([*updates["preferred_styles"], "soft_luxury"]))
    if any(token in normalized for token in ["sexy", "сексу", "соблазн", "дерзк"]):
        updates.setdefault("preferred_styles", [])
        updates["preferred_styles"] = list(dict.fromkeys([*updates["preferred_styles"], "sexy"]))
    brands = extract_brands(normalized)
    if brands:
        updates["preferred_brands"] = brands
    return updates


def extract_constraint_updates(text: str) -> dict[str, object]:
    updates: dict[str, object] = {}
    normalized = normalize_text(text)
    if any(token in normalized for token in ["дешев", "эконом", "бюджет"]):
        updates["budget_segment"] = PriceSegment.budget.value
    if any(token in normalized for token in ["преми", "люкс"]):
        updates["budget_segment"] = PriceSegment.premium.value
    if any(token in normalized for token in ["средн", "mid"]):
        updates["budget_segment"] = PriceSegment.mid.value
    excluded = extract_excluded_ingredients(normalized)
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


def intent_name(action: IntentAction, text: str) -> str:
    if any(token in text for token in ["сделай на вечер", "повечерн", "more evening", "glam version"]):
        return "transform_evening"
    if any(token in text for token in ["сделай sexy", "сексуаль", "дерзк", "more sexy"]):
        return "transform_sexy"
    if any(token in text for token in ["clean girl", "свежее", "легче", "fresh version"]):
        return "transform_fresh"
    if any(token in text for token in ["дороже по ощущению", "quiet luxury", "soft luxury"]):
        return "transform_soft_luxury"
    if any(token in text for token in ["акцент на губы", "focus on lips"]):
        return "focus_lips"
    if any(token in text for token in ["акцент на глаза", "focus on eyes"]):
        return "focus_eyes"
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
    if any(token in text for token in ["образ", "look", "макияж на вечер", "полный макияж"]):
        return "build_full_look"
    if any(token in text for token in ["добавь", "add"]) and any(token in text for token in ["губ", "глаз", "румян", "бров", "помад", "туш"]):
        return "add_category"
    if "бренд" in text:
        return "change_brand"
    if "без " in text or "исключ" in text:
        return "exclude_ingredient"
    return "general_advice"


def heuristic_intent(message: str, session: SessionState | None = None) -> DialogIntent:
    normalized = normalize_text(message)
    categories = detect_categories(normalized)
    action = detect_action(normalized)
    domain = detect_domain(normalized)
    preference_updates = extract_preference_updates(normalized)
    constraints_update = extract_constraint_updates(normalized)
    feedback = extract_feedback(normalized)
    if feedback:
        constraints_update["feedback"] = feedback

    target_categories = list(categories)
    if not target_categories and session:
        last_target = session.dialog_context.last_target_category
        if last_target:
            target_categories = [last_target]
        else:
            current_map = session.dialog_context.current_recommendations or {}
            if len(current_map) == 1:
                target_categories = list(current_map.keys())
    if action == IntentAction.compare and not target_categories and session:
        current_map = session.dialog_context.current_recommendations or {}
        target_categories = list(current_map.keys())[:2]

    target = target_categories[0] if target_categories else None
    target_domain = None
    if target in MAKEUP_CATEGORIES:
        target_domain = ProductDomain.makeup
    elif target:
        target_domain = ProductDomain.skincare

    if action == IntentAction.recommend and (preference_updates or constraints_update or feedback) and not target_categories:
        action = IntentAction.refine
    name = intent_name(action, normalized)
    if "excluded_ingredients" in constraints_update:
        name = "exclude_ingredient"

    if any(token in name for token in ["transform_", "focus_"]):
        constraints_update["look_transform"] = name
    if action not in {IntentAction.compare, IntentAction.explain}:
        constraints_update.setdefault("goal", message)

    target_products = extract_products(normalized)
    return DialogIntent(
        intent=name,
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
