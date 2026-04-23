from __future__ import annotations

from abc import ABC, abstractmethod

from ..completion import Completion


class Adapter(ABC):
    provider: str
    model: str

    @abstractmethod
    def run(self, prompt: str, **kwargs) -> Completion:
        ...
