from app.models import PhotoAnalysisResult, RecommendationPlan, SessionState, SkinProfile, SkinType, UserContext
from app.store import SessionStore


def test_store_save_and_get_roundtrip() -> None:
    store = SessionStore()
    session = SessionState(
        session_id='session-test',
        photo_analysis=PhotoAnalysisResult(),
        skin_profile=SkinProfile(skin_type=SkinType.normal, primary_concerns=[], confidence_overall=0.8),
        current_plan=RecommendationPlan(required_categories=[]),
        user_preferences=UserContext(),
    )
    store.save(session)
    loaded = store.get('session-test')
    assert loaded is not None
    assert loaded.session_id == 'session-test'
