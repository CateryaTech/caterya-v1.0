"""System traces: the primary evaluation object for agents (model + tools + memory + policy + humans)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from .canonical import digest

STEP_TYPES = ("prompt", "plan", "tool_call", "tool_result", "retrieval", "observation", "decision", "action",
              "human_override", "error", "output")


@dataclass
class TraceStep:
    index: int
    type: str
    name: str = ""
    args: dict = field(default_factory=dict)
    content: str = ""
    ok: bool = True
    scope: Optional[str] = None
    side_effect: float = 0.0
    meta: dict = field(default_factory=dict)


@dataclass
class SystemTrace:
    trace_id: str
    goal: str
    steps: list = field(default_factory=list)       # list[TraceStep | dict]
    outcome: dict = field(default_factory=dict)      # {"success": bool, ...}
    meta: dict = field(default_factory=dict)         # scenario info: expected_actions, inject, fault ...

    def to_dict(self) -> dict:
        return {"trace_id": self.trace_id, "goal": self.goal, "outcome": self.outcome, "meta": self.meta,
                "steps": [asdict(s) if isinstance(s, TraceStep) else s for s in self.steps]}

    def hash(self) -> str:
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> "SystemTrace":
        return cls(d["trace_id"], d.get("goal", ""), [TraceStep(**s) if isinstance(s, dict) else s for s in d["steps"]],
                   d.get("outcome", {}), d.get("meta", {}))
