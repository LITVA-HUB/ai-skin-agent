from __future__ import annotations

from functools import lru_cache

from .catalog import load_catalog
from .models import CatalogProduct, DialogIntent, ProductCategory, ProductDomain, RecommendationItem, RecommendationPlan, SessionState, SkinProfile, UserContext
from .retrieval_filters import domain_for_category, get_current_selection_map, hard_filter_candidates
from .retrieval_reranker import rerank_category
from .vector_index import cached_vector_index, vectorize_text, weighted_chunks

CATEGORY_KEYWORDS = {
    ProductCategory.cleanser: ["cleanser", "cleanse", "wash", "gel", "foam", "очищение", "умывание"],
    ProductCategory.serum: ["serum", "сыворотка", "ampoule", "active"],
    ProductCategory.moisturizer: ["moisturizer", "cream", "gel cream", "крем", "эмульсия"],
    ProductCategory.spf: ["spf", "sunscreen", "uv", "sun", "санскрин", "защита"],
    ProductCategory.toner: ["toner", "essence", "тонер", "mist"],
    ProductCategory.mask: ["mask", "маска", "sleeping pack"],
    ProductCategory.spot_treatment: ["spot", "patch", "точечный", "blemish"],
    ProductCategory.foundation: ["foundation", "тональник", "тональный крем", "base makeup"],
    ProductCategory.skin_tint: ["skin tint", "тинт", "sheer coverage", "легкое покрытие"],
    ProductCategory.concealer: ["concealer", "консилер", "under eye", "spot conceal"],
    ProductCategory.powder: ["powder", "setting powder", "пудра", "shine control"],
    ProductCategory.lipstick: ["lipstick", "помада", "lip color"],
    ProductCategory.lip_tint: ["lip tint", "тинт для губ", "stain"],
    ProductCategory.lip_gloss: ["gloss", "блеск для губ", "juicy lips"],
    ProductCategory.lip_liner: ["lip liner", "карандаш для губ", "define lips"],
    ProductCategory.lip_balm: ["lip balm", "бальзам для губ", "hydrating lips"],
    ProductCategory.mascara: ["mascara", "тушь", "lashes"],
    ProductCategory.eyeliner: ["eyeliner", "подводка", "line eyes"],
    ProductCategory.eyeshadow_palette: ["eyeshadow", "палетка теней", "eye palette"],
    ProductCategory.brow_pencil: ["brow pencil", "карандаш для бровей", "brows"],
    ProductCategory.brow_gel: ["brow gel", "гель для бровей", "set brows"],
    ProductCategory.blush: ["blush", "румяна", "cheek color"],
    ProductCategory.bronzer: ["bronzer", "бронзер", "warm complexion"],
    ProductCategory.highlighter: ["highlighter", "хайлайтер", "glow"],
    ProductCategory.contour: ["contour", "контур", "sculpt"],
    ProductCategory.primer: ["primer", "праймер", "prep makeup"],
    ProductCategory.setting_spray: ["setting spray", "фиксирующий спрей", "set makeup"],
    ProductCategory.makeup_remover: ["makeup remover", "снятие макияжа", "micellar"],
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
    "lip-friendly": ["lips", "comfortable", "lip color"],
    "eye-enhancing": ["eyes", "lashes", "brows", "eye look"],
    "face-color": ["cheeks", "face color", "freshness"],
    "longwear": ["longwear", "lasting", "all day"],
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
    "color_families": 1.8,
    "styles": 1.4,
    "occasions": 1.4,
    "effects": 1.4,
}
MAKEUP_CATEGORIES = {
    ProductCategory.foundation, ProductCategory.skin_tint, ProductCategory.concealer, ProductCategory.powder,
    ProductCategory.lipstick, ProductCategory.lip_tint, ProductCategory.lip_gloss, ProductCategory.lip_liner, ProductCategory.lip_balm,
    ProductCategory.mascara, ProductCategory.eyeliner, ProductCategory.eyeshadow_palette, ProductCategory.brow_pencil, ProductCategory.brow_gel,
    ProductCategory.blush, ProductCategory.bronzer, ProductCategory.highlighter, ProductCategory.contour,
    ProductCategory.primer, ProductCategory.setting_spray,
}


