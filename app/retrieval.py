from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from .catalog import load_catalog
from .models import CatalogProduct, DialogIntent, PriceSegment, ProductDomain, RecommendationItem, RecommendationPlan, SessionState, SkinProfile, UserContext

TOKEN_RE = re.compile(r"[a-zA-Zа-яА-Я0-9_+-]+")
CATEGORY_KEYWORDS = {
    "cleanser": ["cleanser", "cleanse", "wash", "gel", "foam", "очищение", "умывание"],
    "serum": ["serum", "сыворотка", "ampoule", "active"],
    "moisturizer": ["moisturizer", "cream", "gel cream", "крем", "эмульсия"],
    "spf": ["spf", "sunscreen", "uv", "sun", "санскрин", "защита"],
    "toner": ["toner", "essence", "тонер", "mist"],
    "mask": ["mask", "маска", "sleeping pack"],
    "spot_treatment": ["spot", "patch", "точечный", "blemish"],
    "foundation": ["foundation", "тональник", "тональный крем", "base makeup"],
    "skin_tint": ["skin tint", "тинт", "sheer coverage", "легкое покрытие"],
    "concealer": ["concealer", "консилер", "under eye", "spot conceal"],
    "powder": ["powder", "setting powder", "пудра", "shine control"],
}
CONCERN_KEYWORDS = {
    "redness": ["redness", "soothing", "calming", "sensitive", "покраснение"],
    "breakouts": ["breakout", "acne", "blemish", "pore", "высыпания"],
    "dryness": ["dryness", "hydrating", "barrier", "dehydrated", "сухость"],
    "oiliness": ["oiliness", "sebum", "shine", "matte", "жирность"],
    "maintenance": ["maintenance", "daily", "basic", "support"],
    "tone_match": ["shade match", "tone match", "undertone", "тон кожи"],
    "under_eye": ["under eye", "dark circles", "консилер"],
}
TAG_KEYWORDS = {
    "gentle": ["gentle", "mild", "soft", "gentle-cleanse"],
    "barrier-support": ["barrier", "ceramide", "repair", "support"],
    "soothing": ["soothing", "calming", "centella", "panthenol"],
    "non-comedogenic": ["non-comedogenic", "clog", "pore", "blemish-safe"],
    "fragrance-free": ["fragrance-free", "unscented"],
    "lightweight": ["lightweight", "gel", "fluid", "airy"],
    "daily-use": ["daily", "everyday", "city"],
    "shade-match": ["shade", "tone", "undertone", "match"],
    "complexion-friendly": ["base makeup", "complexion", "skin-like"],
    "shine-control": ["oil control", "shine control", "matte"],
    "brightening": ["brightening", "under eye", "radiance"],
    "radiant": ["radiant", "glowy", "luminous"],
    "matte": ["matte", "soft matte", "blur"],
}
PRICE_ORDER = {
    PriceSegment.budget: 0,
    PriceSegment.mid: 1,
    PriceSegment.premium: 2,
}
MAKEUP_CATEGORIES = {"foundation", "skin_tint", "concealer", "powder"}


@dataclass(slots=True)
class RetrievalScoredItem:
    product: CatalogProduct
    vector_score: float
    rule_score: float
    rerank_score: float
    why: str


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("-", " ")).strip()


@lru_cache(maxsize=4096)
def tokenize(text: str) -> tuple[str, ...]:
    return tuple(TOKEN_RE.findall(normalize_text(text)))


