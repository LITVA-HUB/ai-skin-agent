# Beauty Expansion Plan

## Goal
Expand the current skin/compexion advisor into a broader Golden Apple beauty advisor that can recommend:
- skincare
- complexion
- lips
- eyes
- cheeks
- prep / finish products

## Implementation steps

1. Extend domain model
- add product categories for lips, eyes, cheeks, prep/finish
- add beauty profile / makeup profile structures
- add richer product metadata for color and use-case matching

2. Extend catalog schema
- new category-specific fields:
  - color family
  - opacity / intensity
  - longwear / waterproof / transfer resistance
  - applicator / effect metadata
  - finish support

3. Extend intent parsing
- support requests for:
  - full look
  - lips / eyes / cheeks only
  - occasion-based looks
  - style-based looks
  - feature focus requests

4. Extend planning
- planner should choose categories for:
  - everyday look
  - evening look
  - quick makeup
  - lips-focused look
  - eyes-focused look
  - full face bundle

5. Extend retrieval
- preserve current hard-filter + semantic + rerank structure
- enrich reranking using beauty-specific metadata

6. Extend tests
- add parser tests
- add planning tests
- add retrieval tests for new categories/domains
