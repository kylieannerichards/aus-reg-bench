# corpus/sources/asic/

Local outputs from the ASIC corpus scraper in `corpus/sources/asic.py`.

## What lives here

- `rg_<number>.json` — parsed landing page for each current ASIC Regulatory Guide (title, URL, publication/updated dates, section headings, overview text, full-text slice). **Not redistributed in this repository** — gitignored. Rebuild locally with `python -m corpus.sources.asic`.
- `manifest.json` — per-RG metadata (number, title, URL, section count, HTML bytes), fetch start/end timestamps, counts of successes and errors. Tracked in git.
- `fetch_errors.log` — tab-separated `rg_number\turl\terror` lines for any RG that failed after two retries. Tracked in git.
- `README.md` — this file.

## How discovery works

ASIC's HTML index page at `/regulatory-resources/find-a-document/regulatory-guides/` is JavaScript-rendered; the static HTML contains no `rg-<n>` links. The scraper instead reads `https://asic.gov.au/sitemap.xml` (2 MB, ~274 current RGs), extracts `rg-<n>-<slug>/` URLs with a regex, and fetches each in order.

**Caveat on content scope.** Each RG's public HTML page is a short landing page (overview paragraph, publication metadata, download links for the PDF version) — not the full guidance text. ASIC publishes the full RG body as a linked PDF. The scraper captures the landing page only, per the benchmark's spec ("HTML version — HTML is easier to parse"). If the full body is needed downstream, a follow-up pass should fetch each RG's PDF link and run it through a PDF extractor.

## Licensing position

ASIC Regulatory Guides are published by the Australian Securities and Investments Commission (© ASIC). This repository takes a conservative position on redistribution:

1. **Full-text parsed RGs are not redistributed here.** `rg_<n>.json` files are produced locally and are gitignored.
2. **We fetch on demand.** The scraper downloads from asic.gov.au using a User-Agent that identifies the research purpose and repository.
3. **We commit only derivative metadata.** `manifest.json` contains per-RG title, URL, section count, and byte count — enough for a reviewer to verify a reproducible parse, not enough to reconstruct the source text.
4. **Fair dealing is the evaluation basis.** Using ASIC RGs to construct benchmark items for academic research fits the *research or study* fair-dealing heading under the Copyright Act 1968 (Cth) (s 40). Published benchmark items will quote only the minimum excerpt needed to pose the evaluation task, and will cite each RG in full.

## Polite scraping

`asic.py` respects ASIC's systems:

- **User-Agent** identifies the project and repository URL.
- **2-second delay** between requests (`--delay 2`) — configurable; do not go below 1 second without an ASIC permission conversation.
- **robots.txt** consulted on startup. Explicit 401/403 aborts; transient 5xx degrades to advisory mode (matching Googlebot behaviour).
- **At most 2 retries** per failed URL with exponential backoff (2s, 4s, 8s) before giving up.
- **Failures logged, not retried indefinitely** — per-RG errors are appended to `fetch_errors.log` and the scrape continues with the next RG.

A full run touches ~274 RG pages. At 2-second delay plus the ~0.5 s mean transfer time per page, the wall-clock cost is about 11 minutes. Expect this to drift upward if ASIC's CDN returns transient 5xx.
