from __future__ import annotations

from dataclasses import dataclass

from .catalog import load_catalog
from .look_harmony import harmony_bonus
from .models import DialogIntent, PriceSegment, ProductCategory, ProductDomain, RecommendationPlan, SessionState, SkinProfile, UserContext
from .retrieval_filters import PRICE_ORDER, get_current_selection_map


@dataclass(slots=True)
class RetrievalScoredItem:
    product: object
    vector_score: float
    rule_score: float
    rerank_score: float
    why: str


def rerank_category(
    category: ProductCategory,
    profile: SkinProfile,
    plan: RecommendationPlan,
    context: UserContext,
    semantic_hits,
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
        color_hits = len(set(plan.preferred_color_families) & set(product.color_families))
        style_hits = len(set(plan.preferred_styles) & set(product.styles))
        occasion_hit = 1 if context.occasion and context.occasion.value in product.occasions else 0
        skin_bonus = 0.12 if product.domain == ProductDomain.skincare and profile.skin_type.value in product.skin_types else 0.05
        if product.price_segment == context.budget_segment:
            budget_bonus = 0.18 if context.budget_segment == PriceSegment.premium else 0.14
        elif PRICE_ORDER[product.price_segment] < PRICE_ORDER[context.budget_segment]:
            budget_bonus = 0.02 if context.budget_segment == PriceSegment.premium else 0.06
        else:
            budget_bonus = 0.0
        complexion_bonus = 0.0
        beauty_bonus = 0.0
        followup_bonus = 0.0
        novelty_penalty = 0.0

        if product.domain == ProductDomain.makeup:
            complexion_bonus += tone_hits * 0.12
            complexion_bonus += undertone_hits * 0.12
            complexion_bonus += finish_hits * 0.1
            complexion_bonus += coverage_hits * 0.08
            beauty_bonus += color_hits * 0.1
            beauty_bonus += style_hits * 0.08
            beauty_bonus += occasion_hit * 0.08
            if product.longwear and "longwear" in plan.preferred_tags:
                beauty_bonus += 0.08
            if category == ProductCategory.concealer and "under_eye" in product.suitable_areas:
                complexion_bonus += 0.08
            if plan.look_strategy == "sensual":
                if category in {ProductCategory.lipstick, ProductCategory.eyeliner, ProductCategory.mascara}:
                    beauty_bonus += 0.1
                if category == ProductCategory.lip_tint:
                    beauty_bonus -= 0.03
            if plan.look_strategy == "soft_luxury":
                if category in {ProductCategory.primer, ProductCategory.foundation, ProductCategory.blush, ProductCategory.highlighter}:
                    beauty_bonus += 0.09
            if plan.look_strategy == "fresh":
                if category in {ProductCategory.skin_tint, ProductCategory.blush, ProductCategory.lip_tint, ProductCategory.brow_gel}:
                    beauty_bonus += 0.09
            if plan.accent_balance == "feature_focus":
                if "lips" in plan.focus_features and category in {ProductCategory.lipstick, ProductCategory.lip_gloss, ProductCategory.lip_liner}:
                    beauty_bonus += 0.08
                if "eyes" in plan.focus_features and category in {ProductCategory.mascara, ProductCategory.eyeliner, ProductCategory.eyeshadow_palette}:
                    beauty_bonus += 0.08
                if "cheeks" in plan.focus_features and category in {ProductCategory.blush, ProductCategory.highlighter, ProductCategory.contour}:
                    beauty_bonus += 0.08
        if current_product and intent and intent.target_category == category:
            if intent.intent == "cheaper_alternative":
                followup_bonus += 0.18 if product.price_value < current_product.price_value else -0.2
            if intent.intent == "replace_product":
                overlap = len(set(product.tags) & set(current_product.tags)) + len(set(product.concerns) & set(current_product.concerns))
                followup_bonus += 0.06 * overlap
        if session and session.dialog_context.look_profile:
            beauty_bonus += harmony_bonus(category, product, session.dialog_context.look_profile)
        if product.sku in shown:
            novelty_penalty += 0.16
        if product.sku in accepted:
            followup_bonus += 0.08

        rule_score = min(1.0, 0.24 + concern_hits * 0.18 + tag_hits * 0.11 + skin_bonus + budget_bonus + complexion_bonus + beauty_bonus)
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
            if color_hits:
                why_bits.append("попадает в нужную цветовую гамму")
            if style_hits:
                why_bits.append("совпадает по стилю макияжа")
            if occasion_hit:
                why_bits.append("подходит под нужный сценарий")
            if product.longwear and "longwear" in plan.preferred_tags:
                why_bits.append("должен держаться дольше обычного")
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
        ranked.append(
            RetrievalScoredItem(
                product=product,
                vector_score=round(vector_score, 4),
                rule_score=round(rule_score, 4),
                rerank_score=rerank_score,
                why=", ".join(dict.fromkeys(why_bits)) or "подходит по профилю и логике подбора",
            )
        )
    ranked.sort(key=lambda item: (item.rerank_score, item.vector_score, -item.product.price_value), reverse=True)
    return ranked
