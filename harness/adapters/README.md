# harness/adapters/

Model adapters. Each adapter wraps a provider SDK behind a common interface so the harness can swap models without changing evaluation code.

Planned adapters:

- `anthropic.py` — Claude (Opus, Sonnet, Haiku) via the Anthropic SDK
- `openai.py` — GPT family via the OpenAI SDK
- `google.py` — Gemini family via the Google GenAI SDK

Common interface (sketch):

```python
class Adapter:
    model_id: str
    def complete(self, prompt: str, *, system: str | None = None,
                 temperature: float, max_tokens: int, seed: int | None) -> Completion: ...
```

`Completion` records the raw response, token counts, latency, and any provider-side request ID for traceability.
