from __future__ import annotations

from .models import ProductCategory, RecommendationItem, RecommendationPlan, UserContext

HERO_PRIORITY = {
    ProductCategory.lipstick: 100,
    ProductCategory.foundation: 95,
    ProductCategory.skin_tint: 92,
    ProductCategory.eyeshadow_palette: 90,
    ProductCategory.blush: 86,
    ProductCategory.mascara: 84,
    ProductCategory.concealer: 82,
    ProductCategory.primer: 78,
    ProductCategory.lip_tint: 77,
    ProductCategory.highlighter: 76,
    ProductCategory.eyeliner: 74,
    ProductCategory.powder: 66,
    ProductCategory.brow_gel: 60,
    ProductCategory.setting_spray: 58,
}

BUNDLE_SUPPORT = {
    ProductCategory.foundation: [ProductCategory.concealer, ProductCategory.blush, ProductCategory.setting_spray],
    ProductCategory.skin_tint: [ProductCategory.blush, ProductCategory.brow_gel, ProductCategory.lip_tint],
    ProductCategory.lipstick: [ProductCategory.blush, ProductCategory.mascara, ProductCategory.highlighter],
    ProductCategory.eyeshadow_palette: [ProductCategory.mascara, ProductCategory.eyeliner, ProductCategory.lip_gloss],
    ProductCategory.blush: [ProductCategory.highlighter, ProductCategory.lip_tint, ProductCategory.brow_gel],
}


def hero_score(item: RecommendationItem, plan: RecommendationPlan, context: UserContext) -> float:
    score = HERO_PRIORITY.get(item.category, 40)
    score += item.final_score * 20
    if plan.look_strategy == 'sensual' and item.category in {ProductCategory.lipstick, ProductCategory.eyeliner, ProductCategory.mascara}:
        score += 12
    if plan.look_strategy == 'soft_luxury' and item.category in {ProductCategory.foundation, ProductCategory.primer, ProductCategory.blush, ProductCategory.highlighter}:
        score += 10
    if plan.look_strategy == 'fresh' and item.category in {ProductCategory.skin_tint, ProductCategory.blush, ProductCategory.lip_tint}:
        score += 10
    if context.budget_segment.value == 'premium' and item.price_segment.value == 'premium':
        score += 5
    return score


def order_for_conversion(items: list[RecommendationItem], plan: RecommendationPlan, context: UserContext) -> list[RecommendationItem]:
    if not items:
        return []
    ordered = sorted(items, key=lambda item: hero_score(item, plan, context), reverse=True)
    hero = ordered[0]
    support_order = BUNDLE_SUPPORT.get(hero.category, [])
    support_rank = {category: idx for idx, category in enumerate(support_order)}
    rest = ordered[1:]
    rest.sort(key=lambda item: (support_rank.get(item.category, 999), -item.final_score))
    return [hero, *rest]


def bundle_story(items: list[RecommendationItem]) -> tuple[RecommendationItem | None, list[RecommendationItem]]:
    if not items:
        return None, []
    return items[0], items[1:3]


def cta_for_conversion(plan: RecommendationPlan, context: UserContext) -> str:
    if context.budget_segment.value == 'premium':
        return 'Если хочешь, я соберу ещё более дорогую и эффектную версию без потери баланса.'
    if plan.look_strategy == 'sensual':
        return 'Если хочешь, я сразу доберу к этому ещё 1-2 вещи, чтобы образ сильнее цеплял.'
    if plan.look_strategy == 'soft_luxury':
        return 'Если хочешь, я дособеру это в более polished и premium-looking комплект.'
    if plan.look_strategy == 'fresh':
        return 'Если хочешь, я доберу к этому ещё пару лёгких штрихов, чтобы образ выглядел ещё свежее.'
    return 'Если хочешь, я сразу дособеру к этому ещё 1-2 вещи, чтобы образ выглядел полностью готовым.'


def one_best_pick(items: list[RecommendationItem]) -> RecommendationItem | None:
    return items[0] if items else None


def vibe_alternative(items: list[RecommendationItem]) -> RecommendationItem | None:
    return items[1] if len(items) > 1 else None


def entry_bundle(items: list[RecommendationItem]) -> list[RecommendationItem]:
    return items[:3]


def selling_frame(items: list[RecommendationItem], plan: RecommendationPlan, context: UserContext) -> list[str]:
    lines: list[str] = []
    best = one_best_pick(items)
    alt = vibe_alternative(items)
    bundle = entry_bundle(items)
    if best:
        lines.append(f"Если брать один продукт для быстрого вау-эффекта, я бы начал с {best.title}.")
    if alt and alt.category != best.category:
        lines.append(f"Если хочется похожий вайб, но в другом ключе, можно смотреть ещё на {alt.title}.")
    if len(bundle) >= 2:
        lines.append("Самый лёгкий вход в образ сейчас — взять главный продукт и добрать к нему ещё 1-2 поддерживающих шага.")
    if context.budget_segment.value == 'budget':
        lines.append('Если хочешь, я могу сразу оставить только те позиции, которые дают максимум эффекта за минимум денег.')
    if plan.look_strategy == 'soft_luxury':
        lines.append('Здесь особенно хорошо работает логика polished minimum: меньше продуктов, но каждый делает лицо визуально дороже.')
    return lines
