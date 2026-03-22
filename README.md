# Golden Apple Beauty Advisor

Локальный Python/FastAPI прототип beauty-ассистента для сценариев уровня Золотого Яблока.

Это не просто demo с кнопкой «подобрать крем». Проект уже умеет работать как **photo-driven beauty advisor**:
- анализирует фото
- собирает skin + complexion profile
- подбирает уход и complexion makeup
- ведёт follow-up диалог внутри одной сессии
- помнит, что уже советовал и что ты уже спрашивал
- пересобирает подборку под новый запрос

Идея проекта — показать, как может выглядеть живой AI-консультант для beauty-ритейла: понятный пользователю, достаточно умный в диалоге и технически структурированный под дальнейший рост.

---

## Что умеет сейчас

### Photo-driven старт
Пользователь загружает фото лица или кожи и получает стартовую подборку.

На основе изображения система извлекает practical signals:
- oiliness
- dryness
- redness
- breakouts
- sensitivity signs
- tone evenness
- skin tone bucket
- undertone guess
- under-eye darkness
- visible shine
- texture visibility

Это не медицинская диагностика и не попытка изображать врача. Это product-oriented visual analysis для beauty-рекомендаций.

---

### Подбор skincare
Поддерживаются категории:
- cleanser
- serum
- moisturizer
- SPF
- toner
- spot treatment

Система учитывает:
- тип кожи
- ключевые concerns
- чувствительность
- бюджет
- исключённые ингредиенты
- preferred brands
- длину рутины
- прошлые реакции внутри текущей сессии

Можно писать, например:
- `подбери уход от покраснений`
- `сделай рутину проще`
- `покажи вариант подешевле`
- `без niacinamide`
- `оставь уход, но замени сыворотку`

---

### Подбор complexion makeup
Поддерживаются категории:
- foundation
- skin tint
- concealer
- powder

Система умеет учитывать:
- примерный tone bucket
- undertone
- desired finish
- desired coverage
- under-eye use case
- shine-control constraints
- сочетание с текущим типом кожи и общим запросом

Можно писать, например:
- `подбери тональник под мой тон кожи`
- `хочу легкое покрытие`
- `нужен сияющий финиш`
- `нужен консилер под глаза`
- `сравни foundation и skin tint`
- `оставь уход, но добавь тон`

---

### Смешанные beauty-сценарии
Одна из главных сильных сторон прототипа — он не разваливается на «уход отдельно / макияж отдельно».

Сейчас он уже умеет вести mixed flows:
- `сначала подбери уход, потом тональник`
- `сделай уход проще, но оставь skin tint`
- `мне нужен уход + консилер под глаза`
- `оставь уход, но замени тон на более легкий`

То есть это уже не просто SKU search, а зачаток реального beauty advisor.

---

### Session-aware чат
Агент помнит контекст **внутри текущей сессии**.

Он удерживает:
- что ты уже спрашивал
- что уже советовал
- preferred finish / coverage
- preferred brands
- excluded ingredients
- accepted / rejected products
- budget direction
- текущую подборку по категориям
- последние сообщения в чате

Благодаря этому можно спрашивать:
- `что я у тебя спрашивал?`
- `что ты советовал в первый раз?`
- `на чём мы остановились?`
- `напомни прошлую подборку`

И он отвечает уже не из фантазии, а из истории текущей сессии.

---

## Как выглядит пользовательский сценарий

### Базовый flow
1. Пользователь загружает фото
2. Сервис строит skin / complexion profile
3. Planner решает, какие категории нужны
4. Retrieval поднимает кандидатов из локального каталога
5. Reranking собирает итоговую подборку
6. Пользователь продолжает диалог обычным языком
7. Агент пересобирает рекомендации без потери контекста

### Что можно сделать после первого ответа
- попросить более дешёвый вариант
- заменить один продукт, не ломая всю подборку
- исключить ингредиент
- сократить рутину
- добавить makeup к skincare
- попросить compare
- попросить explain
- вернуть прошлую подборку

---

## Как это работает внутри

## 1. Photo analysis
На входе:
- `photo_b64` или `image_url`

На выходе:
- `PhotoAnalysisResult`

Внутри сейчас есть:
- мультимодальный путь через Gemini
- deterministic fallback, если Gemini недоступна или не отвечает

Это позволяет проекту оставаться runnable локально и не зависеть полностью от внешнего API в demo-сценарии.

---

## 2. Profile building
После анализа фото система строит profile layer:

### Skin profile
- skin type
- primary concerns
- secondary concerns
- cautions

### Complexion profile
- skin tone
- undertone
- preferred finish
- preferred coverage
- under-eye concealer need
- complexion constraints

Это уже не “сырые сигналы”, а более пригодное представление для planner и retrieval.

---

## 3. Planning
Planner определяет:
- какие product domains нужны:
  - skincare
  - makeup
  - hybrid
- какие категории включать
- какие теги/ограничения важны
- какие preferences должны повлиять на retrieval

Пример:
- если у пользователя есть покраснение + нужен легкий тон,
  planner может одновременно собрать:
  - cleanser
  - serum
  - moisturizer
  - SPF
  - foundation или skin tint
  - concealer

---

## 4. Hybrid retrieval
Текущий retrieval устроен в несколько слоёв.

