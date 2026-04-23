from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic

from ..completion import Completion
from .base import Adapter

DEFAULT_MODEL = "claude-opus-4-7"


class AnthropicAdapter(Adapter):
    provider = "anthropic"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        max_tokens: int = 1024,
        system: str | None = None,
    ) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Export it before running the harness."
            )
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.system = system

    def run(self, prompt: str, **kwargs: Any) -> Completion:
        item_id = kwargs.pop("item_id", "")
        req: dict[str, Any] = {
            "model": kwargs.pop("model", self.model),
            "max_tokens": kwargs.pop("max_tokens", self.max_tokens),
            "messages": [{"role": "user", "content": prompt}],
        }
        system = kwargs.pop("system", self.system)
        if system is not None:
            req["system"] = system
        req.update(kwargs)

        resp = self.client.messages.create(**req)

        text = "".join(
            getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
        )

        return Completion(
            request_id=resp.id,
            model=resp.model,
            provider=self.provider,
            timestamp=datetime.now(timezone.utc),
            prompt=prompt,
            response_text=text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            stop_reason=resp.stop_reason or "",
            raw_response=resp.model_dump(mode="json") if hasattr(resp, "model_dump") else {},
            item_id=item_id,
        )
