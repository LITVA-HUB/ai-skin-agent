# Changelog

## v0.2.0

### Added
- Expanded beauty scope beyond skincare and complexion:
  - lips
  - eyes
  - cheeks
  - prep / finish products
- New beauty-aware planning modules:
  - intent parsing
  - profile service
  - plan service
  - response service
  - dialog service
- Look-aware recommendation logic:
  - look strategy
  - accent balance
  - focus features
  - look harmony
  - look transformations
- Merchandising and conversion layer:
  - hero-first ordering
  - bundle framing
  - choice simplification
  - cart-minded selling prompts
- New beauty catalog entries and richer metadata
- Expanded test coverage across planner, retrieval, response, conversion, harmony, transformations
- Architecture and product notes:
  - `ARCHITECTURE.md`
  - `BEAUTY_EXPANSION_PLAN.md`
  - `CONVERSION_NOTES.md`

### Changed
- UI simplified into a more consumer-facing flow:
  - upload photo
  - get first recommendation
  - chat naturally with the agent
- Response layer made shorter and more retail-oriented
- Recommendation stack split into more maintainable modules

### Current caveats
- Still a prototype
- Catalog is synthetic/mock
- LLM response discipline is improved but still not fully production-grade
- Some style transformations still need stricter category steering for best commercial behavior
