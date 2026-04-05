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
            'goal': 'pick foundation for my skin tone, want light coverage and radiant finish'
        }
    })
    assert analyze.status_code == 200
    body = analyze.json()
    assert body['session_id']
    assert body['recommendations']
    assert any(item['category'] in {'foundation', 'skin_tint'} for item in body['recommendations'])

    session_id = body['session_id']
    followup = client.post(f'/v1/session/{session_id}/message', json={'message': 'need concealer under eye'})
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
            'goal': 'want foundation and concealer with a natural finish'
        }
    })
    session_id = analyze.json()['session_id']

    compare_resp = client.post(f'/v1/session/{session_id}/message', json={'message': 'compare foundation and concealer'})
    assert compare_resp.status_code == 200
    compare_data = compare_resp.json()
    assert compare_data['intent']['action'] == 'compare'
    assert compare_data['intent']['domain'] == 'makeup'
    assert compare_data['answer_text']
    assert len(compare_data['answer_text']) > 20

    explain_resp = client.post(f'/v1/session/{session_id}/message', json={'message': 'explain why this concealer works'})
    assert explain_resp.status_code == 200
    explain_data = explain_resp.json()
    assert explain_data['intent']['action'] == 'explain'
    assert explain_data['answer_text']
    assert len(explain_data['answer_text']) > 20


def test_cart_flow_add_update_remove() -> None:
    analyze = client.post('/v1/photo/analyze', json={
        'image_url': 'https://example.com/cart.jpg',
        'user_context': {
            'budget_segment': 'mid',
            'preferred_brands': [],
            'excluded_ingredients': [],
            'routine_size': 'standard',
            'goal': 'pick foundation for my skin tone'
        }
    })
    assert analyze.status_code == 200
    body = analyze.json()
    session_id = body['session_id']
    product = body['recommendations'][0]

    add_resp = client.post(f'/v1/session/{session_id}/cart/items', json={
        'sku': product['sku'],
        'title': product['title'],
        'brand': product['brand'],
        'category': product['category'],
        'domain': product['domain'],
        'price_value': product['price_value'],
    })
    assert add_resp.status_code == 200
    add_data = add_resp.json()
    assert add_data['total_items'] == 1
    assert add_data['total_price'] == product['price_value']

    patch_resp = client.patch(f"/v1/session/{session_id}/cart/items/{product['sku']}", json={'quantity': 3})
    assert patch_resp.status_code == 200
    patch_data = patch_resp.json()
    assert patch_data['total_items'] == 3
    assert patch_data['total_price'] == product['price_value'] * 3

    delete_resp = client.delete(f"/v1/session/{session_id}/cart/items/{product['sku']}")
    assert delete_resp.status_code == 200
    delete_data = delete_resp.json()
    assert delete_data['total_items'] == 0
    assert delete_data['total_price'] == 0



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


def test_hybrid_domain_from_goal() -> None:
    analyze = client.post('/v1/photo/analyze', json={
        'image_url': 'https://example.com/3.jpg',
        'user_context': {
            'budget_segment': 'mid',
            'preferred_brands': [],
            'excluded_ingredients': [],
            'routine_size': 'standard',
            'goal': 'want skincare routine and foundation with light coverage'
        }
    })
    assert analyze.status_code == 200
    data = analyze.json()
    assert set(data['recommendation_plan']['product_domains']) == {'skincare', 'makeup'}
    categories = {item['category'] for item in data['recommendations']}
    assert {'cleanser', 'moisturizer', 'spf', 'foundation'}.issubset(categories)



def test_session_stores_raw_conversation_turns() -> None:
    analyze = client.post('/v1/photo/analyze', json={
        'image_url': 'https://example.com/memory-store.jpg',
        'user_context': {
            'budget_segment': 'mid',
            'preferred_brands': [],
            'excluded_ingredients': [],
            'routine_size': 'standard',
            'goal': 'pick skincare routine and skin tint'
        }
    })
    session_id = analyze.json()['session_id']

    followup = client.post(f'/v1/session/{session_id}/message', json={'message': 'сделай подборку дешевле'})
    assert followup.status_code == 200
    history = followup.json()['updated_session_state']['conversation_history']

    assert len(history) >= 3
    assert history[0]['role'] == 'assistant'
    assert history[1]['role'] == 'user'
    assert history[1]['message'] == 'сделай подборку дешевле'
    assert history[2]['role'] == 'assistant'
    assert history[2]['message']



def test_conversation_memory_recall_uses_session_history() -> None:
    analyze = client.post('/v1/photo/analyze', json={
        'image_url': 'https://example.com/memory-recall.jpg',
        'user_context': {
            'budget_segment': 'mid',
            'preferred_brands': [],
            'excluded_ingredients': [],
            'routine_size': 'standard',
            'goal': 'pick foundation for my skin tone'
        }
    })
    session_id = analyze.json()['session_id']

    client.post(f'/v1/session/{session_id}/message', json={'message': 'подбери консилер под глаза'})
    client.post(f'/v1/session/{session_id}/message', json={'message': 'сделай вариант подешевле'})
    recall = client.post(f'/v1/session/{session_id}/message', json={'message': 'что я у тебя спрашивал?'})

    assert recall.status_code == 200
    data = recall.json()
    assert data['intent']['intent'] == 'conversation_memory'
    assert 'подбери консилер под глаза' in data['answer_text']
    assert 'сделай вариант подешевле' in data['answer_text']
    assert 'что я у тебя спрашивал?' not in data['answer_text']



def test_conversation_memory_recall_previous_selection() -> None:
    analyze = client.post('/v1/photo/analyze', json={
        'image_url': 'https://example.com/memory-selection.jpg',
        'user_context': {
            'budget_segment': 'mid',
            'preferred_brands': [],
            'excluded_ingredients': [],
            'routine_size': 'standard',
            'goal': 'pick foundation and concealer'
        }
    })
    session_id = analyze.json()['session_id']

    client.post(f'/v1/session/{session_id}/message', json={'message': 'подбери консилер под глаза'})
    recall = client.post(f'/v1/session/{session_id}/message', json={'message': 'напомни прошлую подборку'})

    assert recall.status_code == 200
    data = recall.json()
    assert data['intent']['intent'] == 'conversation_memory'
    assert 'Напоминаю прошлую подборку' in data['answer_text']
    assert len(data['updated_session_state']['conversation_history']) >= 5
