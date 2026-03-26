from app.config import validate_settings


def test_validate_settings_returns_list() -> None:
    errors = validate_settings()
    assert isinstance(errors, list)
