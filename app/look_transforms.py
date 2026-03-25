from __future__ import annotations

from .models import MakeupStyle, OccasionType, UserContext


def apply_look_transform(context: UserContext, transform: str) -> UserContext:
    updated = context.model_copy(deep=True)
    styles = list(updated.preferred_styles)

    def add_style(value: MakeupStyle) -> None:
        if value not in styles:
            styles.append(value)

    if transform == 'transform_evening':
        updated.occasion = OccasionType.party
        add_style(MakeupStyle.glam)
        add_style(MakeupStyle.evening)
    elif transform == 'transform_sexy':
        updated.occasion = updated.occasion or OccasionType.date
        add_style(MakeupStyle.sexy)
        add_style(MakeupStyle.glam)
    elif transform == 'transform_fresh':
        updated.occasion = OccasionType.everyday
        add_style(MakeupStyle.clean_girl)
        add_style(MakeupStyle.natural)
    elif transform == 'transform_soft_luxury':
        updated.occasion = updated.occasion or OccasionType.date
        add_style(MakeupStyle.soft_luxury)
        add_style(MakeupStyle.natural)
    elif transform == 'focus_lips':
        add_style(MakeupStyle.sexy)
    elif transform == 'focus_eyes':
        add_style(MakeupStyle.glam)

    updated.preferred_styles = styles
    return updated


def transformation_label(transform: str) -> str:
    return {
        'transform_evening': 'evening_shift',
        'transform_sexy': 'sexy_shift',
        'transform_fresh': 'fresh_shift',
        'transform_soft_luxury': 'luxury_shift',
        'focus_lips': 'focus_lips',
        'focus_eyes': 'focus_eyes',
    }.get(transform, transform)
