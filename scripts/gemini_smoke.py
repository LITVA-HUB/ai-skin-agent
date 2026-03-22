import os
from pathlib import Path

import httpx

for line in Path('.env').read_text(encoding='utf-8').splitlines():
    if '=' in line:
        k, v = line.split('=', 1)
        os.environ[k] = v

key = os.environ['GEMINI_API_KEY']
model = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')
url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
payload = {
    'generationConfig': {'temperature': 0, 'responseMimeType': 'application/json'},
    'contents': [{'parts': [{'text': 'Return only {"ok": true} as valid JSON.'}]}],
}
resp = httpx.post(url, json=payload, timeout=30)
print('status=', resp.status_code)
print(resp.text[:1200])
