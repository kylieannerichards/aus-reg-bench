# corpus/sources/aasb/

Local outputs from the AASB corpus fetchers in `corpus/sources/aasb_s2.py` (and future AASB scripts).

## What lives here

- `s2.json` — full parsed AASB S2 (paragraph records). **Not redistributed in this repository** — gitignored. Rebuild locally with `python -m corpus.sources.aasb_s2` or `--pdf <path>`.
- `s2_summary.json` — paragraph count, section list, fetch timestamp, sample IDs. Small, tracked in git so reviewers can see the parse worked.
- `README.md` — this file.

## Licensing position

AASB pronouncements, including AASB S2 *Climate-related Disclosures*, are published by the Australian Accounting Standards Board (© Commonwealth of Australia). The AASB licenses the standards for non-commercial use but does not grant a general redistribution right.

This repository takes a conservative position:

1. **We do not redistribute the standard text.** `s2.json` is produced locally and is excluded from version control via `.gitignore`.
2. **We fetch on demand.** The `aasb_s2.py` script fetches from the AASB website for each user who runs it, or accepts a local copy via `--pdf`.
3. **We commit derivative metadata only.** `s2_summary.json` contains paragraph counts, section headings, and sample paragraph IDs — enough for a reviewer to verify a reproducible parse, not enough to reconstruct the source text.
4. **Fair dealing is the evaluation basis.** Using AASB S2 to construct benchmark items for academic research fits the *research or study* fair-dealing heading under the Copyright Act 1968 (Cth) (s 40). Published benchmark items will quote only the minimum excerpt needed to pose the evaluation task, and will cite AASB S2 in full.

If the AASB's licensing position changes, or if the Board grants an explicit distribution permission, update this README and revisit the `.gitignore` entries for the `s2.json` output.

## Current fetch status

The initial `aasb_s2.py` fetch from this sandboxed environment returned HTTP 503 from `www.aasb.gov.au` (the AASB's CDN appears to rate-limit unauthenticated scripted access). The parser is validated against the AASB S2 paragraph structure independently. A working fetch and the resulting `s2_summary.json` will be committed in a follow-up once the script is run from an environment the AASB CDN accepts, or with a locally-supplied PDF via `--pdf`.
