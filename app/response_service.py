from __future__ import annotations

import re

from .catalog import load_catalog
from .look_harmony import build_cta_from_harmony
from .merchandising import bundle_story, cta_for_conversion, selling_frame
from .models import DialogIntent, IntentAction, IntentDomain, ProductCategory, ProductDomain, RecommendationItem, RecommendationPlan, SessionState
from .retrieval import retrieve_products

CATEGORY_LABELS = {
    ProductCategory.cleanser: "очищение",
    ProductCategory.serum: "сыворотка",
    ProductCategory.moisturizer: "крем",
    ProductCategory.spf: "SPF",
    ProductCategory.toner: "тонер",
    ProductCategory.mask: "маска",
    ProductCategory.spot_treatment: "точечный уход",
    ProductCategory.foundation: "тон",
    ProductCategory.skin_tint: "скин тинт",
    ProductCategory.concealer: "консилер",
    ProductCategory.powder: "пудра",
    ProductCategory.lipstick: "помада",
    ProductCategory.lip_tint: "тинт для губ",
    ProductCategory.lip_gloss: "блеск для губ",
    ProductCategory.lip_liner: "карандаш для губ",
    ProductCategory.lip_balm: "бальзам для губ",
    ProductCategory.mascara: "тушь",
    ProductCategory.eyeliner: "подводка",
    ProductCategory.eyeshadow_palette: "палетка теней",
    ProductCategory.brow_pencil: "карандаш для бровей",
    ProductCategory.brow_gel: "гель для бровей",
    ProductCategory.blush: "румяна",
    ProductCategory.bronzer: "бронзер",
    ProductCategory.highlighter: "хайлайтер",
    ProductCategory.contour: "контур",
    ProductCategory.primer: "праймер",
    ProductCategory.setting_spray: "фиксирующий спрей",
    ProductCategory.makeup_remover: "снятие макияжа",
}
CONCERN_LABELS = {
    "redness": "покраснение",
    "breakouts": "высыпания",
    "dryness": "сухость",
    "oiliness": "жирность",
    "maintenance": "поддержание кожи",
    "tone_match": "подбор оттенка",
    "under_eye": "зона под глазами",
}
SKIN_TYPE_LABELS = {
    "dry": "сухой",
    "oily": "жирной",
    "combination": "комбинированной",
    "normal": "нормальной",
    "sensitive": "чувствительной",
}
COVERAGE_LABELS = {
    "sheer": "очень легкое покрытие",
    "light": "легкое покрытие",
    "medium": "среднее покрытие",
    "full": "плотное покрытие",
}
FINISH_LABELS = {
    "radiant": "сияющий финиш",
    "matte": "матовый финиш",
    "natural": "естественный финиш",
    "satin": "сатиновый финиш",
}
COLOR_LABELS = {
    "nude": "нюдовой гамме",
    "pink": "розовой гамме",
    "rose": "розово-нюдовой гамме",
    "coral": "коралловой гамме",
    "berry": "ягодной гамме",
    "red": "красной гамме",
    "brown": "коричневой гамме",
    "peach": "персиковой гамме",
    "bronze": "бронзовой гамме",
    "plum": "сливовой гамме",
    "neutral": "нейтральной гамме",
}


TONE_CTA = {
    "soft_luxury": "Если хочешь, я соберу это ещё более дорого и утончённо по ощущению.",
    "sexy": "Если хочешь, я сразу усилю это в более чувственный и цепляющий вариант.",
    "clean_girl": "Если хочешь, я сделаю это ещё свежее, чище и легче по вайбу.",
    "glam": "Если хочешь, я дожму это в более вечерний и эффектный образ.",
    "default": "Если хочешь, я могу сразу сделать этот образ более вечерним, более сексуальным или более бюджетным.",
}

