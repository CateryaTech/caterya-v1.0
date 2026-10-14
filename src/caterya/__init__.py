"""CATERYA AI ASSURANCE INFRASTRUCTURE.

Open, vendor-neutral infrastructure that evaluates AI systems, produces verifiable
evidence about their behaviour and risk, preserves provenance and supports
continuous assurance. CATERYA measures and documents; governance decides.
"""
from __future__ import annotations

import importlib

__version__ = "1.0.0a2"
SPEC_VERSION = "caterya.core/v1"
PRODUCT_NAME = "CATERYA AI ASSURANCE INFRASTRUCTURE"

_LAZY = {
    "AssuranceEngine": "caterya.sdk",
    "ProofToken": "caterya.sdk",
    "SystemConfig": "caterya.core.system",
    "SystemDescriptor": "caterya.core.system",
    "CateryaConfig": "caterya.core.config",
    "EvaluationRunner": "caterya.evaluators.runner",
    "Evidence": "caterya.evidence.model",
    "MockModel": "caterya.adapters.mock",
    "CallableAdapter": "caterya.adapters.base",
    "CATERYAGuardrail": "caterya.guardrails",
    "EthicsSwarm": "caterya.guardrails",
}


def __getattr__(name: str):
    if name in _LAZY:
        return getattr(importlib.import_module(_LAZY[name]), name)
    raise AttributeError(f"module 'caterya' has no attribute {name!r}")


__all__ = ["__version__", "SPEC_VERSION", "PRODUCT_NAME", *_LAZY]
