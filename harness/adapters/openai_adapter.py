"""OpenAI adapter.

Default model selection:
    If the caller passes ``model=...``, that wins. Otherwise we query
    ``client.models.list()`` at construction time and pick the newest
    id starting with "gpt-5" (sorted lexicographically descending).
    If no gpt-5 variant is visible to this API key, we fall back to
    ``gpt-4-turbo``. If the listing call itself fails (typically
    because the API key is unset or invalid) we fall back to the
    hardcoded string ``gpt-5`` and let the real request fail later
    with a clearer error.

    We use ``max_completion_tokens`` rather than the deprecated
    ``max_tokens``, since gpt-5-family models reject the latter.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI

from ..completion import Completion
from .base import Adapter


FALLBACK_MODEL = "gpt-5"
SECONDARY_FALLBACK_MODEL = "gpt-4-turbo"


def _best_available_model(client: OpenAI) -> str:
    try:
        model_ids = [m.id for m in client.models.list().data]
    except Exception:  # noqa: BLE001 — any listing failure → fallback
        return FALLBACK_MODEL
    gpt5 = sorted((m for m in model_ids if m.startswith("gpt-5")), reverse=True)
    if gpt5:
        return gpt5[0]
    if SECONDARY_FALLBACK_MODEL in model_ids:
        return SECONDARY_FALLBACK_MODEL
    return FALLBACK_MODEL


class OpenAIAdapter(Adapter):
    provider = "openai"

    def __init__(
        self,
        model: str | None = None,
        *,
        max_tokens: int = 1024,
        system: str | None = None,
    ) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set. Export it before running the harness.")
        self.client = OpenAI(api_key=api_key)
        self.model = model or _best_available_model(self.client)
        self.max_tokens = max_tokens
        self.system = system

    def run(self, prompt: str, **kwargs: Any) -> Completion:
        item_id = kwargs.pop("item_id", "")
        messages: list[dict] = []
        system = kwargs.pop("system", self.system)
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        req: dict[str, Any] = {
            "model": kwargs.pop("model", self.model),
            "messages": messages,
            "max_completion_tokens": kwargs.pop("max_tokens", self.max_tokens),
        }
        req.update(kwargs)

        resp = self.client.chat.completions.create(**req)
        choice = resp.choices[0]
        text = choice.message.content or ""
        usage = resp.usage

        return Completion(
            request_id=resp.id,
            model=resp.model,
            provider=self.provider,
            timestamp=datetime.now(timezone.utc),
            prompt=prompt,
            response_text=text,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            stop_reason=choice.finish_reason or "",
            raw_response=resp.model_dump(mode="json") if hasattr(resp, "model_dump") else {},
            item_id=item_id,
        )
