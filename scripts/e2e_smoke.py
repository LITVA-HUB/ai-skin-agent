import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

health = client.get('/health')
print('health', health.status_code, health.json())

analyze = client.post('/v1/photo/analyze', json={
    'image_url': 'https://example.com/photo.jpg',
    'user_context': {
        'budget_segment': 'mid',
        'preferred_brands': [],
        'excluded_ingredients': [],
        'routine_size': 'standard',
        'goal': 'хочу убрать прыщи и покраснение'
    }
})
print('analyze', analyze.status_code)
adata = analyze.json()
print('session_id', adata.get('session_id'))
print('analysis_source', adata['photo_analysis_result']['source'])

message = client.post(f"/v1/session/{adata['session_id']}/message", json={
    'message': 'привет вот хочу тональник и немного прыщи убрать'
})
print('message', message.status_code)
mdata = message.json()
print('intent', mdata['intent']['intent'])
print('reply', mdata['answer_text'])