def build_product_document(product: CatalogProduct) -> str:
    keyword_chunks: list[str] = []
    keyword_chunks.extend(CATEGORY_KEYWORDS.get(product.category, []))
    for concern in product.concerns:
        keyword_chunks.extend(CONCERN_KEYWORDS.get(concern.value, [concern.value]))
    for tag in product.tags:
        keyword_chunks.extend(TAG_KEYWORDS.get(tag, [tag]))
    weighted_parts: list[str] = []
    weighted_parts.extend(weighted_chunks("title", product.title, FIELD_WEIGHTS["title"]))
    weighted_parts.extend(weighted_chunks("brand", product.brand, FIELD_WEIGHTS["brand"]))
    weighted_parts.extend(weighted_chunks("category", product.category.value, FIELD_WEIGHTS["category"]))
    weighted_parts.extend(weighted_chunks("domain", product.domain.value, FIELD_WEIGHTS["domain"]))
    weighted_parts.extend(weighted_chunks("skin", product.skin_types, FIELD_WEIGHTS["skin_types"]))
    weighted_parts.extend(weighted_chunks("concern", [c.value for c in product.concerns], FIELD_WEIGHTS["concerns"]))
    weighted_parts.extend(weighted_chunks("tag", product.tags, FIELD_WEIGHTS["tags"]))
    weighted_parts.extend(weighted_chunks("ingredient", product.ingredients, FIELD_WEIGHTS["ingredients"]))
    weighted_parts.extend(weighted_chunks("tone", product.tones, FIELD_WEIGHTS["tones"]))
    weighted_parts.extend(weighted_chunks("undertone", product.undertones, FIELD_WEIGHTS["undertones"]))
    weighted_parts.extend(weighted_chunks("finish", product.finishes, FIELD_WEIGHTS["finishes"]))
    weighted_parts.extend(weighted_chunks("coverage", product.coverage_levels, FIELD_WEIGHTS["coverage_levels"]))
    weighted_parts.extend(weighted_chunks("area", product.suitable_areas, FIELD_WEIGHTS["suitable_areas"]))
    weighted_parts.extend(weighted_chunks("color", product.color_families, FIELD_WEIGHTS["color_families"]))
    weighted_parts.extend(weighted_chunks("style", product.styles, FIELD_WEIGHTS["styles"]))
    weighted_parts.extend(weighted_chunks("occasion", product.occasions, FIELD_WEIGHTS["occasions"]))
    weighted_parts.extend(weighted_chunks("effect", product.effects, FIELD_WEIGHTS["effects"]))
    weighted_parts.extend(weighted_chunks("texture", product.texture or "", FIELD_WEIGHTS["texture"]))
    weighted_parts.extend(weighted_chunks("embed", product.embedding_text, FIELD_WEIGHTS["embedding_text"]))
    weighted_parts.extend(weighted_chunks("keyword", keyword_chunks, FIELD_WEIGHTS["keywords"]))
    return " ".join(weighted_parts)


@lru_cache(maxsize=1)
def vector_index():
    return cached_vector_index(build_product_document)


def build_query_text(profile: SkinProfile, plan: RecommendationPlan, context: UserContext, category: ProductCategory, intent: DialogIntent | None) -> str:
    parts = [
        category.value,
        profile.skin_type.value,
        " ".join(item.value for item in profile.primary_concerns),
        " ".join(item.value for item in profile.secondary_concerns),
        " ".join(plan.preferred_tags),
        " ".join(plan.preferred_skin_types),
        " ".join(plan.preferred_tones),
        " ".join(plan.preferred_undertones),
        " ".join(plan.preferred_finishes),
        " ".join(plan.preferred_coverages),
        " ".join(plan.preferred_color_families),
        " ".join(plan.preferred_styles),
        " ".join(item.value for item in context.preferred_finish),
        " ".join(item.value for item in context.preferred_coverage),
        " ".join(item.value for item in context.preferred_color_families),
        " ".join(item.value for item in context.preferred_styles),
        context.occasion.value if context.occasion else "",
        context.goal or "",
    ]
    if intent and intent.intent:
        parts.append(intent.intent)
    if intent and intent.target_category:
        parts.append(intent.target_category.value)
    parts.extend(CATEGORY_KEYWORDS.get(category, []))
    for concern in profile.primary_concerns:
        parts.extend(CONCERN_KEYWORDS.get(concern.value, [concern.value]))
    for tag in plan.preferred_tags:
        parts.extend(TAG_KEYWORDS.get(tag, [tag]))
    if category in MAKEUP_CATEGORIES:
        parts.extend(plan.preferred_tones)
        parts.extend(plan.preferred_undertones)
        parts.extend(plan.preferred_finishes)
        parts.extend(plan.preferred_coverages)
        parts.extend(plan.preferred_color_families)
        parts.extend(plan.preferred_styles)
    return " ".join(part for part in parts if part)


def semantic_retrieve(category: ProductCategory, candidates: list[CatalogProduct], query_text: str, top_k: int = 8) -> list[tuple[CatalogProduct, float]]:
    if not candidates:
        return []
    hits = vector_index().search(category, candidates, query_text, top_k=top_k)
    by_sku = {product.sku: product for product in candidates}
    results = [(by_sku[hit.sku], hit.score) for hit in hits if hit.sku in by_sku]
    return results[:top_k]


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
        if not candidates and domain_for_category(category) == ProductDomain.makeup:
            active_plan = plan.model_copy(deep=True)
            active_plan.preferred_undertones = []
            candidates = hard_filter_candidates(category, profile, active_plan, context, session, intent)
        if not candidates and domain_for_category(category) == ProductDomain.makeup:
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
