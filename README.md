# Golden Apple Beauty Advisor

Локальный Python/FastAPI прототип beauty-ассистента для сценариев уровня Золотого Яблока.

Проект начинался как простой skincare demo, а сейчас это уже **session-aware beauty advisor** с поддержкой:
- photo-driven skincare рекомендаций
- complexion makeup рекомендаций
- диалогового follow-up агента
- hybrid retrieval с локальным vector search
- памяти контекста внутри текущей сессии

---

## Что это умеет сейчас

### 1. Анализ фото
Сервис принимает фото лица/кожи и строит практический профиль для рекомендаций.

Сейчас используются сигналы вроде:
- oiliness
- dryness
- redness
- breakouts
- sensitivity
- skin tone
- undertone
- under-eye darkness
- visible shine
- texture visibility

Важно: это **demo-level analysis**, а не медицинская или профессиональная диагностика.

---

### 2. Подбор ухода
Поддерживаются skincare-категории:
- cleanser
- serum
- moisturizer
- SPF
- toner
- spot treatment

Агент умеет учитывать:
- тип кожи
- ключевые concerns
- чувствительность
- бюджет
- нежелательные ингредиенты
- preferred brands
- длину рутины

Примеры запросов:
- `подбери уход от покраснений`
- `сделай рутину проще`
- `покажи вариант подешевле`
- `без niacinamide`

---

### 3. Подбор complexion makeup
Поддерживаются makeup-категории:
- foundation
- skin tint
- concealer
- powder

Агент умеет учитывать:
- примерный tone bucket
- undertone
- desired finish
- desired coverage
- under-eye use case
- shine control / texture preferences

Примеры запросов:
- `подбери тональник под мой тон кожи`
- `хочу легкое покрытие`
- `нужен сияющий финиш`
- `нужен консилер под глаза`
- `сравни foundation и skin tint`

---

### 4. Session-aware агент
Это не просто поиск товаров, а агент с памятью внутри сессии.

Он запоминает:
- что ты уже спрашивал
- что он уже советовал
- preferred finish / coverage
- excluded ingredients
- preferred brands
- rejected / accepted products
- direction по бюджету
- текущую подборку по категориям

Поддерживаются сценарии:
- compare mode
- explain mode
- cheaper alternative
- replace product
- simplify routine
- mixed skincare + makeup flow
- recall прошлых сообщений в текущем чате

Примеры:
- `что я у тебя спрашивал?`
- `что ты советовал в первый раз?`
- `на чём мы остановились?`
- `напомни прошлую подборку`

---

## Как это устроено

### High-level pipeline

1. **Photo analysis**
2. **Skin / complexion profile building**
3. **Planning**
4. **Hybrid retrieval**
5. **Reranking**
6. **Session-aware response generation**

---

## Retrieval architecture

Проект работает локально, без внешней БД и без настоящего vector DB, но retrieval уже построен по взрослой схеме.

### Hard filters
Сначала отсекаются товары по правилам:
- category
- domain
- availability
- budget
- excluded ingredients
- skin-type fit
- product exclusions
- brand preferences
- session rejections
- tone / undertone / suitable area для makeup

### Local vector search
Сейчас используется **локальный deterministic vector search**:
- нормализация текста через `unicodedata`
- расширение токенов beauty-синонимами RU/EN
- hashed vectors
- 128 dimensions
- lexical overlap + vector similarity
- cached local vector index

### Reranking
После retrieval идёт reranking, который учитывает:
- concern overlap
- preferred tags
- skin type fit
- budget fit
- tone / undertone fit
- finish / coverage fit
- novelty penalties
- follow-up bonuses/penalties

Это всё ещё локальная реализация, но уже не игрушечная.

---

## Agent / orchestration layer

Agent layer умеет структурировать follow-up примерно так:

- `domain`: `skincare | makeup | hybrid`
- `action`: `recommend | replace | compare | explain | simplify | cheaper | refine`
- `target_category` / `target_categories`
- `preference_updates`
- `constraints_update`

