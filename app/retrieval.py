from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter
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
SYNONYM_MAP = {
    "тональник": ("foundation", "base", "complexion"),
    "тональный": ("foundation", "base"),
    "консилер": ("concealer", "under_eye"),
    "пудра": ("powder", "setting"),
    "сияющий": ("radiant", "glowy"),
    "сияние": ("radiant", "glow"),
    "матовый": ("matte", "blur"),
    "легкий": ("light", "sheer"),
    "лёгкий": ("light", "sheer"),
    "увлажнение": ("hydrating", "moisturizing"),
    "увлажняющий": ("hydrating", "moisturizing"),
    "покраснение": ("redness", "soothing"),
    "успокаивающий": ("soothing", "calming"),
    "высыпания": ("breakouts", "blemish", "acne"),
    "жирность": ("oiliness", "shine", "matte"),
    "сухость": ("dryness", "hydrating", "barrier"),
    "санскрин": ("spf", "sunscreen", "uv"),
    "умывание": ("cleanser", "cleanse"),
    "сыворотка": ("serum", "active"),
    "крем": ("moisturizer", "cream"),
    "подтон": ("undertone",),
    "тон": ("tone", "shade"),
    "lightweight": ("light", "sheer", "airy"),
    "glowy": ("radiant", "luminous"),
    "luminous": ("radiant", "glowy"),
    "dewy": ("radiant", "hydrated"),
    "sheer": ("light", "skin_tint"),
}
FIELD_WEIGHTS = {
    "title": 3.0,
    "brand": 1.1,
    "category": 2.4,
    "domain": 1.3,
    "skin_types": 1.6,
    "concerns": 2.0,
    "tags": 1.8,
    "ingredients": 1.0,
    "tones": 2.0,
    "undertones": 2.2,
    "finishes": 1.9,
    "coverage_levels": 1.9,
    "suitable_areas": 1.6,
    "texture": 1.1,
    "embedding_text": 1.5,
    "keywords": 1.6,
}


@dataclass(slots=True)
class RetrievalScoredItem:
    product: CatalogProduct
    vector_score: float
    rule_score: float
    rerank_score: float
    why: str


@dataclass(slots=True)
class LocalVectorHit:
    sku: str
    score: float
    vector_score: float
    lexical_score: float


@dataclass(slots=True)
class LocalVectorDocument:
    sku: str
    category: str
    text: str
    weighted_text: str
    vector: tuple[float, ...]
    token_counts: Counter[str]


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text.lower())
    normalized = normalized.replace("ё", "е")
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"[^\w\s+а-яА-Я]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


@lru_cache(maxsize=4096)
def tokenize(text: str) -> tuple[str, ...]:
    base_tokens = TOKEN_RE.findall(normalize_text(text))
    expanded: list[str] = []
    for token in base_tokens:
        expanded.append(token)
        expanded.extend(SYNONYM_MAP.get(token, ()))
        if len(token) >= 6:
            expanded.append(token[:4])
            expanded.append(token[-4:])
    return tuple(expanded)


