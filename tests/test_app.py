from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_analyze_makeup_and_followup() -> None:
    analyze = client.post('/v1/photo/analyze', json={
        'image_url': 'https://example.com/photo.jpg',
        'user_context': {
            'budget_segment': 'mid',
            'preferred_brands': [],
            'excluded_ingredients': [],
            'routine_size': 'standard',
            'goal': 'подбери тональник под мой тон кожи, хочу лёгкое покрытие и сияющий финиш'
        }
    })
    assert analyze.status_code == 200
    body = analyze.json()
    assert body['session_id']
    assert body['recommendations']
    assert any(item['category'] in {'foundation', 'skin_tint'} for item in body['recommendations'])

    session_id = body['session_id']
    followup = client.post(f'/v1/session/{session_id}/message', json={'message': 'нужен консилер под глаза'})
    assert followup.status_code == 200
    follow = followup.json()
    assert follow['intent']['action'] == 'recommend'
    assert follow['intent']['target_category'] == 'concealer'
    assert any(x['category'] == 'concealer' for x in follow['recommendations'])


def test_compare_and_explain_modes() -> None:
    analyze = client.post('/v1/photo/analyze', json={
        'image_url': 'https://example.com/compare.jpg',
        'user_context': {
            'budget_segment': 'mid',
            'preferred_brands': [],
            'excluded_ingredients': [],
            'routine_size': 'standard',
            'goal': 'хочу тональный и консилер с естественным финишем'
        }
    })
    session_id = analyze.json()['session_id']

    compare_resp = client.post(f'/v1/session/{session_id}/message', json={'message': 'сравни foundation и concealer'})
    assert compare_resp.status_code == 200
    compare_data = compare_resp.json()
    assert compare_data['intent']['action'] == 'compare'
    assert compare_data['intent']['domain'] == 'makeup'
    assert compare_data['answer_text']
    assert len(compare_data['answer_text']) > 20

    explain_resp = client.post(f'/v1/session/{session_id}/message', json={'message': 'объясни почему этот консилер подходит'})
    assert explain_resp.status_code == 200
    explain_data = explain_resp.json()
    assert explain_data['intent']['action'] == 'explain'
    assert explain_data['answer_text']
    assert len(explain_data['answer_text']) > 20


def test_mixed_domain_memory_and_preference_updates() -> None:
    analyze = client.post('/v1/photo/analyze', json={
        'image_url': 'https://example.com/hybrid.jpg',
        'user_context': {
            'budget_segment': 'mid',
            'preferred_brands': [],
            'excluded_ingredients': [],
            'routine_size': 'standard',
            'goal': 'build a skincare routine and pick a skin tint'
        }
    })
    session_id = analyze.json()['session_id']
    response = client.post(
        f'/v1/session/{session_id}/message',
        json={'message': 'make the routine minimal but keep skin tint, I want matte finish and no niacinamide'}
    )
    assert response.status_code == 200
    data = response.json()
    assert data['intent']['domain'] == 'hybrid'
    assert data['updated_session_state']['user_preferences']['routine_size'] == 'minimal'
    assert data['updated_session_state']['user_preferences']['excluded_ingredients'] == ['niacinamide']
    assert data['updated_session_state']['user_preferences']['preferred_finish'] == ['matte']
