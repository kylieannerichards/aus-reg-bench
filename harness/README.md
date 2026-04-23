# harness/

Evaluation harness. Loads benchmark items, dispatches them to model adapters, collects responses, and writes raw result logs to `results/raw/`.

Planned contents:

- `run.py` — CLI entrypoint: `python -m harness.run --task citation_retrieval --model claude-opus-4-7`
- `adapters/` — one module per model provider (see `adapters/README.md`)
- `scoring.py` — task-specific scorers producing per-item and aggregate metrics
- `config.py` — run configuration (seeds, retries, rate limits)

Determinism goals: given the same benchmark version, model version, temperature, and seed, a rerun should produce bit-identical raw logs where the provider API is deterministic, and otherwise metadata sufficient to reconstruct the run.
