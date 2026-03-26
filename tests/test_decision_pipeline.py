from app.decision_pipeline import dedup_categories
from app.models import ProductCategory


def test_dedup_categories_preserves_order() -> None:
    items = [ProductCategory.lipstick, ProductCategory.lipstick, ProductCategory.blush]
    assert dedup_categories(items) == [ProductCategory.lipstick, ProductCategory.blush]
