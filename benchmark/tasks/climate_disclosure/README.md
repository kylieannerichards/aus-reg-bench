# benchmark/tasks/climate_disclosure/

**Task:** assess climate disclosure quality against AASB S2 *Climate-related Disclosures*.

Items present a disclosure excerpt (real or constructed) and ask the model to evaluate compliance with specific AASB S2 requirements. Ground-truth assessments are produced by Australian sustainability reporting experts.

Planned contents:

- `items.jsonl` — `{id, disclosure_text, requirement_refs, gold_assessment, rationale, ...}`
- `rubric.md` — scoring rubric covering coverage, specificity, and reasoning quality
- Notes on provenance of disclosure excerpts and permissions for any real-company text.
