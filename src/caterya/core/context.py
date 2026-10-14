"""Evaluation context: the only place model calls happen, so every call is logged and hashable."""
from __future__ import annotations

import random
import time
from typing import Any, Optional

from .canonical import derive_seed, digest
from .config import CateryaConfig
from .errors import AdapterError, ConfigError


class EvalContext:
    def __init__(self, adapter=None, config: Optional[CateryaConfig] = None, datasets: Optional[dict] = None,
                 seed: Optional[int] = None, system=None):
        self.adapter = adapter
        self.config = config or CateryaConfig()
        self.datasets = datasets or {}
        self.seed = self.config.seed if seed is None else seed
        self.system = system
        self.errors = 0
        self.begin()

    # --- lifecycle -------------------------------------------------------
    def begin(self) -> None:
        self.raw_log: list[dict] = []
        self.used: dict[str, Any] = {}
        self.calls = self.tokens_in = self.tokens_out = 0
        self.latency_ms = 0.0
        self.errors = 0

    # --- helpers ---------------------------------------------------------
    def derive(self, *parts: Any) -> int:
        return derive_seed(self.seed, *parts)

    def rng(self, *parts: Any) -> random.Random:
        return random.Random(self.derive(*parts))

    def n(self, base: int) -> int:
        return max(1, int(round(base * self.config.tier())))

    def dataset(self, name: str) -> list:
        if name not in self.datasets:
            raise ConfigError(f"dataset '{name}' not provided")
        self.used[name] = self.datasets[name]
        return self.datasets[name]

    def has_dataset(self, name: str) -> bool:
        return name in self.datasets

    def ask(self, prompt: str, *, system: Optional[str] = None, history: Optional[list] = None,
            temperature: float = 0.0, seed: Optional[int] = None):
        from ..adapters.base import Generation
        if self.adapter is None:
            raise AdapterError("no model adapter supplied for this metric")
        t0 = time.perf_counter()
        try:
            g = self.adapter.generate(prompt, system=system, history=history, temperature=temperature, seed=seed)
        except Exception as e:  # recorded, never hidden
            self.errors += 1
            g = Generation(text="", error=f"{type(e).__name__}: {e}")
        self.calls += 1
        self.tokens_in += g.tokens_in
        self.tokens_out += g.tokens_out
        self.latency_ms += g.latency_ms or (time.perf_counter() - t0) * 1000
        self.raw_log.append({"prompt": prompt, "system": system, "history": len(history or []),
                             "temperature": temperature, "seed": seed, "output": g.text, "error": g.error})
        return g

    def dataset_hash(self) -> str:
        return digest({k: digest(v) for k, v in sorted(self.used.items())}) if self.used else ""

    def dataset_hashes(self) -> dict:
        return {k: digest(v) for k, v in sorted(self.used.items())}

    def raw_hash(self) -> str:
        return digest(self.raw_log)
