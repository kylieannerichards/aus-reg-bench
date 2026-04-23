from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd
from Levenshtein import ratio as levenshtein_ratio

from .completion import Completion


Scorer = Callable[[Completion, dict], dict]


_WS_RE = re.compile(r"\s+")


def _normalise(s: str) -> str:
    return _WS_RE.sub(" ", s).strip().casefold()


def exact_match(completion: Completion, item: dict) -> dict:
    gold = _normalise(item["gold"])
    pred = _normalise(completion.response_text)
    hit = gold in pred
    return {"score": 1.0 if hit else 0.0, "method": "exact_match"}


def fuzzy_match(
    completion: Completion,
    item: dict,
    *,
    threshold: float = 0.85,
) -> dict:
    gold = _normalise(item["gold"])
    pred = _normalise(completion.response_text)
    r = levenshtein_ratio(gold, pred)
    return {
        "score": 1.0 if r >= threshold else 0.0,
        "ratio": r,
        "threshold": threshold,
        "method": "fuzzy_match",
    }


def semantic_match(completion: Completion, item: dict) -> dict:
    return {"score": None, "method": "semantic_match", "note": "not implemented"}


DEFAULT_SCORERS: tuple[Scorer, ...] = (exact_match, fuzzy_match, semantic_match)


def _load_completions(path: Path) -> list[Completion]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(Completion.from_json(line))
    return out


def _load_items(path: Path) -> dict[str, dict]:
    items = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            items[item["item_id"]] = item
    return items


def score_run(
    run_file: Path | str,
    items_file: Path | str,
    scorers: Iterable[Scorer] = DEFAULT_SCORERS,
) -> pd.DataFrame:
    run_path = Path(run_file)
    items_path = Path(items_file)

    completions = _load_completions(run_path)
    items = _load_items(items_path)

    rows = []
    for c in completions:
        item = items.get(c.item_id)
        if item is None:
            continue
        row = {
            "item_id": c.item_id,
            "model": c.model,
            "provider": c.provider,
            "gold": item["gold"],
            "response_text": c.response_text,
            "input_tokens": c.input_tokens,
            "output_tokens": c.output_tokens,
        }
        for scorer in scorers:
            result = scorer(c, item)
            method = result.get("method", scorer.__name__)
            row[f"{method}_score"] = result.get("score")
            for k, v in result.items():
                if k in ("score", "method"):
                    continue
                row[f"{method}_{k}"] = v
        rows.append(row)

    return pd.DataFrame(rows)
