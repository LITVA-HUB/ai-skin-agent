# Golden Apple Beauty Advisor

Локальный FastAPI-прототип AI-консультанта для beauty-ритейла в логике Golden Apple.

Проект уже умеет работать не просто как skin analyzer, а как **photo-driven beauty advisor**, который:
- анализирует фото,
- собирает стартовую подборку,
- ведёт session-aware диалог,
- перестраивает образ под новый запрос,
- старается продавать не только через “объяснение”, но и через desirability / bundle / conversion logic.

---

## Current version

**Version:** `v0.2.0`

Это уже не просто skincare/compexion demo. Текущая версия включает:
- расширенный beauty scope,
- look-aware planner,
- look harmony,
- look transformations,
- merchandising/conversion layer,
- упрощённый consumer-facing UI.

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

Это ещё не production-grade commerce engine, но это уже шаг в сторону продающего beauty advisor, а не просто explain-bot.

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

Последняя проверка перед публикацией:
- **48 passed**

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
- ответный слой стал лучше, но ещё не полностью production-safe
- LLM discipline improved, but still needs stricter response control for perfect retail consistency
- some transformation flows still need stronger category steering

---

## Short roadmap

### Next likely focus
- stricter response-control layer
- stronger hero-item selection by visible payoff
- harder category steering for sexy / evening / focus transformations
- UI conversion polish
- real catalog / persistent data / release-grade polish
