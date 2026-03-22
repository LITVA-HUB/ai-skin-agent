# Golden Apple Beauty Advisor MVP+

Локальный Python/FastAPI прототип, который расширяет исходный skincare-only demo до beauty advisor сценария:
- photo-driven skincare рекомендации
- complexion makeup рекомендации
- единый chat + photo UX
- локальный mock catalog без внешней БД
- hybrid retrieval: hard filters -> deterministic vector retrieval -> reranking
- session-aware follow-up диалог

## Что теперь умеет

### Skincare
- очищение / сыворотка / крем / SPF
- в extended flow: тонер и точечный уход
- учитывает тип кожи, primary concerns, чувствительность, бюджет, исключённые ингредиенты

### Complexion makeup
- foundation
- skin tint
- concealer
- powder
- учитывает приблизительный skin tone bucket, undertone guess, desired finish, desired coverage, under-eye need, shine-control constraints

Примеры запросов:
- `подобрать тональник под мой тон кожи`
- `хочу легкое покрытие`
- `нужен сияющий финиш`
- `нужен консилер под глаза`
- `что подойдет для комбинированной кожи и светлого нейтрального подтона`
- `сделай уход проще, но добавь консилер`

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

## Architecture update

### 1) Photo analysis -> broader profile
`PhotoAnalysisResult` now contains both:
- skincare signals
- complexion signals

Added practical complexion fields:
- `skin_tone`
- `undertone`
- `under_eye_darkness`
- `visible_shine`
- `texture_visibility`

This is still approximate and safe for demo usage. If Gemini is unavailable, the service falls back to deterministic local mock analysis.

### 2) Unified skin + complexion profile
`SkinProfile` now includes nested `ComplexionProfile` with:
- inferred tone / undertone
- preferred finish
- preferred coverage
- under-eye concealer need
- complexion suitability constraints

Finish and coverage are inferred from user intent/text, not from the image.

### 3) Hybrid retrieval for both domains
The local retrieval pipeline in `app/retrieval.py` now supports:
- skincare domain
- makeup domain
- hybrid plans that combine both in one recommendation response

#### Hard filters
For every category, the pipeline filters by:
- category + domain
- availability
- budget
- excluded ingredients
- skin type / exclude_for
- brand preferences
- rejected products in session
- tone bucket
- undertone
- area suitability (`under_eye`, `face`)

#### Deterministic semantic retrieval
The app still uses a local hashed vectorizer:
- product documents include skincare and makeup facets
- vector search is deterministic and fully local
- no pgvector / Elasticsearch / external DB required

#### Reranking
Final ranking blends:
- concern overlap
- preferred tags
- skin type fit
- budget fit
- tone / undertone fit
- finish / coverage fit
- session context and novelty penalties

### 4) Dialog logic
Follow-up dialog can now:
- stay in skincare
- switch into makeup
- stay in makeup
- combine skincare + makeup in one flow

Heuristic intent parsing covers:
- cheaper alternatives
- replacements
- ingredient exclusions
- routine simplification
- makeup asks like foundation / tint / concealer / powder
- finish and coverage preferences
- explicit tone / undertone hints from user text

## Mock catalog
Catalog lives in `app/data/catalog.json`.

Current local catalog contains normalized SKUs across:
- cleanser
- serum
- moisturizer
- SPF
- toner
- spot_treatment
- foundation
- skin_tint
- concealer
- powder

Makeup SKU schema includes practical local fields:
- `domain`
- `tones`
- `undertones`
- `finishes`
- `coverage_levels`
- `suitable_areas`
- `texture`

## What is still mocked
- exact shade match from photo is approximate
- undertone detection is heuristic / fallback-friendly
- no real retailer inventory sync
- no external vector DB or search index
- no true multimodal shade calibration
- prices / descriptions / availability are demo-local

## Tests
Run:

```powershell
pytest
```

Covered scenarios:
- hybrid retrieval returns skincare + makeup categories
- tone / undertone / finish aware makeup retrieval
- cheaper foundation follow-up
- category replacement stability
- API analyze + follow-up flow
- UI root page still renders

## Scope evolution
The product is no longer just “AI Skin Agent”. It is now a broader Golden Apple beauty advisor demo that:
- keeps the original skincare pipeline intact
- adds complexion makeup recommendation architecture
- stays local and runnable without external DB dependencies
- remains simple enough for demo UX, but structured for future real multimodal analysis and catalog integrations
