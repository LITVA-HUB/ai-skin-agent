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
    assert body['skin_profile']['primary_concerns']
    assert body['skin_profile']['complexion']['skin_tone'] is not None
    assert any(item['category'] in {'foundation', 'skin_tint'} for item in body['recommendations'])

    session_id = body['session_id']
    followup = client.post(f'/v1/session/{session_id}/message', json={'message': 'нужен консилер под глаза'})
    assert followup.status_code == 200
    follow = followup.json()
    assert follow['intent']['intent'] == 'general_advice'
    assert follow['intent']['target_category'] == 'concealer'
    concealer_items = [x for x in follow['recommendations'] if x['category'] == 'concealer']
    assert concealer_items



def test_exclude_ingredient_in_skincare_followup() -> None:
    analyze = client.post('/v1/photo/analyze', json={
        'image_url': 'https://example.com/2.jpg',
        'user_context': {
            'budget_segment': 'mid',
            'preferred_brands': [],
            'excluded_ingredients': [],
            'routine_size': 'standard',
            'goal': 'сделай уход помягче для комбинированной кожи'
        }
    })
    session_id = analyze.json()['session_id']
    followup = client.post(f'/v1/session/{session_id}/message', json={'message': 'сыворотка без niacinamide'})
    assert followup.status_code == 200
    data = followup.json()
    assert data['intent']['intent'] == 'exclude_ingredient'