SHORT_REASON_TEMPLATES = {
    ProductCategory.primer: "сделает тон визуально ровнее и аккуратнее",
    ProductCategory.foundation: "даст более дорогой и собранный тон лица",
    ProductCategory.skin_tint: "освежит лицо без тяжёлого слоя",
    ProductCategory.concealer: "быстро соберёт зону под глазами и мелкие несовершенства",
    ProductCategory.powder: "поможет макияжу выглядеть чище в течение дня",
    ProductCategory.blush: "сразу добавит лицу живость и свежесть",
    ProductCategory.mascara: "раскроет взгляд за пару движений",
    ProductCategory.lipstick: "даст образу завершённость и настроение",
    ProductCategory.lip_tint: "даст свежий и более молодой эффект",
    ProductCategory.lip_gloss: "сделает образ более сочным и притягательным",
    ProductCategory.eyeshadow_palette: "поможет быстро усилить образ на вечер",
    ProductCategory.eyeliner: "добавит взгляду остроту и характер",
    ProductCategory.brow_gel: "соберёт лицо и сделает макияж аккуратнее",
    ProductCategory.highlighter: "добавит коже дорогого свечения",
    ProductCategory.setting_spray: "поможет образу дольше выглядеть свежо",
}


def humanize_shade_token(value: str) -> str:
    parts = value.replace("-", "_").split("_")
    mapping = {
        "fair": "очень светлый",
        "light": "светлый",
        "medium": "средний",
        "tan": "загорелый",
        "deep": "глубокий",
        "neutral": "нейтральный",
        "warm": "тёплый",
        "cool": "холодный",
        "olive": "оливковый",
        "rose": "розовый",
        "nude": "нюдовый",
        "coral": "коралловый",
        "plum": "сливовый",
        "bronze": "бронзовый",
        "pink": "розовый",
        "champagne": "шампань",
        "taupe": "тауповый",
        "peach": "персиковый",
    }
    human = [mapping.get(part.lower(), part.lower()) for part in parts if part]
    return " ".join(human).strip()


def pretty_product_title(title: str) -> str:
    match = re.search(r"\b([A-Z]+(?:_[A-Z]+)+)\b", title)
    if not match:
        return title
    shade = match.group(1)
    human_shade = humanize_shade_token(shade)
    return title.replace(shade, human_shade)


def sanitize_agent_text(text: str) -> str:
    cleaned = text.replace("**", "").replace("__", "")
    cleaned = re.sub(r"(?m)^\s*#{1,6}\s*", "", cleaned)
    cleaned = re.sub(r"`+", "", cleaned)
    cleaned = re.sub(r"^(?:привет|здравствуй|здравствуйте|рада тебя видеть снова|рада тебя видеть|рада, что ты заглянула|рада, что ты вернулась)[!, .\s]*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s+", "", cleaned)
    return cleaned.strip()


def _pick_highlight_line(item: RecommendationItem) -> str:
    title = pretty_product_title(item.title)
    reason = SHORT_REASON_TEMPLATES.get(item.category, "хорошо встанет в образ")
    return f"- {CATEGORY_LABELS.get(item.category, item.category.value).capitalize()}: {title} — {reason}."


def _style_mode(session_or_profile) -> str:
    styles = []
    if hasattr(session_or_profile, 'makeup_profile'):
        styles = getattr(session_or_profile.makeup_profile, 'preferred_styles', []) or []
    elif hasattr(session_or_profile, 'skin_profile'):
        styles = getattr(session_or_profile.skin_profile.makeup_profile, 'preferred_styles', []) or []
    values = [style.value if hasattr(style, 'value') else str(style) for style in styles]
    if 'sexy' in values:
        return 'sexy'
    if 'soft_luxury' in values:
        return 'soft_luxury'
    if 'glam' in values or 'evening' in values:
        return 'glam'
    if 'clean_girl' in values:
        return 'clean_girl'
    return 'default'


def _opening_line(profile) -> str:
    mode = _style_mode(profile)
    if mode == 'soft_luxury':
        return 'Я бы собирал это в более дорогой, ухоженный и quietly luxurious образ — без лишнего шума.'
    if mode == 'sexy':
        return 'Я бы собирал это так, чтобы образ сразу цеплял: более выразительно, притягательно и с правильным акцентом.'
    if mode == 'glam':
        return 'Я бы сразу двигал это в более эффектный и заметный образ, который хорошо держит внимание.'
    if mode == 'clean_girl':
        return 'Я бы собирал это в очень свежий, чистый и дорогой на вид образ — легко, но с эффектом.'
    return 'Я бы собирал образ так, чтобы лицо сразу выглядело свежее, дороже и выразительнее — без перегруза.'


