"""HTTP adapters (stdlib only). Black-box access: OpenAI-compatible chat API and Anthropic Messages API."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from ..core.errors import AdapterError
from ..core.textutil import est_tokens
from .base import Generation, ModelAdapter


def _post(url: str, payload: dict, headers: dict, timeout: float, retries: int) -> dict:
    data = json.dumps(payload).encode()
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - URL allowlisted by caller
                return json.load(r)
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(min(2 ** attempt, 8))
    raise AdapterError(f"request failed after {retries + 1} attempts: {last}")


def _msgs(prompt: str, history: Optional[list]) -> list[dict]:
    m = [{"role": r, "content": t} for r, t in (history or [])]
    return m + [{"role": "user", "content": prompt}]


class OpenAICompatAdapter(ModelAdapter):
    provider = "openai-compatible"

    def __init__(self, base_url: str, model: str, api_key_env: str = "OPENAI_API_KEY", timeout: float = 60,
                 retries: int = 2, max_tokens: int = 512, allowed: list[str] | None = None):
        if allowed is not None and not any(base_url.startswith(a) for a in allowed):
            raise AdapterError(f"endpoint not in allowlist: {base_url}")
        self.base_url, self.model_id, self.api_key_env = base_url.rstrip("/"), model, api_key_env
        self.timeout, self.retries, self.max_tokens, self.name = timeout, retries, max_tokens, model

    def generate(self, prompt, *, system=None, history=None, temperature=0.0, seed=None, **kw) -> Generation:
        msgs = ([{"role": "system", "content": system}] if system else []) + _msgs(prompt, history)
        payload: dict[str, Any] = {"model": self.model_id, "messages": msgs, "temperature": temperature,
                                   "max_tokens": self.max_tokens}
        if seed is not None:
            payload["seed"] = int(seed) % 2**31
        key = os.environ.get(self.api_key_env, "")
        t0 = time.perf_counter()
        d = _post(f"{self.base_url}/chat/completions", payload, {"Authorization": f"Bearer {key}"},
                  self.timeout, self.retries)
        text = d["choices"][0]["message"]["content"] or ""
        u = d.get("usage", {})
        return Generation(text=text, latency_ms=(time.perf_counter() - t0) * 1000,
                          tokens_in=u.get("prompt_tokens", est_tokens(prompt)),
                          tokens_out=u.get("completion_tokens", est_tokens(text)),
                          meta={"model": d.get("model", self.model_id)})


class AnthropicAdapter(ModelAdapter):
    provider = "anthropic"

    def __init__(self, model: str, api_key_env: str = "ANTHROPIC_API_KEY", base_url: str = "https://api.anthropic.com",
                 timeout: float = 60, retries: int = 2, max_tokens: int = 512):
        self.model_id, self.api_key_env, self.base_url = model, api_key_env, base_url.rstrip("/")
        self.timeout, self.retries, self.max_tokens, self.name = timeout, retries, max_tokens, model

    def generate(self, prompt, *, system=None, history=None, temperature=0.0, seed=None, **kw) -> Generation:
        payload: dict[str, Any] = {"model": self.model_id, "max_tokens": self.max_tokens,
                                   "temperature": temperature, "messages": _msgs(prompt, history)}
        if system:
            payload["system"] = system
        hdr = {"x-api-key": os.environ.get(self.api_key_env, ""), "anthropic-version": "2023-06-01"}
        t0 = time.perf_counter()
        d = _post(f"{self.base_url}/v1/messages", payload, hdr, self.timeout, self.retries)
        text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
        u = d.get("usage", {})
        return Generation(text=text, latency_ms=(time.perf_counter() - t0) * 1000,
                          tokens_in=u.get("input_tokens", est_tokens(prompt)),
                          tokens_out=u.get("output_tokens", est_tokens(text)))