def _stable_bucket(token: str, salt: str, dims: int) -> int:
    digest = hashlib.sha256(f"{salt}:{token}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % dims


def _hashed_vector(tokens: Iterable[str], dims: int = 64) -> list[float]:
    vector = [0.0] * dims
    for token in tokens:
        idx = _stable_bucket(token, "idx", dims)
        sign = -1.0 if (_stable_bucket(token, "sign", 2) % 2) else 1.0
        vector[idx] += sign * (1.0 + (len(token) % 5) * 0.1)
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


@lru_cache(maxsize=2048)
def vectorize_text(text: str, dims: int = 64) -> tuple[float, ...]:
    return tuple(_hashed_vector(tokenize(text), dims=dims))


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    return max(0.0, min(1.0, (sum(a * b for a, b in zip(left, right)) + 1.0) / 2.0))


@lru_cache(maxsize=256)
def _product_vectors() -> dict[str, tuple[float, ...]]:
    return {product.sku: vectorize_text(build_product_document(product)) for product in load_catalog()}


def build_product_document(product: CatalogProduct) -> str:
    keyword_chunks = []
    keyword_chunks.extend(CATEGORY_KEYWORDS.get(product.category, []))
    for concern in product.concerns:
        keyword_chunks.extend(CONCERN_KEYWORDS.get(concern, [concern]))
    for tag in product.tags:
        keyword_chunks.extend(TAG_KEYWORDS.get(tag, [tag]))
    return " ".join([
        product.title,
        product.brand,
        product.domain.value,
        product.category,
        " ".join(product.skin_types),
        " ".join(product.concerns),
        " ".join(product.tags),
        " ".join(product.ingredients),
        " ".join(product.tones),
        " ".join(product.undertones),
        " ".join(product.finishes),
        " ".join(product.coverage_levels),
        " ".join(product.suitable_areas),
        product.texture or "",
        product.embedding_text,
        " ".join(keyword_chunks),
    ])


def build_query_text(profile: SkinProfile, plan: RecommendationPlan, context: UserContext, category: str, intent: DialogIntent | None) -> str:
    parts = [
        category,
        profile.skin_type.value,
        " ".join(profile.primary_concerns),
        " ".join(profile.secondary_concerns),
        " ".join(plan.preferred_tags),
        " ".join(plan.preferred_skin_types),
        " ".join(plan.preferred_tones),
        " ".join(plan.preferred_undertones),
        " ".join(plan.preferred_finishes),
        " ".join(plan.preferred_coverages),
        context.goal or "",
    ]
    if intent and intent.intent:
        parts.append(intent.intent)
    if intent and intent.target_category:
        parts.append(intent.target_category)
    parts.extend(CATEGORY_KEYWORDS.get(category, []))
    return " ".join(part for part in parts if part)


def _budget_allows(product: CatalogProduct, budget: PriceSegment, intent: DialogIntent | None, current_product: CatalogProduct | None) -> bool:
    if intent and intent.intent == "cheaper_alternative":
        if current_product and product.price_value >= current_product.price_value:
            return False
        if budget == PriceSegment.budget:
            return product.price_segment == PriceSegment.budget
        if budget == PriceSegment.mid:
            return product.price_segment in {PriceSegment.budget, PriceSegment.mid}
        return True
    if budget == PriceSegment.premium:
        return True
    if budget == PriceSegment.mid:
        return product.price_segment != PriceSegment.premium
    return product.price_segment == PriceSegment.budget


def _domain_for_category(category: str) -> ProductDomain:
    return ProductDomain.makeup if category in MAKEUP_CATEGORIES else ProductDomain.skincare


def hard_filter_candidates(
    category: str,
    profile: SkinProfile,
    plan: RecommendationPlan,
    context: UserContext,
    session: SessionState | None,
    intent: DialogIntent | None,
) -> list[CatalogProduct]:
    current_selection = get_current_selection_map(session)
    current_product = next((p for p in load_catalog() if p.sku == current_selection.get(category)), None)
    candidates: list[CatalogProduct] = []
    excluded_ingredients = {item.lower() for item in context.excluded_ingredients}
    rejected = set(session.rejected_products if session else [])
    category_domain = _domain_for_category(category)

    for product in load_catalog():
        if product.category != category or not product.availability:
            continue
        if product.domain != category_domain:
            continue
        if plan.product_domains and product.domain not in plan.product_domains:
            continue
        if not _budget_allows(product, context.budget_segment, intent if intent and intent.target_category == category else None, current_product):
            continue
        if excluded_ingredients.intersection(ingredient.lower() for ingredient in product.ingredients):
            continue
        if profile.skin_type.value in product.exclude_for or set(profile.primary_concerns).intersection(product.exclude_for):
            continue
        if plan.exclude_tags and set(plan.exclude_tags).intersection(product.tags):
            continue
        if context.preferred_brands and product.brand not in context.preferred_brands:
            continue
        if product.sku in rejected and not (intent and intent.intent == "cheaper_alternative"):
            continue
        if intent and intent.intent in {"replace_product", "cheaper_alternative"} and intent.target_category == category and current_selection.get(category) == product.sku:
            continue

        if product.domain == ProductDomain.skincare:
            skin_match = profile.skin_type.value in product.skin_types or any(t in product.skin_types for t in ["sensitive", "combination", "normal"])
            if not skin_match:
                continue
        else:
            if plan.preferred_tones and product.tones and not set(plan.preferred_tones).intersection(product.tones):
                continue
            if plan.preferred_undertones and product.undertones and not set(plan.preferred_undertones).intersection(product.undertones):
                continue
            if category == "concealer" and profile.complexion.needs_under_eye_concealer and product.suitable_areas and "under_eye" not in product.suitable_areas:
                continue
        candidates.append(product)
    return candidates


def semantic_retrieve(category: str, candidates: list[CatalogProduct], query_text: str, top_k: int = 8) -> list[tuple[CatalogProduct, float]]:
    query_vector = vectorize_text(query_text)
    vectors = _product_vectors()
    scored = [(product, cosine_similarity(query_vector, vectors[product.sku])) for product in candidates]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:top_k]


