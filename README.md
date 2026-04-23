# aus-reg-bench

**An empirical benchmark for evaluating frontier language models on Australian financial regulatory reasoning.**

> Status: **v0.1 — active development.** Expect breaking changes. Initial release targeted for mid-2026.

## Overview

`aus-reg-bench` evaluates how well frontier large language models reason about Australian financial regulation. It covers three task types drawn from publicly available Australian regulatory sources:

1. **Regulatory citation retrieval** — given a scenario, identify the governing instrument and section across ASIC Regulatory Guides, APRA Prudential Standards, and AASB Accounting Standards.
2. **Prudential reasoning** — multi-step application of APRA standards to novel scenarios, constructed with input from Australian regulatory experts.
3. **Climate disclosure evaluation** — assessment of disclosure quality against AASB S2 *Climate-related Disclosures*.

The benchmark is designed to inform evidence-based assessment of frontier AI capability in Australian institutional contexts, where policy debate is proceeding with limited local empirical grounding.

## Why this exists

Australia has no public empirical infrastructure for evaluating frontier AI capability in local regulatory and institutional contexts. Existing benchmarks are overwhelmingly US-centric and do not test reasoning over Australian statutory language, prudential frameworks, or disclosure standards. This project contributes a reproducible Australian-specific evaluation framework, with methodological emphasis on statistical rigour — Bayesian capability estimation, heavy-tail error analysis, inter-rater reliability — rather than point accuracy alone.

## Repository structure

```
aus-reg-bench/
├── paper/            # Working paper LaTeX source and figures
├── benchmark/        # Task items, organised by task type
│   └── tasks/
│       ├── citation_retrieval/
│       ├── prudential_reasoning/
│       └── climate_disclosure/
├── corpus/           # Source regulatory text: build scripts, not redistribution
├── harness/          # Evaluation code; model adapters for Claude, GPT, Gemini
├── results/          # Per-model response logs, analysis notebooks, figures
└── docs/             # Methodology notes, contribution guide
```

## Current status

- [x] Repository initialised and scaffolded
- [ ] Corpus build scripts (ASIC, APRA, AASB)
- [ ] Citation retrieval task generator
- [ ] Expert-validated prudential reasoning items
- [ ] AASB S2 disclosure evaluation items
- [x] Evaluation harness (Claude adapter)
- [ ] Evaluation harness (GPT, Gemini adapters)
- [ ] Statistical analysis notebooks
- [ ] Working paper (target: SSRN preprint, mid-2026)

### Recent activity

- **v0.1.1** — harness skeleton, Anthropic adapter, 5-item citation_retrieval seed set, statistical pipeline stub (Jeffreys interval on exact-match rate).

## Use of AI in this research

This benchmark is constructed with substantial AI assistance, consistent with emerging norms in empirical AI research. Claude Code (Anthropic) assists with corpus construction scripts, evaluation harness implementation, and drafting. Claude Opus 4.7 assists with methodological framing and writing. All benchmark items are human-designed and human-validated; evaluation subjects (the models being tested) receive no research assistance from the research team. Author bears full responsibility for all claims, methodology, and findings.

## Citation

If you use this benchmark, please cite:

```
Richards, K-A. (2026). aus-reg-bench: An empirical benchmark for
Australian financial regulatory reasoning (v0.1) [Software].
https://github.com/kylieannerichards/aus-reg-bench
```

A working paper will accompany the v0.2 release.

## Licence

- **Code**: MIT Licence (see `LICENSE`)
- **Benchmark items**: CC-BY 4.0
- **Source regulatory text** is not redistributed in this repository. The `corpus/` directory contains build scripts that fetch source text from official publishers (ASIC, APRA, AASB, AustLII). Users rebuild the corpus locally.

## Contact

Kylie-Anne Richards
UTS Business School, University of Technology Sydney

GitHub: [@kylieannerichards](https://github.com/kylieannerichards)
