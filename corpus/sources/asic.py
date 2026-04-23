"""
Fetch and parse ASIC Regulatory Guides into structured JSON.

ASIC Regulatory Guides are (C) Australian Securities and Investments Commission.
This script fetches HTML copies from asic.gov.au for local parsing; the
parsed per-RG JSON files are gitignored and rebuilt locally. Only the
script itself, the manifest, and the fetch error log are committed.

Usage:
    python -m corpus.sources.asic --limit 3           # smoke-test 3 RGs
    python -m corpus.sources.asic --only 97 168 271   # specific RGs only
    python -m corpus.sources.asic                      # full run (~11 min)
    python -m corpus.sources.asic --dry-run            # discovery only

Discovery:
    ASIC's HTML index page at /regulatory-resources/.../regulatory-guides/
    is JavaScript-rendered (the static HTML has no RG links), so the
    scraper reads https://asic.gov.au/sitemap.xml and extracts the
    /rg-<n>-<slug>/ URLs from it. The HTML index is kept as a fallback.

The full run is deliberately polite:
    - User-Agent identifies the research purpose and repository
    - 2-second delay between requests (configurable with --delay)
    - robots.txt consulted; 401/403 abort, 5xx degrades to advisory
    - At most 2 retries per failed URL; failures are logged and skipped

Scope caveat:
    Each RG's HTML landing page is a short summary (overview text,
    publication metadata, download link for the PDF). The full RG body
    is in the linked PDF. This script captures the landing page only;
    a follow-up PDF extraction pass is future work.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import re
import sys
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "aus-reg-bench/0.1 (research benchmark; "
    "https://github.com/kylieannerichards/aus-reg-bench)"
)

INDEX_URL = "https://asic.gov.au/regulatory-resources/find-a-document/regulatory-guides/"
SITEMAP_URL = "https://asic.gov.au/sitemap.xml"
ROBOTS_URL = "https://asic.gov.au/robots.txt"

# ASIC's own RG index page is JavaScript-rendered and contains no RG
# links in the static HTML, so we rely on the sitemap. Each current RG
# has exactly one URL in the sitemap of the form
#   https://www.asic.gov.au/.../regulatory-guides/rg-<number>-<slug>/
RG_URL_RE = re.compile(r"/regulatory-guides/(rg-(\d+)[^/]*)/?", re.IGNORECASE)
RG_TITLE_RE = re.compile(r"(?:Regulatory Guide\s+|RG\s*)(\d+)\b\s*[:\-]?\s*(.*)", re.IGNORECASE)


log = logging.getLogger("asic")


@dataclasses.dataclass
class IndexEntry:
    rg_number: str
    title: str
    url: str


class Scraper:
    def __init__(
        self,
        output_dir: Path,
        delay: float = 2.0,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.output_dir = output_dir
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.errors: list[dict] = []

    # ---------- HTTP ----------

    def check_robots(self) -> None:
        """Consult robots.txt.

        Standard convention treats a 5xx response as "all disallowed", but
        real-world scrapers (including Googlebot) degrade to advisory mode
        on transient 5xx because government CDNs often 5xx under load.
        We fail-closed only on explicit auth-related responses (401/403)
        and on a 200 that genuinely disallows our target.
        """
        # Fetch robots.txt ourselves rather than via urllib.robotparser so
        # we can tell the difference between 5xx (advisory) and 200 with
        # an explicit Disallow.
        try:
            r = self.session.get(ROBOTS_URL, timeout=self.timeout)
        except requests.RequestException as e:
            log.warning("robots.txt fetch errored (%s); proceeding advisory-mode.", e)
            return
        if r.status_code in (401, 403):
            raise RuntimeError(
                f"robots.txt {ROBOTS_URL} returned {r.status_code}; refusing to fetch."
            )
        if r.status_code >= 500 or r.status_code == 404:
            log.warning(
                "robots.txt returned HTTP %s; proceeding advisory-mode.", r.status_code
            )
            return
        # 2xx: parse and enforce.
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(r.text.splitlines())
        if not rp.can_fetch(USER_AGENT, INDEX_URL):
            raise RuntimeError(
                f"robots.txt disallows {INDEX_URL} for our User-Agent. Aborting."
            )

    def _get(self, url: str) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                r = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                if r.status_code == 200:
                    return r
                last_exc = RuntimeError(f"HTTP {r.status_code}")
            except requests.RequestException as e:
                last_exc = e
            sleep_for = self.delay * (2**attempt)
            log.warning("GET %s failed (%s); retrying in %.1fs", url, last_exc, sleep_for)
            time.sleep(sleep_for)
        raise RuntimeError(f"GET {url} failed after {self.max_retries + 1} attempts: {last_exc}")

    # ---------- Index ----------

    def parse_sitemap(self, xml: str) -> list[IndexEntry]:
        """Extract RG URLs from the ASIC sitemap.xml. Titles are not in the
        sitemap; they are filled in when each RG page is fetched."""
        entries: dict[str, IndexEntry] = {}
        soup = BeautifulSoup(xml, "lxml-xml")
        for loc in soup.find_all("loc"):
            url = (loc.text or "").strip()
            m = RG_URL_RE.search(url)
            if not m:
                continue
            rg_number = m.group(2)
            canonical = url.rstrip("/") + "/"
            entries.setdefault(rg_number, IndexEntry(rg_number, "", canonical))
        return sorted(entries.values(), key=lambda e: int(e.rg_number))

    def parse_index(self, html: str) -> list[IndexEntry]:
        """Fallback: parse RGs out of the HTML index page. ASIC's index is
        currently JS-rendered, so this usually returns []; the sitemap is
        the reliable source."""
        soup = BeautifulSoup(html, "lxml")
        entries: dict[str, IndexEntry] = {}
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = RG_URL_RE.search(href)
            if not m:
                continue
            rg_number = m.group(2)
            title_raw = a.get_text(" ", strip=True)
            tm = RG_TITLE_RE.match(title_raw)
            title = tm.group(2).strip() if tm else title_raw
            full_url = href if href.startswith("http") else (
                "https://asic.gov.au" + href if href.startswith("/") else href
            )
            canonical = full_url.rstrip("/") + "/"
            if rg_number in entries and entries[rg_number].title:
                continue
            entries[rg_number] = IndexEntry(rg_number, title, canonical)
        return sorted(entries.values(), key=lambda e: int(e.rg_number))

    # ---------- Single RG ----------

    def parse_rg(self, html: str, url: str, rg_number: str) -> dict:
        soup = BeautifulSoup(html, "lxml")

        # Title: prefer <h1>, fall back to <title>
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(" ", strip=True)
        if not title and soup.title:
            title = soup.title.get_text(" ", strip=True)

        # Dates — ASIC RG landing pages typically carry "Issued <date>" and
        # optionally "Last updated <date>". The keyword must anchor to a
        # line start or appear after a structural break (e.g. a semicolon
        # in "Issued X; Last updated Y") so we don't catch "Issued"
        # mid-sentence. We capture the date span itself; downstream code
        # can normalise the format.
        text_all = soup.get_text("\n", strip=True)
        _date = r"((?:\d{1,2}\s+)?[A-Z][a-z]+\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
        _anchor = r"(?:^|\n|;\s*)"
        pub = _first_match(
            _anchor + r"\s*(?:Issued|Published|Originally issued)[:\s]+" + _date, text_all
        )
        updated = _first_match(
            _anchor + r"\s*(?:Last updated|Reissued|Updated)[:\s]+" + _date, text_all
        )

        # Main content: strip obvious chrome (nav, footer, scripts, aside) first.
        for tag in soup(["script", "style", "nav", "footer", "aside", "form", "noscript"]):
            tag.decompose()
        main = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_=re.compile("(content|main|rg-body)", re.IGNORECASE))
            or soup.body
            or soup
        )

        # Sections: walk through h2/h3 siblings
        sections: list[dict] = []
        current = {"heading": "", "text": ""}
        for el in main.descendants:
            name = getattr(el, "name", None)
            if name in ("h2", "h3"):
                if current["heading"] or current["text"]:
                    sections.append({**current, "text": current["text"].strip()})
                current = {"heading": el.get_text(" ", strip=True), "text": ""}
            elif name == "p":
                t = el.get_text(" ", strip=True)
                if t:
                    current["text"] += t + "\n"
        if current["heading"] or current["text"]:
            sections.append({**current, "text": current["text"].strip()})

        full_text = "\n\n".join(
            (s["heading"] + "\n" + s["text"]).strip()
            for s in sections
            if s["heading"] or s["text"]
        )

        return {
            "rg_number": rg_number,
            "title": title,
            "publication_date": pub,
            "last_updated": updated,
            "url": url,
            "full_text": full_text,
            "sections": sections,
        }

    # ---------- Orchestration ----------

    def run(
        self,
        limit: int | None = None,
        dry_run: bool = False,
        only: Iterable[str] | None = None,
    ) -> dict:
        started_at = _now_iso()
        try:
            self.check_robots()
            # Sitemap is the reliable source; the HTML index page is JS-rendered.
            log.info("Fetching sitemap: %s", SITEMAP_URL)
            sitemap_xml = self._get(SITEMAP_URL).text
            entries = self.parse_sitemap(sitemap_xml)
            if not entries:
                log.warning("Sitemap yielded no RG URLs; falling back to HTML index.")
                entries = self.parse_index(self._get(INDEX_URL).text)
        except Exception as e:  # noqa: BLE001 — record and return a manifest stub
            log.error("Index/sitemap fetch aborted: %s", e)
            self.errors.append(
                {"rg_number": "INDEX", "url": SITEMAP_URL, "error": str(e)}
            )
            return self._write_manifest([], [], started_at, aborted=str(e))
        log.info("Discovered %d RG URLs", len(entries))

        if only is not None:
            wanted = set(only)
            entries = [e for e in entries if e.rg_number in wanted]

        if limit is not None:
            entries = entries[:limit]

        if dry_run:
            return self._write_manifest(entries, fetched=[], started_at=started_at)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        fetched: list[dict] = []

        for i, entry in enumerate(entries, 1):
            log.info("[%d/%d] RG %s: %s", i, len(entries), entry.rg_number, entry.title[:60])
            try:
                resp = self._get(entry.url)
                rg = self.parse_rg(resp.text, entry.url, entry.rg_number)
                out_path = self.output_dir / f"rg_{entry.rg_number}.json"
                out_path.write_text(json.dumps(rg, ensure_ascii=False, indent=2), encoding="utf-8")
                fetched.append(
                    {
                        "rg_number": entry.rg_number,
                        "title": rg.get("title", entry.title),
                        "url": entry.url,
                        "sections": len(rg.get("sections", [])),
                        "bytes": len(resp.content),
                    }
                )
            except Exception as e:  # noqa: BLE001 — log-and-continue is the point
                log.error("RG %s failed: %s", entry.rg_number, e)
                self.errors.append(
                    {"rg_number": entry.rg_number, "url": entry.url, "error": str(e)}
                )
            time.sleep(self.delay)

        return self._write_manifest(entries, fetched, started_at)

    # ---------- Outputs ----------

    def _write_manifest(
        self,
        entries: list[IndexEntry],
        fetched: list[dict],
        started_at: str,
        aborted: str | None = None,
    ) -> dict:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "source": INDEX_URL,
            "started_at_utc": started_at,
            "completed_at_utc": _now_iso(),
            "user_agent": USER_AGENT,
            "index_entry_count": len(entries),
            "fetched_count": len(fetched),
            "error_count": len(self.errors),
            "aborted_reason": aborted,
            "fetched": fetched,
        }
        (self.output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if self.errors:
            log_lines = [
                f"{e['rg_number']}\t{e['url']}\t{e['error']}" for e in self.errors
            ]
            (self.output_dir / "fetch_errors.log").write_text(
                "\n".join(log_lines) + "\n", encoding="utf-8"
            )
        return manifest


def _first_match(pattern: str, text: str) -> str:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("corpus/sources/asic"),
        help="Directory for rg_<n>.json, manifest.json, fetch_errors.log.",
    )
    p.add_argument("--delay", type=float, default=2.0, help="Seconds between requests (default: 2).")
    p.add_argument("--limit", type=int, default=None, help="Only fetch the first N RGs (smoke test).")
    p.add_argument("--dry-run", action="store_true", help="Parse the index only; don't fetch any RGs.")
    p.add_argument(
        "--only",
        type=str,
        nargs="+",
        default=None,
        help="Only fetch the listed RG numbers (space-separated, e.g. --only 97 168 271).",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="DEBUG-level logging.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    scraper = Scraper(args.output_dir, delay=args.delay)
    manifest = scraper.run(limit=args.limit, dry_run=args.dry_run, only=args.only)
    print(
        f"done: {manifest['fetched_count']}/{manifest['index_entry_count']} RGs fetched, "
        f"{manifest['error_count']} errors",
        file=sys.stderr,
    )
    return 0 if manifest["error_count"] < manifest["index_entry_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
