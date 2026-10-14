"""Thin adapters. They do not import LangGraph or CrewAI until asked, and they do not drop outputs.

CATERYA's decision is attached to the payload. The host framework is not told
to discard the message: a silent block would hide the output from the evidence
the human still needs to see.
"""
from __future__ import annotations

from typing import Any, Callable

from .guardrail import CATERYAGuardrail, GuardrailDecision


def as_langgraph_node(guardrail: CATERYAGuardrail, *, output_key: str = "output", mode: str = "heuristic") -> Callable[[dict], dict]:
    """Return a pure ``(state) -> state`` function usable as a LangGraph node.

    The original output is preserved. ``caterya_allow_release`` is advisory.
    """

    def node(state: dict) -> dict:
        if not isinstance(state, dict):
            raise TypeError("langgraph adapter expects a dict state")
        text = state.get(output_key)
        if text is None and state.get("messages"):
            last = state["messages"][-1]
            text = last.get("content", last) if isinstance(last, dict) else str(last)
        decision = guardrail.check(text if text is not None else "", mode=mode, sensitive_context=state.get("caterya_context"))
        return {**state, "caterya_guardrail": decision.to_dict(), "caterya_allow_release": decision.allow_release}

    return node


def as_crewai_guard(guardrail: CATERYAGuardrail, *, mode: str = "heuristic") -> Callable[[Any], tuple[bool, Any]]:
    """Return a CrewAI-style ``(output) -> (bool, payload)`` callable.

    The boolean is always ``True`` so the framework does not swallow the output.
    Read ``payload['caterya']['allow_release']`` and the Evidence id. Blocking,
    if required, is a separate explicit policy gate with a named decider.
    """

    def _guard(output: Any) -> tuple[bool, dict[str, Any]]:
        raw = getattr(output, "raw", None)
        text = raw if isinstance(raw, str) else str(output)
        decision: GuardrailDecision = guardrail.check(text, mode=mode)
        return True, {"output": text, "caterya": decision.to_dict(), "allow_release": decision.allow_release}

    return _guard
