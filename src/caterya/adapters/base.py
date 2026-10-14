from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..core.textutil import est_tokens


@dataclass
class Generation:
    text: str
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    logprobs: Optional[list] = None
    meta: dict = field(default_factory=dict)
    error: Optional[str] = None


class ModelAdapter(ABC):
    """Vendor-neutral interface. Black-box (text in/text out) is the baseline."""
    name = "adapter"
    provider = "unknown"
    model_id = ""
    model_version = ""
    access_mode = "black_box"

    @abstractmethod
    def generate(self, prompt: str, *, system: Optional[str] = None, history: Optional[list] = None,
                 temperature: float = 0.0, seed: Optional[int] = None, **kw: Any) -> Generation: ...

    def describe(self) -> dict:
        return {"name": self.name, "provider": self.provider, "model_id": self.model_id,
                "model_version": self.model_version, "access_mode": self.access_mode}


class CallableAdapter(ModelAdapter):
    """Wrap any function (any SDK / local model): fn(prompt, system=, history=, temperature=, seed=) -> str|Generation."""

    def __init__(self, fn: Callable[..., Any], name: str = "callable", provider: str = "custom",
                 model_id: str = "", model_version: str = ""):
        self.fn, self.name, self.provider = fn, name, provider
        self.model_id, self.model_version = model_id or name, model_version

    def generate(self, prompt, *, system=None, history=None, temperature=0.0, seed=None, **kw) -> Generation:
        t0 = time.perf_counter()
        out = self.fn(prompt, system=system, history=history, temperature=temperature, seed=seed)
        if isinstance(out, Generation):
            return out
        return Generation(text=str(out), latency_ms=(time.perf_counter() - t0) * 1000,
                          tokens_in=est_tokens(prompt + (system or "")), tokens_out=est_tokens(str(out)))
