from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

from .adapters.base import Adapter


def _load_adapters() -> dict[str, type[Adapter]]:
    """Lazy-import adapters so a missing SDK only breaks its own adapter."""
    registry: dict[str, type[Adapter]] = {}
    try:
        from .adapters.anthropic_adapter import AnthropicAdapter

        registry["anthropic"] = AnthropicAdapter
    except ImportError as e:
        print(f"note: anthropic adapter unavailable ({e})", file=sys.stderr)
    try:
        from .adapters.openai_adapter import OpenAIAdapter

        registry["openai"] = OpenAIAdapter
    except ImportError as e:
        print(f"note: openai adapter unavailable ({e})", file=sys.stderr)
    try:
        from .adapters.gemini_adapter import GeminiAdapter

        registry["gemini"] = GeminiAdapter
    except ImportError as e:
        print(f"note: gemini adapter unavailable ({e})", file=sys.stderr)
    return registry


def load_items(path: Path) -> list[dict]:
    items: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def build_adapter(
    name: str,
    model: str | None,
    registry: dict[str, type[Adapter]],
) -> Adapter:
    if name not in registry:
        raise ValueError(f"Unknown adapter {name!r}; available: {sorted(registry)}")
    cls = registry[name]
    return cls(model=model) if model else cls()


def make_run_id(adapter_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{adapter_name}"


def _resolve_primary_output(output_arg: Path | None, run_id: str) -> Path:
    if output_arg is None:
        return Path("results/raw") / f"{run_id}.jsonl"
    if output_arg.is_dir() or str(output_arg).endswith("/"):
        return output_arg / f"{run_id}.jsonl"
    return output_arg


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run a benchmark task through a model adapter.")
    p.add_argument("--items", type=Path, required=True, help="Path to a JSONL items file.")
    p.add_argument(
        "--adapter",
        type=str,
        default="anthropic",
        help="Adapter name (anthropic | openai | gemini).",
    )
    p.add_argument("--model", type=str, default=None, help="Optional model override.")
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Primary (backwards-compat) output path. Defaults to results/raw/<run_id>.jsonl.",
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
    registry = _load_adapters()

    items = load_items(args.items)
    if args.limit is not None:
        items = items[: args.limit]

    adapter = build_adapter(args.adapter, args.model, registry)

    run_id = make_run_id(args.adapter)
    primary_path = _resolve_primary_output(args.output, run_id)
    primary_path.parent.mkdir(parents=True, exist_ok=True)

    # Longitudinal mirror: results/longitudinal/YYYY-MM-DD/<adapter>/<run_id>.jsonl
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    longitudinal_path = (
        Path("results/longitudinal") / today / args.adapter / f"{run_id}.jsonl"
    )
    longitudinal_path.parent.mkdir(parents=True, exist_ok=True)

    with primary_path.open("w", encoding="utf-8") as out:
        for item in tqdm(items, desc=f"{args.adapter}:{adapter.model}"):
            completion = adapter.run(item["prompt"], item_id=item["item_id"])
            out.write(completion.to_json() + "\n")
            out.flush()

    shutil.copyfile(primary_path, longitudinal_path)

    print(
        f"Wrote {len(items)} completions to:\n  {primary_path}\n  {longitudinal_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
