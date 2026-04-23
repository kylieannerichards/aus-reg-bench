from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Completion:
    request_id: str
    model: str
    provider: str
    timestamp: datetime
    prompt: str
    response_text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    raw_response: dict[str, Any] = field(default_factory=dict)
    item_id: str = ""

    def to_json(self) -> str:
        d = asdict(self)
        d["timestamp"] = self.timestamp.astimezone(timezone.utc).isoformat()
        return json.dumps(d, ensure_ascii=False, default=str)

    @classmethod
    def from_json(cls, s: str) -> Completion:
        d = json.loads(s)
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        return cls(**d)
