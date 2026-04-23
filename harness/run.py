from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

from .adapters.anthropic_adapter import AnthropicAdapter
from .adapters.base import Adapter


ADAPTERS: dict[str, type[Adapter]] = {
    "anthropic": AnthropicAdapter,
}


def load_items(path: Path) -> list[dict]:
    items = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def build_adapter(name: str, model: str | None) -> Adapter:
    if name not in ADAPTERS:
        raise ValueError(f"Unknown adapter {name!r}; available: {sorted(ADAPTERS)}")
    cls = ADAPTERS[name]
    if model:
        return cls(model=model)
    return cls()


def make_run_id(adapter_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{adapter_name}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run a benchmark task through a model adapter.")
    p.add_argument("--items", type=Path, required=True, help="Path to a JSONL items file.")
    p.add_argument("--adapter", type=str, default="anthropic", help="Adapter name.")
    p.add_argument("--model", type=str, default=None, help="Optional model override.")
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSONL path. Defaults to results/raw/<run_id>.jsonl.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only run the first N items (useful for smoke tests).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    items = load_items(args.items)
    if args.limit is not None:
        items = items[: args.limit]

    adapter = build_adapter(args.adapter, args.model)

    run_id = make_run_id(args.adapter)
    if args.output is None:
        output_path = Path("results/raw") / f"{run_id}.jsonl"
    elif args.output.is_dir() or str(args.output).endswith("/"):
        output_path = args.output / f"{run_id}.jsonl"
    else:
        output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as out:
        for item in tqdm(items, desc=f"{args.adapter}:{adapter.model}"):
            completion = adapter.run(item["prompt"], item_id=item["item_id"])
            out.write(completion.to_json() + "\n")

    print(f"Wrote {len(items)} completions to {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
