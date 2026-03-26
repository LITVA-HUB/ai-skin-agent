# Production Blueprint

## Current diagnosis

The project has grown strong conceptually but still has architectural inconsistency in how recommendations are decided:
- multiple overlapping decision layers
- planner and retrieval are not always aligned
- transformation logic can drift from actual candidate availability
- response stability improved, but recommendation correctness is still the primary bottleneck

## Production-direction goals

1. Single authoritative decision pipeline
2. Deterministic recommendation assembly first, optional LLM polish second
3. Stable mode-driven bundle selection
4. Explicit fallback families
5. Stronger hero/support selection based on visible payoff
6. Simpler and more debuggable state transitions

## Recommended production architecture

### Layer 1 — Input understanding
- intent parsing
- preference extraction
- session merge

### Layer 2 — Decision core
- mode selection
- bundle template selection
- category guarantee resolution
- candidate retrieval per category family
- fallback resolution
- deduplication
- hero/support ordering

### Layer 3 — Response assembly
- deterministic response composer
- optional short LLM rewrite only when safe

### Layer 4 — Persistence / analytics (next stage)
- persistent session storage
- recommendation history
- eval traces

## Production cleanup priorities

### Priority A
- unify decision flow around one decision pipeline
- reduce duplicated or competing planning logic
- keep response generation grounded to selected products only

### Priority B
- make mode bundles more explicit and testable
- soften retrieval filters only inside controlled fallback paths
- improve category family guarantees for style-critical flows

### Priority C
- add structured debugability:
  - why this category was chosen
  - why fallback happened
  - why hero won

## Not production-ready yet

The following are still missing for true production:
- persistent data store
- real retail catalog integration
- operational observability
- stronger evaluation suite
- stricter response validation against catalog ids
- robust auth / deployment configuration
