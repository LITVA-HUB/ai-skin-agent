# Golden Apple Beauty Advisor

Локальный FastAPI-прототип AI-консультанта для beauty-ритейла в логике Golden Apple.

Проект уже работает не просто как skin analyzer, а как **photo-driven beauty advisor**, который:
- анализирует фото,
- собирает стартовую подборку,
- ведёт session-aware диалог,
- перестраивает образ под новый запрос,
- позволяет сразу добавлять предложенные товары в корзину,
- двигается в сторону retail-консультанта, а не просто explain-bot.

---

## Current version

**Archive baseline:** `v0.2.0`

Важно: внутри проекта есть рассинхрон версий — в `README` архив обозначен как `v0.2.0`, а в `app/main.py` версия приложения сейчас указана как `0.4.0`.

Текущее состояние включает:
- расширенный beauty scope,
- look-aware planner,
- look harmony,
- look transformations,
- merchandising / conversion layer,
- consumer-facing UI,
- встроенную session cart / корзину.

---

## What the project does now

### 1. Photo-driven start
Пользователь загружает фото и получает первую подборку.

Система извлекает practical signals:
- oiliness
- dryness
- redness
- breakouts
- tone evenness
- sensitivity signs
- skin tone bucket
- undertone guess
- under-eye darkness
- visible shine
- texture visibility

Важно: это не медицинская диагностика и не косметолог. Это product-oriented visual analysis.

---

### 2. Beauty recommendation domains
Сейчас проект покрывает:

#### Skincare
- cleanser
- serum
- moisturizer
- SPF
- toner
- spot treatment
- makeup remover

#### Complexion
- foundation
- skin tint
- concealer
- powder
- primer
- setting spray

#### Lips
- lipstick
- lip tint
- lip gloss
- lip liner
- lip balm

#### Eyes / brows
- mascara
- eyeliner
- eyeshadow palette
- brow pencil
- brow gel

#### Cheeks / face color
- blush
- bronzer
- highlighter
- contour

---

### 3. Session-aware beauty chat
Агент удерживает внутри сессии:
- текущую подборку,
- ограничения,
- budget direction,
- accepted / rejected products,
- последние цели,
- структуру look / focus / transformations.

Он умеет:
- пересобрать подборку,
- сделать вариант подешевле,
- упростить образ,
- сдвинуть акцент на губы / глаза,
- сделать образ более вечерним,
- объяснить выбор,
- сравнить варианты.

---

### 4. Look-aware planning
Planner теперь работает не только на уровне категорий, но и на уровне образа.

Поддерживаются идеи:
- fresh
- balanced
- glam
- sensual
- soft luxury

Также учитываются:
- focus features
- accent balance
- color family
- finish logic
- occasion-like transformations

---

### 5. Look harmony
Система старается учитывать сочетание между продуктами:
- dominant color
- dominant finish
- lips / eyes / cheeks focus
- стратегию образа
- более согласованную связку hero + support items

---

### 6. Look transformation flows
Поддерживаются трансформации вроде:
- day → evening
- fresh → sexy
- balanced → soft luxury
- focus lips
- focus eyes

То есть агент может не только “собрать”, но и **перестроить** уже начатый образ.

---

### 7. Merchandising / conversion layer
В проект уже добавлены:
- hero-first ordering
- support-item sequencing
- bundle framing
- cart-minded selling logic
- choice simplification
- aspirational CTA

Это ещё не production-grade commerce engine, но это уже шаг в сторону продающего beauty advisor.

---

### 8. Built-in cart flow
Теперь в UI есть **магазинная корзина**, привязанная к текущей сессии:
- товары можно добавлять прямо из рекомендаций,
- можно менять количество,
- удалять позиции,
- очищать корзину,
- видеть общее количество и итоговую сумму.

Под это добавлены API-эндпоинты:
- `GET /v1/session/{session_id}/cart`
- `POST /v1/session/{session_id}/cart/items`
- `PATCH /v1/session/{session_id}/cart/items/{sku}`
- `DELETE /v1/session/{session_id}/cart/items/{sku}`
- `DELETE /v1/session/{session_id}/cart`

---

## Architecture

Ключевые слои сейчас:
- `profile_service.py`
- `intent_service.py`
- `plan_service.py`
- `retrieval.py`
- `retrieval_filters.py`
- `retrieval_reranker.py`
- `response_service.py`
- `dialog_service.py`
- `look_harmony.py`
- `look_transforms.py`
- `merchandising.py`
- `logic.py` как orchestration layer
- `store.py` для in-memory session storage

Подробнее:
- `ARCHITECTURE.md`

---

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Открыть:
- `http://127.0.0.1:8000/`

Если используется фиксированный локальный запуск:
- `http://127.0.0.1:8010/`

---

## Configuration

Проект читает `.env` в корне репозитория.

Пример:

```env
GEMINI_API_KEY=your_real_api_key
GEMINI_MODEL=gemini-3.1-flash-lite-preview
SESSION_TTL_HOURS=24
```

Важно:
- `GEMINI_API_KEY` — API key
- `GEMINI_MODEL` — имя модели, не ключ

---

## Tests

Проект покрыт тестами по:
- app flows
- retrieval
- intent parsing
- planning
- response helpers
- beauty expansion
- look harmony
- look transforms
- merchandising
- conversion layer
- UI smoke
- cart flow

Локальная проверка перед публикацией в этой итерации:
- **10 passed** (`tests/test_app.py`, `tests/test_ui.py`)

---

## Repository notes

Полезные файлы:
- `ARCHITECTURE.md`
- `BEAUTY_EXPANSION_PLAN.md`
- `CONVERSION_NOTES.md`
- `CHANGELOG.md`

GitHub:
- <https://github.com/LITVA-HUB/ai-skin-agent>

---

## Current caveats

Это всё ещё **prototype**, а не production-ready система.

Слабые места текущей версии:
- каталог synthetic/mock
- нет real retail integration
- нет persistent DB-backed sessions
- корзина пока session-based, а не backed by database
- checkout пока только UI / flow stub, без реального заказа
- ответный слой стал лучше, но ещё не полностью production-safe
- LLM discipline improved, but still needs stricter response control for perfect retail consistency
- some transformation flows still need stronger category steering

---

## Short roadmap

### Next likely focus
- отдельный checkout screen
- stronger hero-item selection by visible payoff
- harder category steering for sexy / evening / focus transformations
- richer cart / bundle flow
- real catalog / persistent data / release-grade polish
