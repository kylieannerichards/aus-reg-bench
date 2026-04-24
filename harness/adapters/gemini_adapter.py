"""Gemini adapter.

Default model selection:
    If the caller passes ``model=...``, that wins. Otherwise we query
    ``genai.list_models()`` and prefer, in order, the newest
    ``gemini-3-*`` variant, then the newest ``gemini-2.5-*``, then the
    newest ``gemini-2.*``. We only consider models that advertise
    ``generateContent`` support. If listing fails (typically because
    the API key is unset or invalid) we fall back to the hardcoded
    string ``gemini-3-pro`` and let the real request fail later with
    a clearer error.

API key is read from ``GEMINI_API_KEY`` (the name in our spec). If
only ``GOOGLE_API_KEY`` is set we honour that too, since the
``google-generativeai`` SDK's own default reads ``GOOGLE_API_KEY``.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import google.generativeai as genai

from ..completion import Completion
from .base import Adapter


FALLBACK_MODEL = "gemini-3-pro"
_PREFERRED_PREFIXES: tuple[str, ...] = ("gemini-3-", "gemini-2.5-", "gemini-2.")


def _best_available_model() -> str:
    try:
        models = list(genai.list_models())
    except Exception:  # noqa: BLE001 — listing failure → fallback
        return FALLBACK_MODEL
    supported: list[str] = []
    for m in models:
        name = m.name.split("/")[-1] if m.name else ""
        methods = set(getattr(m, "supported_generation_methods", []) or [])
        if name and "generateContent" in methods:
            supported.append(name)
    if not supported:
        return FALLBACK_MODEL
    for prefix in _PREFERRED_PREFIXES:
        matches = sorted((n for n in supported if n.startswith(prefix)), reverse=True)
        if matches:
            return matches[0]
    return sorted(supported, reverse=True)[0]


class GeminiAdapter(Adapter):
    provider = "google"

    def __init__(
        self,
        model: str | None = None,
        *,
        max_tokens: int = 1024,
        system: str | None = None,
    ) -> None:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Neither GEMINI_API_KEY nor GOOGLE_API_KEY is set. "
                "Export one before running the harness."
            )
        genai.configure(api_key=api_key)
        self.model_name = model or _best_available_model()
        self.model = self.model_name
        self.max_tokens = max_tokens
        self.system = system
        self._client = genai.GenerativeModel(
            self.model_name,
            system_instruction=system if system else None,
        )

    def run(self, prompt: str, **kwargs: Any) -> Completion:
        item_id = kwargs.pop("item_id", "")
        max_tokens = kwargs.pop("max_tokens", self.max_tokens)
        system = kwargs.pop("system", None)

        client = self._client
        if system is not None and system != self.system:
            client = genai.GenerativeModel(self.model_name, system_instruction=system)

        resp = client.generate_content(
            prompt,
            generation_config={"max_output_tokens": max_tokens},
        )
        text = getattr(resp, "text", "") or ""

        usage = getattr(resp, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0

        stop_reason = ""
        candidates = getattr(resp, "candidates", None) or []
        if candidates:
            finish = getattr(candidates[0], "finish_reason", "")
            stop_reason = finish.name if hasattr(finish, "name") else str(finish)

        raw: dict[str, Any] = {}
        if hasattr(resp, "to_dict"):
            try:
                raw = resp.to_dict()
            except Exception:  # noqa: BLE001
                raw = {}

        return Completion(
            request_id=f"gemini-{uuid.uuid4().hex[:12]}",
            model=self.model_name,
            provider=self.provider,
            timestamp=datetime.now(timezone.utc),
            prompt=prompt,
            response_text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=stop_reason,
            raw_response=raw,
            item_id=item_id,
        )