def compose_initial_response(profile, recommendations: list[RecommendationItem], plan: RecommendationPlan) -> str:
    lines = [_opening_line(profile)]
    hero, support = bundle_story(recommendations)
    if hero:
        lines.append(f"Я бы начал с главного акцента: {_pick_highlight_line(hero)[2:]}")
    if support:
        lines.append('Чтобы образ выглядел цельно, я бы добавил к нему:')
        for item in support:
            lines.append(_pick_highlight_line(item))
    elif recommendations:
        for item in recommendations[1:4]:
            lines.append(_pick_highlight_line(item))
    lines.append('Если хочешь, я могу сразу дособрать это в готовый комплект под день, вечер или более дорогой вайб.')
    return '\n'.join(lines)


def build_reply_prompt(session: SessionState, intent: DialogIntent, recommendations: list[RecommendationItem], message: str) -> str:
    rec_lines = "\n".join(f"- {pretty_product_title(item.title)} | brand={item.brand} | category={item.category.value} | price={item.price_value} | why={item.why}" for item in recommendations[:3])
    mode = _style_mode(session)
    return f"""
Ты — сильный beauty-консультант в стиле премиального ритейла Golden Apple.
Отвечай по-русски.
Текущий retail-tone mode: {mode}.
КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ:
- НЕЛЬЗЯ придумывать бренды, товары, SKU, линейки, текстуры или продукты, которых нет в списке ниже.
- Можно упоминать ТОЛЬКО продукты из блока ПОДБОРКА.
- Если в подборке 1 продукт — говори только о нём и о следующем шаге, не выдумывай дополнительные товары.
- Нельзя уводить пользователя в другой домен без фактической подборки.
- Нельзя советовать новые бренды "от себя".
ФОРМАТ ОТВЕТА:
- максимум 3 коротких абзаца
- максимум 2-3 продукта в тексте
- без длинных редакторских вступлений
- без сухой диагностики
- без markdown-звёздочек и заголовков
ЗАДАЧА:
- коротко продать текущую подборку
- объяснить эффект образа
- закончить мягким следующим шагом
Если запрос на compare — сравни только товары из подборки.
Если запрос на explain — объясни только товары из подборки.
Сообщение пользователя: {message}
Action={intent.action.value}; domain={intent.domain.value}; target={intent.target_category.value if intent.target_category else ''};
ПОДБОРКА:
{rec_lines}
""".strip()


def pick_label(values: list[str], labels: dict[str, str]) -> str | None:
    for value in values:
        label = labels.get(value)
        if label:
            return label
    return None


def describe_item(item: RecommendationItem, session: SessionState) -> str:
    catalog = {product.sku: product for product in load_catalog()}
    product = catalog.get(item.sku)
    if not product:
        return item.why
    bits: list[str] = []
    if product.domain == ProductDomain.makeup:
        finish = pick_label(product.finishes, FINISH_LABELS)
        color = pick_label(product.color_families, COLOR_LABELS)
        if finish:
            bits.append(finish)
        if color:
            bits.append(f"в {color}")
        if product.longwear and "longwear" in session.current_plan.preferred_tags:
            bits.append("с хорошей стойкостью")
    else:
        if "soothing" in product.tags:
            bits.append("работает мягко")
        if "non-comedogenic" in product.tags:
            bits.append("не должен перегружать кожу")
    details = ", ".join(bits[:2])
    return details or item.why


def find_item_for_category(session: SessionState, recommendations: list[RecommendationItem], category: ProductCategory) -> RecommendationItem | None:
    for item in recommendations:
        if item.category == category:
            return item
    sku = session.dialog_context.current_recommendations.get(category)
    if not sku:
        return None
    product = next((product for product in load_catalog() if product.sku == sku), None)
    if not product:
        return None
    return RecommendationItem(
        sku=product.sku,
        title=product.title,
        brand=product.brand,
        category=product.category,
        domain=product.domain,
        price_segment=product.price_segment,
        price_value=product.price_value,
        why="текущий вариант",
        vector_score=0.0,
        rule_score=0.0,
        final_score=0.0,
    )


