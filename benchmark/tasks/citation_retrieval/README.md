# benchmark/tasks/citation_retrieval/

**Task:** given a short scenario, identify the governing instrument and section across ASIC Regulatory Guides, APRA Prudential Standards, and AASB Accounting Standards.

Planned contents:

- `items.jsonl` — one item per line: `{id, scenario, gold_citation, source, difficulty, ...}`
- `generator.py` — script to construct items from the corpus in `corpus/`
- Scoring metric: exact-match on instrument + section, with partial credit for correct instrument only

Items are generated programmatically from the corpus then spot-checked by a human reviewer before inclusion.