### Hard filters
Сначала товары режутся по правилам:
- category
- domain
- availability
- budget
- excluded ingredients
- skin-type fit
- product exclusions
- preferred brands
- session rejections
- tone / undertone / suitable area для makeup

### Local vector search
После фильтрации включается локальный vector search.

Сейчас он уже сделан не игрушечно:
- нормализация текста через `unicodedata`
- `ё -> е`
- чистка пунктуации
- расширение RU/EN beauty-синонимами
- hashed vectors
- 128 dimensions
- lexical overlap + vector similarity
- cached local vector index
- weighted query / product documents

Это всё ещё локальная deterministic реализация, но уже достаточно взрослая по структуре.

### Reranking
После semantic retrieval кандидаты ранжируются дальше по:
- concern overlap
- preferred tags
- skin type fit
- budget fit
- tone fit
- undertone fit
- finish fit
- coverage fit
- novelty penalties
- follow-up bonuses/penalties

Именно этот слой делает поведение агента более правдоподобным в повторных запросах типа:
- `подешевле`
- `замени только тон`
- `оставь уход, но покажи другой консилер`

---

## 5. Agent / orchestration layer
Follow-up агент раскладывает сообщение примерно так:

- `domain`: `skincare | makeup | hybrid`
- `action`: `recommend | replace | compare | explain | simplify | cheaper | refine`
- `target_category` / `target_categories`
- `preference_updates`
- `constraints_update`

За счёт этого агент умеет:
- не начинать каждый раз новый чат с нуля
- держать структуру разговора
- различать compare / explain / refine / replace
- работать как product-oriented консультант, а не просто текстогенератор

---

## Demo UI
Локальный UI специально сделан простым, но достаточно полным для продуктового теста.

Что там есть:
- загрузка фото
- preview
- goal input
- дополнительные настройки
- карточки рекомендаций
- чат с агентом

Этого уже достаточно, чтобы полноценно руками прогонять сценарии пользователя.

---

## Что можно протестировать прямо сейчас

### Skincare
- `подбери уход от покраснений`
- `сделай рутину проще`
- `без niacinamide`
- `оставь уход, но замени сыворотку`

### Makeup
- `подбери тональник под мой тон кожи`
- `хочу легкое покрытие`
- `нужен сияющий финиш`
- `нужен консилер под глаза`
- `покажи вариант подешевле`

### Mixed flow
- `сначала подбери уход, потом тон`
- `оставь уход, но добавь консилер`
- `мне нужен уход плюс skin tint`

### Agent memory
- `что я у тебя спрашивал?`
- `что ты советовал в первый раз?`
- `на чём мы остановились?`
- `напомни прошлую подборку`

### Compare / explain
- `сравни foundation и skin tint`
- `почему ты выбрал именно это`
- `объясни, почему этот вариант мне подходит`

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

Если локально запускается fixed-port версия:
- `http://localhost:8010/`

---

## Environment variables

Пример:

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

### Product
- photo-driven beauty advisor
- skincare + complexion makeup
- unified beauty chat
- compare mode
- explain mode
- mixed-domain flows
- session memory inside one conversation

### Engineering
- FastAPI app
- local mock catalog
- hybrid retrieval
- improved local vector search layer
- session-aware orchestration
- deterministic local testing
- GitHub repo ready

### Retrieval
- hard filters
- local vector search
- reranking
- tone / undertone / finish / coverage-aware ranking
- follow-up-aware replacement behavior

### Agent layer
- structured intents
- in-session preference memory
- conversation history recall
- improved product-facing replies

---

## Что ещё не сделано

Вот честный список следующего этапа.

### Catalog / data
- реальный каталог ритейлера вместо mock data
- real availability / inventory sync
- richer price / promo logic
- полноценные shade matrices и product variants

### Retrieval / ML
- настоящие embeddings
- persistent vector index
- pgvector / vector DB / ANN search
- более сильный compare/explain candidate set
- более точный shade match по фото

### Agent layer
- сильнее NLU вместо mostly heuristic parsing
- лучшее извлечение brands / ingredients / constraints
- долговременная память между рестартами
- более умный compare engine по нескольким товарам
- лучшее поведение на более длинных диалогах

### Product / UX
- сохранение сессий
- debug panel: why this product was chosen
- richer product cards
- better explainability UI
- deploy-ready cloud config
- screenshots / public demo docs

---

## Ограничения текущей версии

Важно: это **prototype/demo**, а не production-ready beauty platform.

Сейчас ограничения такие:
- shade match приблизительный
- undertone detection partly heuristic
- photo analysis не является диагностикой
- vector search локальный, а не на настоящих embeddings
- session memory живёт в памяти процесса и не переживает рестарт
- catalog synthetic / mocked
- compare/explain пока не опираются на отдельный глубокий reasoning engine по каталогу

---

## Почему проект уже выглядит сильно

Потому что он уже показывает не один isolated feature, а связную систему:
- фото -> профиль
- профиль -> план
- план -> retrieval
- retrieval -> рекомендации
- рекомендации -> follow-up диалог
- follow-up -> session-aware перестройка

То есть это уже не просто “чатик про косметику”, а хороший фундамент под реального retail beauty advisor.

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
- experiments / evaluation
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
- repo cleaned up and documented
- not yet production-ready
