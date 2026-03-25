from app.look_transforms import apply_look_transform, transformation_label
from app.models import MakeupStyle, OccasionType, UserContext


def test_apply_look_transform_evening_sets_party() -> None:
    context = UserContext()
    updated = apply_look_transform(context, 'transform_evening')
    assert updated.occasion == OccasionType.party
    assert MakeupStyle.glam in updated.preferred_styles


def test_apply_look_transform_soft_luxury_adds_style() -> None:
    context = UserContext()
    updated = apply_look_transform(context, 'transform_soft_luxury')
    assert MakeupStyle.soft_luxury in updated.preferred_styles


def test_transformation_label_focus_lips() -> None:
    assert transformation_label('focus_lips') == 'focus_lips'
