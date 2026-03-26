# Golden Apple Beauty Advisor

AI beauty-advisor backend prototype for Golden Apple-style retail flows.

This project is evolving from a product concept demo into a more production-oriented recommendation backend.
It is not a final production retail system yet, but it already contains:
- session-aware beauty dialogue,
- photo-driven starting recommendations,
- beauty-domain planning,
- recommendation pipeline with retrieval/reranking,
- conversion-oriented response framing,
- SQLite-backed session persistence,
- health/readiness endpoints,
- structured logging foundation.

---

## Current checkpoint

**Checkpoint version:** `v0.6.0-beta`

This checkpoint should be understood as:
- a strong backend checkpoint,
- a production-hardening milestone,
- not a final production release.

---

## What exists now

### Beauty domains
The system currently covers:

#### Skincare
- cleanser
- serum
- moisturizer
- SPF
- toner
- spot treatment
- makeup remover

#### Complexion / base
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

## Current backend architecture

The project has been split into focused modules.

### Core runtime / API
- `app/main.py`
- `app/runtime.py`
- `app/config.py`
- `app/store.py`
- `app/observability.py`
- `app/validation.py`

### Decision / recommendation logic
- `app/intent_service.py`
- `app/profile_service.py`
- `app/plan_service.py`
- `app/beauty_modes.py`
- `app/look_rules.py`
- `app/look_transforms.py`
- `app/look_harmony.py`
- `app/decision_pipeline.py`
- `app/retrieval.py`
- `app/retrieval_filters.py`
- `app/retrieval_reranker.py`
- `app/merchandising.py`
- `app/response_service.py`
- `app/dialog_service.py`
- `app/logic.py`

### Data
- `app/data/catalog.json`

---

## What the backend can do now

### 1. Start from a photo
The backend accepts a photo payload and creates a first recommendation set.

### 2. Maintain session state
The backend keeps conversation state across requests and now persists sessions via SQLite by default.

### 3. Interpret user requests
It can react to requests such as:
- show cheaper option
- replace product
- explain choice
- compare choices
- make it simpler
- shift focus to lips / eyes
- attempt evening / glam / soft-luxury style shifts

### 4. Build recommendation sets
The backend currently uses:
- profile inference
- recommendation planning
- retrieval filters
- reranking
- hero/support ordering

### 5. Produce retail-oriented responses
Responses are shorter and more grounded than earlier builds.
There is a stronger fail-safe fallback to deterministic response composition.

---

## Operational foundation added in this checkpoint

### Persistence
- SQLite-backed session persistence
- TTL support
- expired-session cleanup
- simple migration discipline for session table evolution

### Service health
- `/health`
- `/ready`

### Observability
- startup/shutdown events
- request/error logging foundation
- structured JSON-line logs
- decision trace in runtime state

### Safety improvements
- stricter response grounding validation
- stronger deterministic fallback for answers

---

## Current strengths

- the backend architecture is much stronger than the initial prototype
- the project is modular and testable
- response discipline is better than before
- persistence and runtime discipline are now present
- there is a growing production-style operational foundation

---

## Current limitations

This beta checkpoint is still **not final production-ready**.

Main open gaps:

### 1. Decision correctness is still inconsistent
The hardest unresolved product-quality issue is recommendation correctness in some style-critical flows:
- sexy
- soft luxury
- evening transformation
- eyes/lips focus shifts

These are better understood now, but still not stable enough to call production-grade.

### 2. Catalog realism is limited
The catalog is still synthetic/mock and not a real retail catalog.
That limits recommendation quality significantly.

### 3. Response safety is improved, but not perfect
Grounding is much better than before, but production-grade answer control still needs more tightening.

### 4. Operational maturity is incomplete
The service now has a much better foundation, but still needs:
- stronger request tracing
- richer error diagnostics
- fuller config discipline
- deeper evaluation harness

---

## Roadmap

## Phase A — Recommendation correctness
Primary focus:
- fix mode resolution quality
- fix bundle correctness for key beauty scenarios
- stabilize sexy / luxury / evening / focus flows
- improve hero selection and visible-payoff ranking

## Phase B — Response reliability
- stricter grounded response control
- safer compare/explain behavior
- more deterministic product-facing response assembly

## Phase C — Data realism
- richer catalog metadata
- better shade/family structure
- stronger compatibility logic
- real retail catalog integration path

## Phase D — Production maturity
- stronger storage lifecycle
- richer request tracing
- structured warning/error events
- evaluation/regression harness
- deployment/runtime hardening

---

## For humans and models reading this repo

If you are reviewing this repository, the correct interpretation is:

- this is no longer a toy demo;
- this is also not yet a final production beauty backend;
- this repository is currently in a serious backend-hardening stage;
- the biggest remaining challenge is product-quality correctness, not basic project structure.

In other words:
**architecture is getting stronger faster than recommendation quality**, and the next milestones should focus on closing that gap.

---

## Tests

At the time of this checkpoint, the project test suite is green.

Latest status during this work:
- **62 passed**

---

## Related project docs

- `ARCHITECTURE.md`
- `BEAUTY_EXPANSION_PLAN.md`
- `CONVERSION_NOTES.md`
- `PRODUCTION_BLUEPRINT.md`
- `CHANGELOG.md`

---

## Repository

GitHub:
- <https://github.com/LITVA-HUB/ai-skin-agent>