def alternative_for_category(session: SessionState, category: ProductCategory, intent: DialogIntent) -> RecommendationItem | None:
    alt_intent = DialogIntent(
        intent="replace_product",
        action=IntentAction.replace,
        domain=intent.domain,
        target_category=category,
        target_categories=[category],
        confidence=0.4,
    )
    alt = retrieve_products(session.skin_profile, session.current_plan, session.user_preferences, session=session, intent=alt_intent)
    for item in alt:
        if item.category == category:
            return item
    return None


def compose_compare_response(session: SessionState, intent: DialogIntent, recommendations: list[RecommendationItem]) -> str:
    target_categories = intent.target_categories or ([intent.target_category] if intent.target_category else [])
    items: list[RecommendationItem] = []
    if target_categories:
        for category in target_categories:
            item = find_item_for_category(session, recommendations, category)
            if item:
                items.append(item)
    else:
        items = recommendations[:2]
    if len(target_categories) == 1:
        alt = alternative_for_category(session, target_categories[0], intent)
        if alt:
            items.append(alt)
    if len(items) < 2:
        return "Сейчас не из чего собрать честное сравнение. Скажи, что сравнить — например две помады или два варианта для глаз."
    first, second = items[:2]
    return (
        f"{pretty_product_title(first.title)} — даёт более собранный и выразительный эффект.\n"
        f"{pretty_product_title(second.title)} — смотрится мягче и спокойнее.\n"
        f"Если хочешь, я сразу скажу, какой из них выгоднее именно под твой запрос."
    )


def compose_explain_response(session: SessionState, intent: DialogIntent, recommendations: list[RecommendationItem]) -> str:
    target = intent.target_category or (intent.target_categories[0] if intent.target_categories else None)
    focus = find_item_for_category(session, recommendations, target) if target else (recommendations[0] if recommendations else None)
    if not focus:
        return "Скажи, какой именно продукт разобрать — я коротко объясню, почему он работает в образе."
    pretty_title = pretty_product_title(focus.title)
    return (
        f"{pretty_title} здесь работает очень внятно: он сразу делает образ более собранным и выигрышным.\n"
        f"По ощущению результата — {describe_item(focus, session)}.\n"
        f"Если хочешь, я сразу подберу к нему ещё 1-2 вещи, чтобы добить образ."
    )


def compose_followup_response(session: SessionState, intent: DialogIntent, recommendations: list[RecommendationItem], message: str) -> str:
    if intent.action == IntentAction.compare:
        return compose_compare_response(session, intent, recommendations)
    if intent.action == IntentAction.explain:
        return compose_explain_response(session, intent, recommendations)

    preface = {
        "cheaper_alternative": "Нашёл более доступный вариант, который всё ещё выглядит вкусно и не дешево по ощущению.",
        "replace_product": "Вот версия, которая выглядит выигрышнее и современнее.",
        "exclude_ingredient": "Пересобрал подборку так, чтобы сохранить эффект, но убрать лишнее ограничение из состава.",
        "simplify_routine": "Собрал более лёгкую версию — чтобы выглядело дорого, но без лишних шагов.",
        "build_full_look": "Вот образ, который уже ощущается более цельным, собранным и привлекательным.",
        "add_category": "Добавил ещё один штрих, который делает образ заметно живее и интереснее.",
        "general_advice": "Вот вариант, который сейчас выглядит особенно удачно.",
    }.get(intent.intent, "Подборку обновил.")

    lines = [preface]
    visible_items = []
    for item in recommendations[:4]:
        if intent.target_category and intent.action in {IntentAction.replace, IntentAction.cheaper} and item.category != intent.target_category:
            continue
        visible_items.append(item)
    hero, support = bundle_story(visible_items)
    if hero:
        lines.append(f"Главный ход здесь — {_pick_highlight_line(hero)[2:]}")
    for item in support:
        lines.append(_pick_highlight_line(item))
    if not support:
        for item in visible_items[1:3]:
            lines.append(_pick_highlight_line(item))
    for frame_line in selling_frame(visible_items, session.current_plan, session.user_preferences):
        lines.append(frame_line)
    harmony_cta = build_cta_from_harmony(session.dialog_context.look_profile) if session.dialog_context.look_profile else TONE_CTA.get(_style_mode(session), TONE_CTA['default'])
    lines.append(cta_for_conversion(session.current_plan, session.user_preferences))
    lines.append(harmony_cta)
    return "\n".join(lines)
