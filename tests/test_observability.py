from pathlib import Path

from app.observability import LOG_FILE, log_event


def test_log_event_writes_json_line() -> None:
    log_event('test_event', sample='ok')
    assert Path(LOG_FILE).exists()
    content = Path(LOG_FILE).read_text(encoding='utf-8')
    assert 'test_event' in content
