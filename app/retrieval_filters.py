from __future__ import annotations

from .catalog import load_catalog
from .models import DialogIntent, PriceSegment, ProductCategory, ProductDomain, RecommendationPlan, SessionState, SkinProfile, UserContext

PRICE_ORDER = {
    PriceSegment.budget: 0,
    PriceSegment.mid: 1,
    PriceSegment.premium: 2,
}
MAKEUP_CATEGORIES = {
    ProductCategory.foundation, ProductCategory.skin_tint, ProductCategory.concealer, ProductCategory.powder,
    ProductCategory.lipstick, ProductCategory.lip_tint, ProductCategory.lip_gloss, ProductCategory.lip_liner, ProductCategory.lip_balm,
    ProductCategory.mascara, ProductCategory.eyeliner, ProductCategory.eyeshadow_palette, ProductCategory.brow_pencil, ProductCategory.brow_gel,
    ProductCategory.blush, ProductCategory.bronzer, ProductCategory.highlighter, ProductCategory.contour,
    ProductCategory.primer, ProductCategory.setting_spray,
}


def get_current_selection_map(session: SessionState | None) -> dict[ProductCategory, str]:
    if not session:
        return {}
    current = session.dialog_context.current_recommendations
    return dict(current) if current else {}


def budget_allows(product, budget: PriceSegment, intent: DialogIntent | None, current_product) -> bool:
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


def domain_for_category(category: ProductCategory) -> ProductDomain:
    return ProductDomain.makeup if category in MAKEUP_CATEGORIES else ProductDomain.skincare


def hard_filter_candidates(
    category: ProductCategory,
    profile: SkinProfile,
    plan: RecommendationPlan,
    context: UserContext,
    session: SessionState | None,
    intent: DialogIntent | None,
):
    current_selection = get_current_selection_map(session)
    current_product = next((p for p in load_catalog() if p.sku == current_selection.get(category)), None)
    candidates = []
    excluded_ingredients = {item.lower() for item in context.excluded_ingredients}
    rejected = set(session.rejected_products if session else [])
    category_domain = domain_for_category(category)

    for product in load_catalog():
        if product.category != category or not product.availability:
            continue
        if product.domain != category_domain:
            continue
        if plan.product_domains and product.domain not in plan.product_domains:
            continue
        if not budget_allows(product, context.budget_segment, intent if intent and intent.target_category == category else None, current_product):
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
            if plan.preferred_color_families and product.color_families and not set(plan.preferred_color_families).intersection(product.color_families):
                continue
            if plan.preferred_styles and product.styles and not set(plan.preferred_styles).intersection(product.styles):
                continue
            if context.occasion and product.occasions and context.occasion.value not in product.occasions:
                continue
            if "longwear" in plan.preferred_tags and product.longwear is False and category in {ProductCategory.lipstick, ProductCategory.eyeliner, ProductCategory.setting_spray, ProductCategory.foundation}:
                continue
            if category == ProductCategory.concealer and profile.complexion.needs_under_eye_concealer and product.suitable_areas and "under_eye" not in product.suitable_areas:
                continue
        candidates.append(product)
    return candidates
