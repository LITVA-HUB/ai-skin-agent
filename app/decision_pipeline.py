from __future__ import annotations

from pydantic import BaseModel, Field

from .beauty_modes import detect_mode, mode_categories
from .look_rules import fallback_categories_for
from .models import DialogIntent, ProductCategory, RecommendationItem, RecommendationPlan, SessionState, SkinProfile, UserContext
from .retrieval import build_query_text, semantic_retrieve
from .retrieval_filters import hard_filter_candidates
from .retrieval_reranker import rerank_category


class DecisionTraceItem(BaseModel):
    requested_category: ProductCategory
    resolved_category: ProductCategory | None = None
    fallback_used: bool = False
    fallback_from: ProductCategory | None = None
    selected_sku: str | None = None


class DecisionTrace(BaseModel):
    mode: str
    requested_categories: list[ProductCategory] = Field(default_factory=list)
    resolved_items: list[DecisionTraceItem] = Field(default_factory=list)


def dedup_categories(categories: list[ProductCategory]) -> list[ProductCategory]:
    return list(dict.fromkeys(categories))


def bundle_for_request(context: UserContext) -> tuple[str, list[ProductCategory]]:
    mode = detect_mode((context.goal or '').lower())
    return mode, dedup_categories(mode_categories(mode))


def recommendation_from_scored(top) -> RecommendationItem:
    return RecommendationItem(
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
    )


def best_for_category(category: ProductCategory, profile: SkinProfile, plan: RecommendationPlan, context: UserContext, session: SessionState | None = None, intent: DialogIntent | None = None) -> tuple[RecommendationItem | None, DecisionTraceItem]:
    trace = DecisionTraceItem(requested_category=category)
    candidates = hard_filter_candidates(category, profile, plan, context, session, intent)
    if candidates:
        query_text = build_query_text(profile, plan, context, category, intent)
        ranked = rerank_category(category, profile, plan, context, semantic_retrieve(category, candidates, query_text), session, intent)
        if ranked:
            picked = recommendation_from_scored(ranked[0])
            trace.resolved_category = picked.category
            trace.selected_sku = picked.sku
            return picked, trace
    for fallback in fallback_categories_for(category):
        fallback_candidates = hard_filter_candidates(fallback, profile, plan, context, session, intent)
        if not fallback_candidates:
            continue
        query_text = build_query_text(profile, plan, context, fallback, intent)
        ranked = rerank_category(fallback, profile, plan, context, semantic_retrieve(fallback, fallback_candidates, query_text), session, intent)
        if ranked:
            picked = recommendation_from_scored(ranked[0])
            trace.resolved_category = picked.category
            trace.selected_sku = picked.sku
            trace.fallback_used = True
            trace.fallback_from = category
            return picked, trace
    return None, trace


def build_bundle_recommendations(profile: SkinProfile, plan: RecommendationPlan, context: UserContext, session: SessionState | None = None, intent: DialogIntent | None = None) -> tuple[list[RecommendationItem], DecisionTrace]:
    mode = detect_mode((context.goal or '').lower())
    results: list[RecommendationItem] = []
    seen_categories: set[ProductCategory] = set()
    ordered_categories = dedup_categories([
        *(intent.target_categories if intent and intent.target_categories else ([intent.target_category] if intent and intent.target_category else [])),
        *plan.required_categories,
    ])
    trace = DecisionTrace(mode=mode, requested_categories=ordered_categories)
    for category in ordered_categories:
        picked, item_trace = best_for_category(category, profile, plan, context, session, intent)
        trace.resolved_items.append(item_trace)
        if not picked or picked.category in seen_categories:
            continue
        if intent and intent.target_category == category:
            results.insert(0, picked)
        else:
            results.append(picked)
        seen_categories.add(picked.category)
    return results, trace
