from app.intent_service import detect_action, detect_categories, detect_domain, extract_constraint_updates, extract_preference_updates, heuristic_intent
from app.models import IntentAction, IntentDomain, ProductCategory


def test_detect_categories_handles_mixed_query() -> None:
    categories = detect_categories('сначала подбери уход, потом skin tint и консилер под глаза')
    assert ProductCategory.skin_tint in categories
    assert ProductCategory.concealer in categories


def test_detect_domain_returns_hybrid_for_mixed_request() -> None:
    domain = detect_domain('нужен уход и тональник с лёгким покрытием')
    assert domain == IntentDomain.hybrid


def test_detect_action_handles_compare() -> None:
    assert detect_action('сравни foundation и skin tint') == IntentAction.compare


def test_extract_preference_updates_reads_finish_and_routine_size() -> None:
    updates = extract_preference_updates('хочу matte finish и minimal routine')
    assert updates['preferred_finish'] == ['matte']
    assert updates['routine_size'] == 'minimal'


def test_extract_constraint_updates_reads_excluded_ingredient() -> None:
    updates = extract_constraint_updates('без niacinamide')
    assert updates['excluded_ingredients'] == ['niacinamide']


def test_heuristic_intent_sets_target_category() -> None:
    intent = heuristic_intent('подбери консилер под глаза')
    assert intent.target_category == ProductCategory.concealer
    assert intent.domain == IntentDomain.makeup
