# Architecture

## Current service layout

The app is now split into focused modules instead of one oversized orchestration file.

### Core flow
1. `profile_service.py`
   - photo fallback analysis
   - profile building
   - preference inference from goal
2. `intent_service.py`
   - message normalization
   - category/domain/action detection
   - preference and constraint extraction
   - heuristic intent assembly
3. `plan_service.py`
   - recommendation plan construction
   - domain/category selection
4. `retrieval.py`
   - hard filters
   - local vector retrieval
   - reranking
5. `response_service.py`
   - user-facing answer composition
   - compare/explain/follow-up rendering
   - prompt building and text sanitization
6. `dialog_service.py`
   - conversation turn storage helpers
   - session memory-style recall helpers
7. `logic.py`
   - thin orchestration layer for request handling

## State model

`SessionState` now uses a typed `DialogContextState` instead of a raw dictionary.

This makes these fields explicit:
- current recommendations by category
- active domains
- last intent/action/domain
- last target category/categories
- last referenced products

## Type model tightening

The project now uses stronger enum-based typing for:
- `ProductCategory`
- `ConcernType`

This reduces silent bugs from free-form strings and makes refactors safer.

## Next sensible steps

- persistent session storage
- evaluation harness for retrieval quality
- deeper long-dialog regression tests

## Implemented structural improvements

Done in this refactor:
- split retrieval responsibilities into:
  - `text_normalization.py`
  - `vector_index.py`
  - `retrieval_filters.py`
  - `retrieval_reranker.py`
  - `retrieval.py` as the retrieval service facade
- strengthened low-level tests for:
  - intent parsing
  - planning behavior
  - response formatting helpers
- kept user-facing rendering isolated from recommendation decisions
