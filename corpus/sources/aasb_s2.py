"""
Fetch and parse AASB S2 Climate-related Disclosures into structured JSON.

AASB standards are published by the Australian Accounting Standards Board
(© Commonwealth of Australia). This repository does NOT redistribute the
standard text. The parsed output is rebuilt locally from a copy fetched
from the AASB website (or supplied via --pdf); see corpus/sources/aasb/README.md
for the licensing position.

Usage:
    # Fetch from the AASB website
    python -m corpus.sources.aasb_s2

    # Or parse a local copy
    python -m corpus.sources.aasb_s2 --pdf /path/to/AASB_S2.pdf
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests

USER_AGENT = (
    "aus-reg-bench/0.1 (research benchmark; "
    "https://github.com/kylieannerichards/aus-reg-bench)"
)

# Candidate publication URLs for AASB S2. AASB reorganises its file paths
# occasionally; add new ones here as they appear. The first URL that
# returns a PDF-sized 200 wins. See the README in this directory for why
# we don't pin a single URL.
CANDIDATE_URLS: tuple[str, ...] = (
    "https://www.aasb.gov.au/admin/file/content105/c9/AASB_S2_09-24.pdf",
)

# AASB paragraph numbering:
#   main body     — "1", "2", "10"
#   appendices    — "A1", "B2", "C3", "IG1", "BC1"
PARAGRAPH_RE = re.compile(r"^\s*(IG\d+|BC\d+|[A-D]\d+|\d+)\s+(\S.*)$")

# Section headings in AASB standards are set in all-caps. We use an
# uppercase-run heuristic and a conservative length window to avoid
# collecting shouted words inside paragraph bodies.
SECTION_HEADING_RE = re.compile(r"^[A-Z][A-Z\s,\-()&/'\.]{3,80}$")


def fetch_pdf(urls: Iterable[str], timeout: int = 30) -> tuple[str, bytes]:
    """Try each candidate URL until one returns a PDF-sized 200 response."""
    last_err: str | None = None
    for url in urls:
        try:
            r = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
                allow_redirects=True,
            )
        except requests.RequestException as e:
            last_err = f"{url}: {e!r}"
            continue
        # A real AASB standard PDF is far larger than 10 kB; shorter
        # responses are almost always error pages or redirect stubs.
        if r.status_code == 200 and len(r.content) > 10_000:
            return r.url, r.content
        last_err = f"{url}: HTTP {r.status_code} ({len(r.content)} bytes)"
    raise RuntimeError(
        "All AASB S2 candidate URLs failed. "
        "Supply a local PDF with --pdf <path>. Last error: " + (last_err or "none")
    )


def parse_pdf(pdf_bytes: bytes) -> tuple[list[dict], list[str]]:
    """Parse AASB S2 text into paragraph records + section headings.

    Each record:
        {paragraph_id, text, section_heading, parent_section}

    This is a heuristic parse. The paragraph regex catches the common
    AASB numbering schemes; anything a human reviewer finds misparsed
    should be filed as an issue so the regex set can be extended.
    """
    # Local import so `--help` and unit tests don't require pypdf.
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)

    records: list[dict] = []
    headings: list[str] = []
    current_section = ""
    current_parent = ""
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            current["text"] = current["text"].strip()
            records.append(current)
            current = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue

        # Section heading? Flush any open paragraph first.
        if SECTION_HEADING_RE.fullmatch(line) and not any(c.isdigit() for c in line):
            flush()
            # Short headings (<= 6 words) are treated as top-level parents
            # that later, longer headings live beneath. This matches how
            # AASB standards nest top-level ("OBJECTIVE", "SCOPE") vs
            # inner ("Metrics and Targets") groupings.
            if len(line.split()) <= 6:
                current_parent = line
            current_section = line
            if line not in headings:
                headings.append(line)
            continue

        m = PARAGRAPH_RE.match(line)
        if m:
            flush()
            pid, body = m.group(1), m.group(2)
            current = {
                "paragraph_id": pid,
                "text": body,
                "section_heading": current_section,
                "parent_section": current_parent,
            }
        elif current is not None:
            current["text"] += " " + line

    flush()
    return records, headings


def write_outputs(
    output_dir: Path,
    source: str,
    records: list[dict],
    headings: list[str],
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).isoformat()

    full_path = output_dir / "s2.json"
    summary_path = output_dir / "s2_summary.json"

    with full_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "source": source,
                "fetched_at_utc": fetched_at,
                "standard": "AASB S2 Climate-related Disclosures",
                "paragraphs": records,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "source": source,
                "fetched_at_utc": fetched_at,
                "standard": "AASB S2 Climate-related Disclosures",
                "paragraph_count": len(records),
                "section_count": len(headings),
                "sections": headings,
                "paragraph_id_sample": [r["paragraph_id"] for r in records[:10]],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return full_path, summary_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch & parse AASB S2 into JSON.")
    p.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="Path to a local AASB S2 PDF. If omitted, fetches from AASB.",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("corpus/sources/aasb"),
        help="Directory for s2.json and s2_summary.json.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.pdf is not None:
        source = str(args.pdf)
        pdf_bytes = args.pdf.read_bytes()
    else:
        source, pdf_bytes = fetch_pdf(CANDIDATE_URLS)

    records, headings = parse_pdf(pdf_bytes)
    full_path, summary_path = write_outputs(
        args.output_dir, source, records, headings
    )

    print(f"{len(records)} paragraphs, {len(headings)} sections", file=sys.stderr)
    print(f"Wrote {full_path}", file=sys.stderr)
    print(f"Wrote {summary_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
