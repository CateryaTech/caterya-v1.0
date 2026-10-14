from __future__ import annotations

import json
import os
from pathlib import Path

from ..adapters.base import ModelAdapter
from ..adapters.mock import MockModel
from ..adapters.remote import AnthropicAdapter, OpenAICompatAdapter
from ..core.config import CateryaConfig
from ..core.errors import ConfigError
from ..core.system import SystemDescriptor
from ..evaluators.runner import EvaluationRunner
from ..evidence.store import EvidenceStore


def make_runner(home: str | None = None, cfg: CateryaConfig | None = None) -> EvaluationRunner:
    cfg = cfg or CateryaConfig.from_env()
    home = home or os.environ.get("CATERYA_HOME") or cfg.home
    Path(home).mkdir(parents=True, exist_ok=True)
    return EvaluationRunner(EvidenceStore(Path(home) / "store.db"), None, cfg, home=home)


def make_adapter(kind: str, *, model: str = "", base_url: str = "", api_key_env: str = "", allowed: list | None = None) -> ModelAdapter | None:
    """kind: none | mock[:behavior[:severity]] | openai | anthropic."""
    if kind in ("", "none"):
        return None
    if kind.startswith("mock"):
        parts = kind.split(":")
        return MockModel(parts[1] if len(parts) > 1 else "robust", float(parts[2]) if len(parts) > 2 else 0.5)
    if kind == "openai":
        if not (base_url and model):
            raise ConfigError("openai adapter needs --base-url and --model")
        return OpenAICompatAdapter(base_url, model, api_key_env or "OPENAI_API_KEY", allowed=allowed or None)
    if kind == "anthropic":
        if not model:
            raise ConfigError("anthropic adapter needs --model")
        return AnthropicAdapter(model, api_key_env or "ANTHROPIC_API_KEY")
    raise ConfigError(f"unknown adapter '{kind}'")


def load_system(path: str | None, name: str | None, version: str, model: str = "") -> SystemDescriptor:
    if path:
        return SystemDescriptor.from_dict(json.loads(Path(path).read_text()))
    return SystemDescriptor(name or "unnamed-system", version, model_id=model, model_version=version)
