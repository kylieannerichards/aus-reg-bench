# benchmark/tasks/prudential_reasoning/

**Task:** multi-step application of APRA prudential standards to novel scenarios.

Items are hand-constructed with input from Australian regulatory experts, then validated by at least one additional reviewer. Each item tests reasoning that cannot be answered by surface retrieval — the scenario is deliberately novel, but the correct answer follows from published APRA standards.

Planned contents:

- `items.jsonl` — `{id, scenario, question, gold_answer, reasoning_trace, applicable_standards, reviewer_ids, ...}`
- `rubric.md` — scoring rubric for model responses (rule-based and LLM-judge-assisted)
- Inter-rater reliability statistics will be reported in the paper.