def _stable_bucket(token: str, salt: str, dims: int) -> int:
    digest = hashlib.sha256(f"{salt}:{token}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % dims


def _hashed_vector(tokens: Iterable[str], dims: int = 128) -> list[float]:
    counts = Counter(tokens)
    vector = [0.0] * dims
    for token, freq in counts.items():
        base_weight = 1.0 + min(freq - 1, 3) * 0.2 + min(len(token), 12) * 0.03
        idx = _stable_bucket(token, "idx", dims)
        sign = -1.0 if (_stable_bucket(token, "sign", 2) % 2) else 1.0
        vector[idx] += sign * base_weight
        if len(token) >= 4:
            vector[_stable_bucket(token[:4], "prefix", dims)] += base_weight * 0.35
            vector[_stable_bucket(token[-4:], "suffix", dims)] += base_weight * 0.2
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


@lru_cache(maxsize=2048)
def vectorize_text(text: str, dims: int = 128) -> tuple[float, ...]:
    return tuple(_hashed_vector(tokenize(text), dims=dims))


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    raw = sum(a * b for a, b in zip(left, right))
    return max(0.0, min(1.0, raw))


def _weighted_chunks(label: str, values: Iterable[str] | str, weight: float) -> list[str]:
    if isinstance(values, str):
        items = [values]
    else:
        items = [value for value in values if value]
    repeated = max(1, round(weight))
    chunks: list[str] = []
    for item in items:
        normalized = normalize_text(item)
        if not normalized:
            continue
        chunks.extend([normalized] * repeated)
        chunks.append(f"{label} {normalized}")
    return chunks


def build_product_document(product: CatalogProduct) -> str:
    keyword_chunks: list[str] = []
    keyword_chunks.extend(CATEGORY_KEYWORDS.get(product.category, []))
    for concern in product.concerns:
        keyword_chunks.extend(CONCERN_KEYWORDS.get(concern, [concern]))
    for tag in product.tags:
        keyword_chunks.extend(TAG_KEYWORDS.get(tag, [tag]))
    weighted_parts: list[str] = []
    weighted_parts.extend(_weighted_chunks("title", product.title, FIELD_WEIGHTS["title"]))
    weighted_parts.extend(_weighted_chunks("brand", product.brand, FIELD_WEIGHTS["brand"]))
    weighted_parts.extend(_weighted_chunks("category", product.category, FIELD_WEIGHTS["category"]))
    weighted_parts.extend(_weighted_chunks("domain", product.domain.value, FIELD_WEIGHTS["domain"]))
    weighted_parts.extend(_weighted_chunks("skin", product.skin_types, FIELD_WEIGHTS["skin_types"]))
    weighted_parts.extend(_weighted_chunks("concern", product.concerns, FIELD_WEIGHTS["concerns"]))
    weighted_parts.extend(_weighted_chunks("tag", product.tags, FIELD_WEIGHTS["tags"]))
    weighted_parts.extend(_weighted_chunks("ingredient", product.ingredients, FIELD_WEIGHTS["ingredients"]))
    weighted_parts.extend(_weighted_chunks("tone", product.tones, FIELD_WEIGHTS["tones"]))
    weighted_parts.extend(_weighted_chunks("undertone", product.undertones, FIELD_WEIGHTS["undertones"]))
    weighted_parts.extend(_weighted_chunks("finish", product.finishes, FIELD_WEIGHTS["finishes"]))
    weighted_parts.extend(_weighted_chunks("coverage", product.coverage_levels, FIELD_WEIGHTS["coverage_levels"]))
    weighted_parts.extend(_weighted_chunks("area", product.suitable_areas, FIELD_WEIGHTS["suitable_areas"]))
    weighted_parts.extend(_weighted_chunks("texture", product.texture or "", FIELD_WEIGHTS["texture"]))
    weighted_parts.extend(_weighted_chunks("embed", product.embedding_text, FIELD_WEIGHTS["embedding_text"]))
    weighted_parts.extend(_weighted_chunks("keyword", keyword_chunks, FIELD_WEIGHTS["keywords"]))
    return " ".join(weighted_parts)


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
        " ".join(context.preferred_finish),
        " ".join(context.preferred_coverage),
        context.goal or "",
    ]
    if intent and intent.intent:
        parts.append(intent.intent)
    if intent and intent.target_category:
        parts.append(intent.target_category)
    parts.extend(CATEGORY_KEYWORDS.get(category, []))
    for concern in profile.primary_concerns:
        parts.extend(CONCERN_KEYWORDS.get(concern, [concern]))
    for tag in plan.preferred_tags:
        parts.extend(TAG_KEYWORDS.get(tag, [tag]))
    if category in MAKEUP_CATEGORIES:
        parts.extend(plan.preferred_tones)
        parts.extend(plan.preferred_undertones)
        parts.extend(plan.preferred_finishes)
        parts.extend(plan.preferred_coverages)
    return " ".join(part for part in parts if part)


