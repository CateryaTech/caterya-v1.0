"""Python SDK: AssuranceEngine facade, agent guard hook, proof tokens."""
from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import asdict, dataclass, field
from functools import wraps
from typing import Any, Callable, Optional

from .assurance.policy import Policy, gate
from .assurance.record import attach_attestation, finalize
from .assurance.regression import compare
from .core.canonical import canonical_bytes
from .core.clock import iso, utcnow
from .core.config import CateryaConfig
from .core.errors import PolicyViolation
from .core.system import SystemDescriptor
from .core.trace import SystemTrace, TraceStep
from .evaluators.runner import EvaluationResult, EvaluationRunner
from .provenance.attestation import make_dsse, statement_for_car
from .provenance.signing import Signer

SystemConfig = SystemDescriptor


@dataclass
class ProofToken:
    """Per-decision proof: SHA3-256 state hash + timestamp + checked invariants, signed."""
    tool: str
    allowed: bool
    state_hash: str
    timestamp: str
    invariants: dict
    reasons: list = field(default_factory=list)
    key_id: str = ""
    signature: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class AssuranceEngine:
    def __init__(self, system: SystemDescriptor, *, home: Optional[str] = None, config: Optional[CateryaConfig] = None,
                 runner: Optional[EvaluationRunner] = None):
        self.system = system
        self.runner = runner or EvaluationRunner(config=config, home=home)
        self.cfg = self.runner.cfg
        self.last: Optional[EvaluationResult] = None

    # evaluation ------------------------------------------------------
    def evaluate(self, adapter=None, profile: str = "CATERYA-LLM", **kw: Any) -> EvaluationResult:
        self.last = self.runner.run(self.system, adapter, profile, **kw)
        return self.last

    def decide(self, car_id: str, decision: str, decided_by: str, role: str, rationale: str = "", **kw: Any) -> dict:
        car = self.runner.store.get_doc("car", car_id)
        new = finalize(car, {"decision": decision, "decided_by": decided_by, "role": role, "rationale": rationale, **kw},
                       self.runner.signer, self.cfg, self.runner.clock())
        self.runner.store.put_doc("car", car_id, new, new["system"]["name"], new["evaluation"]["timestamp"])
        self.runner.store.put_doc("car_version", f"{car_id}@{new['version']}", new, new["system"]["name"], new["evaluation"]["timestamp"])
        return new

    def attest(self, car: dict, attester: Signer) -> dict:
        return make_dsse(statement_for_car(car), attester)

    def accept_attestation(self, car: dict, envelope: dict, verifier) -> dict:
        new = attach_attestation(car, envelope, verifier, self.runner.signer, self.cfg, self.runner.clock())
        self.runner.store.put_doc("car", new["car_id"], new, new["system"]["name"], new["evaluation"]["timestamp"])
        return new

    def gate(self, car: dict, policy: Policy, previous: Optional[dict] = None) -> dict:
        return gate(car, policy, compare(previous, car, self.cfg) if previous else None, self.runner.clock())

    # runtime guard ---------------------------------------------------
    def guard(self, policy: dict, goal: str = "", human_approver: Optional[Callable[[str, dict], bool]] = None) -> "AgentGuard":
        return AgentGuard(self, policy, goal, human_approver)


class AgentGuard:
    """Low-latency pre-execution hook for agent tool calls. Inline checking is intended for HIGH-RISK actions only."""

    def __init__(self, engine: AssuranceEngine, policy: dict, goal: str = "", approver=None):
        self.engine, self.policy, self.goal, self.approver = engine, policy, goal, approver
        self.steps: list[TraceStep] = []
        self.tokens: list[ProofToken] = []
        self._last: Any = None
        self._run = 0
        self._lock = threading.Lock()

    def check(self, tool: str, args: dict, scope: Optional[str] = None) -> ProofToken:
        pol, reasons = self.policy, []
        spec = pol["allowed_tools"].get(tool)
        if tool in pol.get("forbidden_tools", []) or spec is None:
            reasons.append("tool not allowed")
        else:
            if scope and scope not in spec["scopes"]:
                reasons.append(f"scope '{scope}' not permitted for tool")
            order = pol.get("scope_order", ["read", "write", "admin"])
            if scope and scope in order and order.index(scope) > order.index(pol.get("granted_scope", "read")):
                reasons.append("privilege escalation above granted scope")
            for a, rx in spec.get("arg_constraints", {}).items():
                if a in args and not re.match(rx, str(args[a])):
                    reasons.append(f"argument '{a}' violates constraint")
            if spec.get("requires_human") and not (self.approver and self.approver(tool, args)):
                reasons.append("human approval required")
        key = (tool, str(sorted(args.items())))
        with self._lock:
            self._run = self._run + 1 if key == self._last else 1
            self._last = key
            if self._run > pol.get("max_repeat", 3):
                reasons.append("repeat limit exceeded (possible loop)")
            if len(self.steps) >= pol.get("max_steps", 50):
                reasons.append("step budget exceeded")
            idx = len(self.steps)
        state = {"tool": tool, "args": args, "idx": idx, "reasons": reasons, "goal": self.goal}
        tok = ProofToken(tool, not reasons, "sha3-256:" + hashlib.sha3_256(canonical_bytes(state)).hexdigest(),
                         iso(utcnow()), {"allowed_list": spec is not None, "repeat_run": self._run, "step": idx}, reasons,
                         self.engine.runner.signer.key_id)
        tok.signature = self.engine.runner.signer.sign(canonical_bytes({k: v for k, v in tok.to_dict().items() if k != "signature"}))
        with self._lock:
            self.steps.append(TraceStep(idx, "tool_call", tool, args, "", not reasons, scope))
            self.tokens.append(tok)
        return tok

    def tool(self, name: str, scope: Optional[str] = None):
        """Decorator: block (raise PolicyViolation) or allow; attaches the ProofToken as `fn.last_proof`."""
        def deco(fn):
            @wraps(fn)
            def wrapper(*a, **kw):
                tok = self.check(name, kw or {"args": a}, scope)
                wrapper.last_proof = tok
                if not tok.allowed:
                    raise PolicyViolation(f"{name} blocked: {'; '.join(tok.reasons)}", tok.reasons)
                return fn(*a, **kw)
            return wrapper
        return deco

    def trace(self, outcome: Optional[dict] = None, meta: Optional[dict] = None) -> SystemTrace:
        return SystemTrace("TR-live", self.goal, list(self.steps), outcome or {}, meta or {})
