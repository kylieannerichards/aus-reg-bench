"""Registry of past harness runs.

Scans ``results/longitudinal/`` and returns a DataFrame summarising every run
(date, adapter, model, run_id, item_count, correct_count, exact_match_rate).
Scoring uses the same case-insensitive substring match as
``harness.scoring.exact_match`` so registry numbers line up with the notebook
analyses.

Gold answers are discovered by scanning ``benchmark/tasks/**/items.jsonl``
for items referenced in the run files, so new benchmark tasks are picked up
automatically.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


_WS = re.compile(r"\s+")


def _normalise(s: str) -> str:
    return _WS.sub(" ", s).strip().casefold()


def _gold_lookup(tasks_root: Path) -> dict[str, dict]:
    """Build a dict of item_id -> {gold, metadata} across every items.jsonl."""
    gold: dict[str, dict] = {}
    if not tasks_root.is_dir():
        return gold
    for items_file in tasks_root.rglob("items.jsonl"):
        try:
            for line in items_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                gold[item["item_id"]] = item
        except (OSError, json.JSONDecodeError):
            continue
    return gold


def _score_run_file(run_file: Path, gold: dict[str, dict]) -> tuple[int, int, str]:
    """Return (correct_count, item_count, model) for one run file."""
    correct = 0
    total = 0
    model = ""
    try:
        text = run_file.read_text(encoding="utf-8")
    except OSError:
        return 0, 0, ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not model:
            model = data.get("model", "")
        total += 1
        item = gold.get(data.get("item_id", ""))
        if item is None:
            continue
        if _normalise(item["gold"]) in _normalise(data.get("response_text", "")):
            correct += 1
    return correct, total, model


def list_runs(
    longitudinal_root: Path | str = "results/longitudinal",
    tasks_root: Path | str = "benchmark/tasks",
) -> pd.DataFrame:
    """Return a DataFrame of every run discovered under ``longitudinal_root``.

    Columns: date, adapter, model, run_id, run_file, item_count,
    correct_count, exact_match_rate. Sorted by date ascending then run_id.
    """
    columns = [
        "date",
        "adapter",
        "model",
        "run_id",
        "run_file",
        "item_count",
        "correct_count",
        "exact_match_rate",
    ]
    root = Path(longitudinal_root)
    if not root.is_dir():
        return pd.DataFrame(columns=columns)

    gold = _gold_lookup(Path(tasks_root))
    rows: list[dict] = []
    for date_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for adapter_dir in sorted(p for p in date_dir.iterdir() if p.is_dir()):
            for run_file in sorted(adapter_dir.glob("*.jsonl")):
                correct, total, model = _score_run_file(run_file, gold)
                rows.append(
                    {
                        "date": date_dir.name,
                        "adapter": adapter_dir.name,
                        "model": model,
                        "run_id": run_file.stem,
                        "run_file": str(run_file),
                        "item_count": total,
                        "correct_count": correct,
                        "exact_match_rate": (correct / total) if total else 0.0,
                    }
                )
    return pd.DataFrame(rows, columns=columns)