@lru_cache(maxsize=256)
def _vector_index() -> "LocalVectorIndex":
    return LocalVectorIndex.from_products(load_catalog())


class LocalVectorIndex:
    def __init__(self, documents: dict[str, LocalVectorDocument]) -> None:
        self.documents = documents

    @classmethod
    def from_products(cls, products: list[CatalogProduct]) -> "LocalVectorIndex":
        docs: dict[str, LocalVectorDocument] = {}
        for product in products:
            text = build_product_document(product)
            docs[product.sku] = LocalVectorDocument(
                sku=product.sku,
                category=product.category,
                text=text,
                weighted_text=text,
                vector=vectorize_text(text),
                token_counts=Counter(tokenize(text)),
            )
        return cls(docs)

    def _lexical_score(self, query_tokens: tuple[str, ...], document: LocalVectorDocument) -> float:
        if not query_tokens:
            return 0.0
        query_counts = Counter(query_tokens)
        overlap = 0.0
        coverage = 0.0
        for token, freq in query_counts.items():
            doc_freq = document.token_counts.get(token, 0)
            if doc_freq:
                overlap += min(freq, doc_freq)
                coverage += 1.0
        overlap_ratio = overlap / max(sum(query_counts.values()), 1)
        coverage_ratio = coverage / max(len(query_counts), 1)
        return min(1.0, overlap_ratio * 0.7 + coverage_ratio * 0.3)

    def search(self, category: str, candidates: list[CatalogProduct], query_text: str, top_k: int = 8) -> list[LocalVectorHit]:
        query_vector = vectorize_text(query_text)
        query_tokens = tokenize(query_text)
        scored: list[LocalVectorHit] = []
        for product in candidates:
            document = self.documents[product.sku]
            vector_score = cosine_similarity(query_vector, document.vector)
            lexical_score = self._lexical_score(query_tokens, document)
            category_bonus = 0.05 if product.category == category else 0.0
            score = round(min(1.0, vector_score * 0.72 + lexical_score * 0.23 + category_bonus), 4)
            scored.append(LocalVectorHit(
                sku=product.sku,
                score=score,
                vector_score=round(vector_score, 4),
                lexical_score=round(lexical_score, 4),
            ))
        scored.sort(key=lambda item: (item.score, item.vector_score, item.lexical_score), reverse=True)
        expanded_top_k = min(max(top_k * 2, 8), len(scored))
        return scored[:expanded_top_k]


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
    if not candidates:
        return []
    hits = _vector_index().search(category, candidates, query_text, top_k=top_k)
    by_sku = {product.sku: product for product in candidates}
    results = [(by_sku[hit.sku], hit.score) for hit in hits if hit.sku in by_sku]
    return results[:top_k]


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
        tone_hits = len(set(plan.preferred_tones) & set(product.tones))
        undertone_hits = len(set(plan.preferred_undertones) & set(product.undertones))
        finish_hits = len(set(plan.preferred_finishes) & set(product.finishes))
        coverage_hits = len(set(plan.preferred_coverages) & set(product.coverage_levels))
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
            complexion_bonus += tone_hits * 0.12
            complexion_bonus += undertone_hits * 0.12
            complexion_bonus += finish_hits * 0.1
            complexion_bonus += coverage_hits * 0.08
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

        rule_score = min(1.0, 0.24 + concern_hits * 0.18 + tag_hits * 0.11 + skin_bonus + budget_bonus + complexion_bonus)
        rerank_score = round(max(0.0, 0.44 * rule_score + 0.46 * vector_score + followup_bonus - novelty_penalty + 0.05), 4)
        why_bits = []
        if product.domain == ProductDomain.makeup:
            if tone_hits:
                why_bits.append("попадает в нужный тон кожи")
            if undertone_hits:
                why_bits.append("совпадает по подтону")
            if finish_hits:
                why_bits.append("даёт нужный финиш")
            if coverage_hits:
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
