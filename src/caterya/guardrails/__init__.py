"""Agentic guardrails. Recommendations are signed; they do not silently block."""
from __future__ import annotations

from .adapters import as_crewai_guard, as_langgraph_node
from .guardrail import CATERYAGuardrail, GuardrailDecision
from .swarm import EthicsSwarm, SwarmReport

__all__ = [
    "CATERYAGuardrail",
    "EthicsSwarm",
    "GuardrailDecision",
    "SwarmReport",
    "as_crewai_guard",
    "as_langgraph_node",
]