def get_current_selection_map(session: SessionState | None) -> dict[str, str]:
    if not session:
        return {}
    current = session.dialog_context.get("current_recommendations")
    return current.copy() if isinstance(current, dict) else {}


def rerank_category(
    category: str,
    profile: SkinProfile,
    plan: RecommendationPlan,
    context: UserContext,
    semantic_hits: list[tuple[CatalogProduct, float]],
    session: SessionState | None,
    intent: DialogIntent | None,
) -> list[RetrievalScoredItem]:
    current_selection = get_current_selection_map(session)
    current_sku = current_selection.get(category)
    current_product = next((product for product in load_catalog() if product.sku == current_sku), None)
    shown = set(session.shown_products if session else [])
    accepted = set(session.accepted_products if session else [])

    ranked: list[RetrievalScoredItem] = []
    for product, vector_score in semantic_hits:
        concern_hits = len(set(profile.primary_concerns) & set(product.concerns))
        tag_hits = len(set(plan.preferred_tags) & set(product.tags))
        skin_bonus = 0.12 if product.domain == ProductDomain.skincare and profile.skin_type.value in product.skin_types else 0.05
        if product.price_segment == context.budget_segment:
            budget_bonus = 0.18 if context.budget_segment == PriceSegment.premium else 0.14
        elif PRICE_ORDER[product.price_segment] < PRICE_ORDER[context.budget_segment]:
            budget_bonus = 0.02 if context.budget_segment == PriceSegment.premium else 0.06
        else:
            budget_bonus = 0.0
        complexion_bonus = 0.0
        followup_bonus = 0.0
        novelty_penalty = 0.0

        if product.domain == ProductDomain.makeup:
            if plan.preferred_tones and set(product.tones) & set(plan.preferred_tones):
                complexion_bonus += 0.18
            if plan.preferred_undertones and set(product.undertones) & set(plan.preferred_undertones):
                complexion_bonus += 0.14
            if plan.preferred_finishes and set(product.finishes) & set(plan.preferred_finishes):
                complexion_bonus += 0.12
            if plan.preferred_coverages and set(product.coverage_levels) & set(plan.preferred_coverages):
                complexion_bonus += 0.1
            if category == "concealer" and "under_eye" in product.suitable_areas:
                complexion_bonus += 0.08
        if current_product and intent and intent.target_category == category:
            if intent.intent == "cheaper_alternative":
                followup_bonus += 0.18 if product.price_value < current_product.price_value else -0.2
            if intent.intent == "replace_product":
                overlap = len(set(product.tags) & set(current_product.tags)) + len(set(product.concerns) & set(current_product.concerns))
                followup_bonus += 0.06 * overlap
        if product.sku in shown:
            novelty_penalty += 0.16
        if product.sku in accepted:
            followup_bonus += 0.08

        rule_score = min(1.0, 0.28 + concern_hits * 0.18 + tag_hits * 0.12 + skin_bonus + budget_bonus + complexion_bonus)
        rerank_score = round(max(0.0, 0.52 * rule_score + 0.33 * vector_score + followup_bonus - novelty_penalty + 0.05), 4)
        why_bits = []
        if product.domain == ProductDomain.makeup:
            if plan.preferred_tones and set(product.tones) & set(plan.preferred_tones):
                why_bits.append("попадает в нужный тон кожи")
            if plan.preferred_undertones and set(product.undertones) & set(plan.preferred_undertones):
                why_bits.append("совпадает по подтону")
            if plan.preferred_finishes and set(product.finishes) & set(plan.preferred_finishes):
                why_bits.append("даёт нужный финиш")
            if plan.preferred_coverages and set(product.coverage_levels) & set(plan.preferred_coverages):
                why_bits.append("попадает в желаемую плотность")
        else:
            if concern_hits:
                why_bits.append("закрывает ключевые задачи кожи")
        if tag_hits:
            why_bits.append("совпадает по полезным свойствам")
        if product.price_segment == context.budget_segment or PRICE_ORDER[product.price_segment] < PRICE_ORDER[context.budget_segment]:
            why_bits.append("нормально вписывается в бюджет")
        if intent and intent.intent == "cheaper_alternative" and current_product and product.price_value < current_product.price_value:
            why_bits.append("реально дешевле текущего варианта")
        if intent and intent.intent == "replace_product" and current_product:
            why_bits.append("похож по роли, но не повторяет прошлый вариант")
        ranked.append(RetrievalScoredItem(product=product, vector_score=round(vector_score, 4), rule_score=round(rule_score, 4), rerank_score=rerank_score, why=", ".join(dict.fromkeys(why_bits)) or "подходит по профилю и логике подбора"))
    ranked.sort(key=lambda item: (item.rerank_score, item.vector_score, -item.product.price_value), reverse=True)
    return ranked


