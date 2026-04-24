"""
Generate candidate citation_retrieval items.

For a stratified sample of RGs drawn from corpus/sources/asic/manifest.json,
ask Claude Opus 4.7 to write a plausible Australian financial-services
scenario whose unambiguous answer is that RG. Adversarial items are NOT
generated here — they remain hand-crafted.

Usage:
    python -m benchmark.tasks.citation_retrieval.generate_candidates \\
        --manifest corpus/sources/asic/manifest.json \\
        --output benchmark/tasks/citation_retrieval/candidates.jsonl \\
        --target-easy 40 --target-medium 20 --seed 42

Environment:
    ANTHROPIC_API_KEY must be set.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from anthropic import Anthropic


MODEL = "claude-opus-4-7"

# Difficulty heuristic: if a title contains any EASY_KEYWORDS it goes in
# the easy pool, otherwise in the medium pool. Tuned for ASIC's topic
# distribution — PDS, AFSL, advice, IDR, DDO are everyday concepts for
# an Australian compliance practitioner; niche topics (benchmarks,
# crowdfunding, particular industry codes) are medium.
EASY_KEYWORDS = (
    "product disclosure",
    "pds",
    "afsl",
    "licensing",
    "disclosure",
    "financial advice",
    "personal advice",
    "managed investment",
    "credit",
    "insurance",
    "audit",
    "superannuation",
    "internal dispute",
    "external dispute",
    "conduct",
    "design and distribution",
)

# RGs we deliberately skip — either meta / superseded / non-substantive.
SKIP_TITLE_SUBSTRINGS = (
    "withdrawn",
    "superseded",
    "consultation paper",
)


@dataclass
class RG:
    number: str
    title: str
    url: str

    @property
    def slug(self) -> str:
        t = self.title.lower()
        if any(sub in t for sub in SKIP_TITLE_SUBSTRINGS):
            return "skip"
        return "easy" if any(kw in t for kw in EASY_KEYWORDS) else "medium"


SYSTEM_PROMPT = (
    "You are helping construct evaluation items for an Australian financial regulation "
    "benchmark. You will be given one ASIC Regulatory Guide (RG) by number and title. "
    "Write a single plausible scenario-based question that an Australian financial-services "
    "compliance practitioner might ask, whose unambiguous answer is the specified RG.\n\n"
    "Constraints:\n"
    "- Do NOT name the RG number in the scenario.\n"
    "- Do NOT directly quote the RG title in the scenario.\n"
    "- Make the scenario specific enough that only one RG plausibly applies.\n"
    "- End with the exact sentence: Answer with the RG number only (for example: \"RG 123\").\n"
    "- Output ONLY the scenario question. No preamble. No commentary. No 'Sure, here is ...'."
)


def load_manifest(manifest_path: Path) -> list[RG]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    rgs: list[RG] = []
    for entry in data.get("fetched", []):
        rgs.append(
            RG(
                number=entry["rg_number"],
                title=entry.get("title", "").strip(),
                url=entry.get("url", ""),
            )
        )
    return rgs


def stratify(rgs: Iterable[RG]) -> tuple[list[RG], list[RG], list[RG]]:
    easy, medium, skipped = [], [], []
    for rg in rgs:
        bucket = rg.slug
        if bucket == "skip":
            skipped.append(rg)
        elif bucket == "easy":
            easy.append(rg)
        else:
            medium.append(rg)
    return easy, medium, skipped


def sample(pool: list[RG], n: int, rng: random.Random) -> list[RG]:
    return rng.sample(pool, k=min(n, len(pool)))


def generate_scenario(client: Anthropic, rg: RG) -> str:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"RG number: RG {rg.number}\nTitle: {rg.title}\nURL: {rg.url}",
            }
        ],
    )
    text_parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
    return "\n".join(text_parts).strip()


_RG_TOKEN_RE = re.compile(r"\bRG\s*\d+\b", re.IGNORECASE)


def scenario_is_clean(scenario: str, rg: RG) -> tuple[bool, str]:
    """Sanity-check generated scenarios.

    Returns (ok, reason). A scenario is clean if it (a) does not name
    any RG number and (b) ends with the required answer-format line.
    """
    rg_mentions = _RG_TOKEN_RE.findall(scenario)
    # The required trailing line contains "RG 123" as an example, so one
    # mention is expected; more than one is a leak.
    non_example_mentions = [m for m in rg_mentions if m.upper().replace(" ", "") not in {"RG123"}]
    if non_example_mentions:
        return False, f"scenario mentions RG explicitly: {non_example_mentions}"
    if "Answer with the RG number only" not in scenario:
        return False, "scenario missing required answer-format line"
    return True, ""


def build_item(rg: RG, scenario: str, difficulty: str, index: int) -> dict:
    return {
        "item_id": f"cr-gen-{index:03d}",
        "prompt": scenario,
        "gold": f"RG {rg.number}",
        "metadata": {
            "difficulty": difficulty,
            "domain": "ASIC",
            "source_url": rg.url,
            "generated_by": MODEL,
            "generation_seed_rg": rg.number,
            "generation_seed_title": rg.title,
            "needs_human_review": True,
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--manifest",
        type=Path,
        default=Path("corpus/sources/asic/manifest.json"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark/tasks/citation_retrieval/candidates.jsonl"),
    )
    p.add_argument("--target-easy", type=int, default=40)
    p.add_argument("--target-medium", type=int, default=20)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between generation calls (polite, rate-limit-friendly).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rng = random.Random(args.seed)

    rgs = load_manifest(args.manifest)
    if not rgs:
        print(f"no RGs found in {args.manifest}", file=sys.stderr)
        return 1

    easy_pool, medium_pool, skipped = stratify(rgs)
    print(
        f"pool: {len(easy_pool)} easy candidates, {len(medium_pool)} medium, "
        f"{len(skipped)} skipped",
        file=sys.stderr,
    )

    chosen_easy = sample(easy_pool, args.target_easy, rng)
    chosen_medium = sample(medium_pool, args.target_medium, rng)

    client = Anthropic()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    rejected: list[dict] = []
    written = 0

    with args.output.open("w", encoding="utf-8") as out:
        for i, rg in enumerate(chosen_easy + chosen_medium, 1):
            difficulty = "easy" if rg in chosen_easy else "medium"
            try:
                scenario = generate_scenario(client, rg)
            except Exception as e:  # noqa: BLE001 — record, keep going
                rejected.append({"rg_number": rg.number, "reason": f"api-error: {e}"})
                continue
            ok, reason = scenario_is_clean(scenario, rg)
            if not ok:
                rejected.append({"rg_number": rg.number, "reason": reason, "scenario": scenario})
                continue
            item = build_item(rg, scenario, difficulty, i)
            out.write(json.dumps(item, ensure_ascii=False) + "\n")
            out.flush()
            written += 1
            time.sleep(args.delay)

    summary = {
        "model": MODEL,
        "target_easy": args.target_easy,
        "target_medium": args.target_medium,
        "chosen_easy": [r.number for r in chosen_easy],
        "chosen_medium": [r.number for r in chosen_medium],
        "written_count": written,
        "rejected_count": len(rejected),
        "rejected": rejected,
        "skipped_at_pool_stage": [
            {"rg_number": r.number, "title": r.title} for r in skipped
        ],
    }
    summary_path = args.output.with_name(args.output.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"generated {written}/{args.target_easy + args.target_medium} candidates, "
        f"{len(rejected)} rejected. Output: {args.output}. Summary: {summary_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
