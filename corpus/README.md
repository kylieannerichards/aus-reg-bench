# corpus/

Build scripts and tooling to assemble the Australian regulatory corpus *locally*. Source regulatory text is **not** redistributed in this repository — users rebuild the corpus on their own machine by running scripts here against the official publishers.

Planned contents:

- `build_corpus.py` — top-level entrypoint; invokes per-source fetchers
- `sources/` — one module per publisher (ASIC, APRA, AASB, AustLII)
- Output: a local `corpus/data/` directory (gitignored) containing normalised text and a manifest with hashes and fetch timestamps for reproducibility

The corpus build is deterministic given a manifest: rerunning with the same manifest reproduces the same byte content, or fails loudly if an upstream document has changed.
