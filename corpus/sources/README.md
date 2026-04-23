# corpus/sources/

One module per official publisher. Each module exposes a consistent interface:

- `fetch(manifest) -> list[Document]` — downloads source documents
- `normalise(doc) -> NormalisedDocument` — converts to plain text with section structure preserved
- `manifest_entry(doc) -> dict` — metadata (URL, fetched-at, SHA-256) for reproducibility

Planned sources:

- `asic.py` — ASIC Regulatory Guides
- `apra.py` — APRA Prudential Standards
- `aasb.py` — AASB Accounting Standards (including AASB S2)
- `austlii.py` — statutes and instruments via AustLII

Fetchers respect each publisher's `robots.txt` and rate-limit politely.
