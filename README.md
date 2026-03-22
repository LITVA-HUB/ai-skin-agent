# Golden Apple Beauty Advisor MVP+

Локальный Python/FastAPI прототип, который расширяет skincare-only demo до более умного beauty advisor сценария.

## Что улучшено в agent layer

### 1. Более структурный intent parsing
Теперь follow-up запросы раскладываются не только в legacy `intent`, но и в более полезную структуру:
- `domain`: `skincare | makeup | hybrid`
- `action`: `recommend | replace | compare | explain | simplify | cheaper | refine`
- `target_category` + `target_categories`
- `preference_updates`
- `constraints_update`

Это позволяет устойчивее обрабатывать смешанные beauty-диалоги вроде:
- `сделай уход попроще, но оставь skin tint`
- `сравни foundation и concealer`
- `объясни, почему этот крем лучше под мою кожу`
- `хочу matte finish и покрытие полегче`

API/UI совместимость сохранена: старое поле `intent` осталось.

### 2. Лучшая память предпочтений внутри сессии
Во время диалога агент теперь держит в сессии и переиспользует:
- finish preference
- coverage preference
- preferred brands
- disliked / excluded ingredients
- budget direction
- accepted / rejected products
- minimal vs extended routine preference

За счёт этого follow-up ответы меньше выглядят как «новый чат с нуля».

### 3. Compare mode и explain mode
Появились отдельные режимы оркестрации:
- **compare** — короткое product-facing сравнение товаров/категорий
- **explain** — объяснение, почему конкретный продукт или категория подходят под текущий профиль и запрос

### 4. Смешанные skincare + complexion сценарии
Планировщик лучше работает с hybrid-флоу:
- может вести уход и complexion makeup в одном ответе
- не теряет контекст между skincare и makeup follow-up сообщениями
- лучше учитывает комбинации типа `сделай уход проще, но оставь тон/тинт`

### 5. Более естественные ответы
Fallback-генерация теперь менее техническая и ближе к живой продуктовой консультации:
- меньше системного тона
- больше объяснения «что взять и почему»
- compare/explain ответы выглядят как нормальный beauty-консультант, а не внутренний pipeline

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# optionally set GEMINI_API_KEY in .env
uvicorn app.main:app --reload
```

## API
- `GET /`
- `GET /health`
- `POST /v1/photo/analyze`
- `POST /v1/session/{session_id}/message`
- `GET /v1/session/{session_id}`

## Архитектура

### Photo -> profile
`PhotoAnalysisResult` по-прежнему даёт локально runnable анализ фото и fallback без внешних зависимостей.

### Session-aware planning
`SessionState` + `UserContext` теперь хранят больше агентных сигналов для follow-up оркестрации.

### Retrieval
Retrieval остаётся локальным и совместимым с текущим демо:
- hard filters
- deterministic local vector retrieval
- reranking

## Что покрыто тестами
- makeup analyze + follow-up
- compare mode
- explain mode
- mixed-domain memory updates
- сохранение preferences/constraints в сессии
- health endpoint

## Ограничения
- shade match по фото всё ещё приблизительный
- бренды/ингредиенты пока ловятся простыми эвристиками
- compare/explain режимы завязаны на текущую рекомендательную выборку, а не на отдельный catalog reasoning engine
- intent parsing стал заметно сильнее, но пока не является полноценным NLU-модулем

## Как агент стал умнее
Ключевое изменение — agent layer теперь не просто мапит сообщение в один грубый intent, а хранит и переиспользует контекст предпочтений, различает тип действия пользователя и лучше планирует mixed beauty flow. За счёт этого follow-up сценарии стали устойчивее, натуральнее и ближе к реальной product-консультации.
