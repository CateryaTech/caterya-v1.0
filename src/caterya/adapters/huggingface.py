"""Local Hugging Face adapter (lazy import). Gray/white-box hooks can extend this class."""
from __future__ import annotations

import time

from ..core.errors import CapabilityUnavailable
from ..core.textutil import est_tokens
from .base import Generation, ModelAdapter


class HuggingFaceAdapter(ModelAdapter):
    provider = "huggingface"
    access_mode = "white_box"

    def __init__(self, model_id: str, max_new_tokens: int = 128, **pipeline_kw):
        try:
            from transformers import pipeline  # type: ignore
        except Exception as e:  # pragma: no cover
            raise CapabilityUnavailable("pip install transformers torch") from e
        self.model_id, self.name, self.max_new_tokens = model_id, model_id, max_new_tokens
        self._pipe = pipeline("text-generation", model=model_id, **pipeline_kw)

    def generate(self, prompt, *, system=None, history=None, temperature=0.0, seed=None, **kw) -> Generation:  # pragma: no cover
        if seed is not None:
            from transformers import set_seed  # type: ignore
            set_seed(int(seed) % 2**31)
        text_in = "\n".join(([system] if system else []) + [f"{r}: {t}" for r, t in (history or [])] + [prompt])
        t0 = time.perf_counter()
        out = self._pipe(text_in, max_new_tokens=self.max_new_tokens, do_sample=temperature > 0,
                         temperature=max(temperature, 1e-5), return_full_text=False)[0]["generated_text"]
        return Generation(text=out, latency_ms=(time.perf_counter() - t0) * 1000,
                          tokens_in=est_tokens(text_in), tokens_out=est_tokens(out))