За счёт этого агент лучше держит смешанные сценарии и не воспринимает каждое новое сообщение как чат с нуля.

---

## Demo UI

Есть локальный интерфейс с:
- загрузкой фото
- preview
- goal input
- карточками рекомендаций
- чатом с агентом

UI специально сделан простым, чтобы можно было тестировать продуктовый сценарий, а не только API.

---

## API

### Endpoints
- `GET /`
- `GET /health`
- `POST /v1/photo/analyze`
- `POST /v1/session/{session_id}/message`
- `GET /v1/session/{session_id}`

---

## Local run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# optionally set GEMINI_API_KEY in .env
uvicorn app.main:app --reload
```

Открыть:
- `http://localhost:8000/`

Если проект запускается через fixed port locally:
- `http://localhost:8010/`

---

## Environment variables

Пример в `.env.example`:

```env
GEMINI_API_KEY=replace-me
GEMINI_MODEL=gemini-3.1-flash-lite-preview
SESSION_TTL_HOURS=24
```

---

## Структура проекта

```text
app/
  catalog.py
  config.py
  gemini_client.py
  logic.py
  main.py
  models.py
  retrieval.py
  store.py
  data/catalog.json
  templates/index.html
scripts/
  e2e_smoke.py
  gemini_smoke.py
tests/
  test_app.py
  test_retrieval.py
  test_ui.py
```

---

## Что уже сделано

### Product scope
- skincare recommendations
- complexion makeup recommendations
- unified beauty chat
- compare / explain flows
- conversation memory inside a session

### Engineering
- FastAPI app
- local mock catalog
- hybrid retrieval
- improved local vector search layer
- deterministic local testing
- GitHub repo ready

### Testing
Текущее покрытие включает:
- health endpoint
- analyze + follow-up
- compare mode
- explain mode
- hybrid flows
- session memory recall
- retrieval behavior
- vector normalization behavior
- UI root rendering

---

## Что ещё не сделано

Вот честный список того, что пока остаётся следующим этапом.

### Data / catalog
- реальный каталог ритейлера вместо mock data
- real availability / inventory sync
- richer pricing / promo logic
- SKU variants и оттеночные матрицы на уровне реального каталога

### Retrieval / ML
- настоящие embeddings
- persistent vector index
- pgvector / vector DB / ANN search
- более сильный candidate set для compare/explain
- более точный shade match по фото

### Agent layer
- сильнее NLU вместо в основном heuristic parsing
- лучшее извлечение brands / ingredients / constraints
- долговременная память между рестартами
- более умный compare engine по нескольким товарам

### Product / UX
- сохранение истории сессий
- debug panel: why this product was chosen
- richer product cards
- better explainability UI
- deploy-ready config для облака

---

## Ограничения текущей версии

Важно понимать, что это **demo/prototype**, а не production-ready beauty platform.

Сейчас ограничения такие:
- shade match приблизительный
- undertone detection эвристический / fallback-friendly
- photo analysis не является диагностикой
- vector search локальный, а не на настоящих embeddings
- session memory живёт в процессе и не переживает рестарт сервера
- catalog synthetic / mocked

---

## Почему проект уже полезный

Несмотря на ограничения, это уже хороший product/engineering prototype, потому что он показывает:
- как может выглядеть beauty advisor для ритейла
- как совместить skincare + complexion flows
- как строить session-aware recommendation agent
- как эволюционно прийти от local demo к более серьёзной архитектуре

---

## Roadmap

### Near-term
- stronger compare/explain over wider candidate sets
- persistent sessions
- better product copy style
- richer UI transparency

### Mid-term
- real embeddings
- persistent vector index
- real catalog normalization pipeline
- better multimodal profile extraction

### Later
- production catalog integration
- ranking analytics
- event logging / experiments
- cloud deployment setup

---

## Repository

GitHub:
- <https://github.com/LITVA-HUB/ai-skin-agent>

---

## Status

Current status:
- actively evolving prototype
- local demo ready
- retrieval + agent memory + beauty flows already implemented
- not yet production-ready