def retrieve_products(
    profile: SkinProfile,
    plan: RecommendationPlan,
    context: UserContext,
    session: SessionState | None = None,
    intent: DialogIntent | None = None,
) -> list[RecommendationItem]:
    current_selection = get_current_selection_map(session)
    results: list[RecommendationItem] = []

    for category in plan.required_categories:
        if session and intent and intent.intent in {"replace_product", "cheaper_alternative", "exclude_ingredient", "change_brand"} and intent.target_category and intent.target_category != category:
            keep_sku = current_selection.get(category)
            keep_product = next((product for product in load_catalog() if product.sku == keep_sku), None)
            if keep_product:
                results.append(RecommendationItem(
                    sku=keep_product.sku,
                    title=keep_product.title,
                    brand=keep_product.brand,
                    category=keep_product.category,
                    domain=keep_product.domain,
                    price_segment=keep_product.price_segment,
                    price_value=keep_product.price_value,
                    why="оставил прошлый удачный вариант в этой категории",
                    vector_score=0.0,
                    rule_score=0.0,
                    final_score=1.0,
                ))
                continue

        active_plan = plan
        candidates = hard_filter_candidates(category, profile, plan, context, session, intent)
        if not candidates and _domain_for_category(category) == ProductDomain.makeup:
            active_plan = plan.model_copy(deep=True)
            active_plan.preferred_undertones = []
            candidates = hard_filter_candidates(category, profile, active_plan, context, session, intent)
        if not candidates and _domain_for_category(category) == ProductDomain.makeup:
            active_plan = active_plan.model_copy(deep=True)
            active_plan.preferred_tones = []
            candidates = hard_filter_candidates(category, profile, active_plan, context, session, intent)
        if not candidates:
            continue
        query_text = build_query_text(profile, active_plan, context, category, intent)
        semantic_hits = semantic_retrieve(category, candidates, query_text)
        ranked = rerank_category(category, profile, active_plan, context, semantic_hits, session, intent)
        if not ranked:
            continue
        top = ranked[0]
        results.append(RecommendationItem(
            sku=top.product.sku,
            title=top.product.title,
            brand=top.product.brand,
            category=top.product.category,
            domain=top.product.domain,
            price_segment=top.product.price_segment,
            price_value=top.product.price_value,
            why=top.why,
            vector_score=top.vector_score,
            rule_score=top.rule_score,
            final_score=top.rerank_score,
        ))

    return results
