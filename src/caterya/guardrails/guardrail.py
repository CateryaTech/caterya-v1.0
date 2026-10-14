"""Single-output guardrail.

Decisions are ``pass``, ``fail``, ``remediate``, or ``untested``. The output is
never deleted. ``allow_release`` is a recommendation; deploying, blocking, or
certifying still requires a named decider on the assurance record.

``heuristic`` uses :func:`caterya.guardrails.heuristic.screen`.
``full`` refuses to invent a score when no evaluation dict is supplied.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..core.errors import ConfigError
from ..evidence.model import Evidence
from ..provenance.signing import HmacSigner, Signer
from .evidence import seal_decision
from .heuristic import screen


@dataclass
class GuardrailDecision:
    """Signed recommendation for one agent output."""

    decision: str
    score: Optional[float]
    threshold: float
    mode: str
    allow_release: bool
    output_hash: str
    reason: str
    recommendations: list[str] = field(default_factory=list)
    components: dict = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    evidence: Optional[Evidence] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "score": self.score,
            "threshold": self.threshold,
            "mode": self.mode,
            "allow_release": self.allow_release,
            "output_hash": self.output_hash,
            "reason": self.reason,
            "recommendations": list(self.recommendations),
            "components": self.components,
            "limitations": list(self.limitations),
            "evidence": None if self.evidence is None else self.evidence.to_dict(),
        }


class CATERYAGuardrail:
    """Threshold check that always seals Evidence.

    Parameters
    ----------
    min_score:
        Research default. Not a safety standard. Document the value you actually use.
    signer:
        Evidence signer. A fresh HMAC development signer is used when omitted;
        pass the runner signer for third-party-verifiable Ed25519.
    """

    def __init__(self, min_score: float = 0.70, *, signer: Optional[Signer] = None, system_hash: str = "", profile: str = ""):
        if not 0.0 <= min_score <= 1.0:
            raise ConfigError("min_score must be in [0, 1]")
        self.min_score = float(min_score)
        self.signer = signer or HmacSigner()
        self.system_hash = system_hash
        self.profile = profile
        self._prev = ""

    def check(
        self,
        agent_output: Any,
        *,
        sensitive_context: Optional[dict[str, Any]] = None,
        evaluation: Optional[dict[str, Any]] = None,
        mode: str = "heuristic",
        request_remediation: bool = False,
        assurance_mode: str = "canary",
        seed: int = 0,
    ) -> GuardrailDecision:
        """Record ``pass`` / ``fail`` / ``remediate`` / ``untested``.

        ``request_remediation`` does not rewrite the output. It labels the
        decision ``remediate`` and returns recommendations.
        """
        if mode not in ("heuristic", "full"):
            raise ConfigError("mode must be 'heuristic' or 'full'")
        text = "" if agent_output is None else str(agent_output)
        context = dict(sensitive_context or {})
        if mode == "heuristic":
            screened = screen(text, context)
            score: Optional[float] = float(screened["score"])
            components = screened["components"]
            limitations = list(screened["limitations"])
            output_hash = screened["output_hash"]
            detail = {"weights": screened["weights"], "formula": screened["formula"], "reasons": screened["reasons"], "pii_kinds": screened["pii_kinds"]}
            untested = None
        else:
            screened = screen(text, context)  # still recorded, not used as the score
            output_hash = screened["output_hash"]
            components = {}
            limitations = [
                "Full mode aggregates supplied evaluation scores. It does not run a hidden model.",
                "The mean is not COS and it ignores any metric that was not supplied.",
                "Safety, security and privacy are included only when the caller put them in the score map.",
            ]
            scores = _numeric_scores(evaluation)
            if scores is None:
                score = None
                untested = "full mode requires evaluation={'scores': {...}}; refusing to invent a score"
                detail = {"supplied": False}
            else:
                score = sum(scores.values()) / len(scores)
                components = scores
                detail = {"aggregation": "unweighted_mean", "n_scores": len(scores)}
                untested = None
                limitations.append("Unweighted mean of the supplied scores. Missing metrics are omitted, not filled.")
        hard_flags = [name for name in ("non_empty", "pii", "injection_markers") if components.get(name, 1.0) == 0.0] if mode == "heuristic" else []
        if score is None:
            decision, allow, reason = "untested", False, untested or "not measured"
            recommendations = ["Provide an evaluation result before treating this output as checked."]
        elif score >= self.min_score and not hard_flags:
            decision, allow = "pass", True
            reason = f"score {score:.4f} >= threshold {self.min_score:.4f}"
            recommendations = []
        elif request_remediation:
            decision, allow = "remediate", False
            why = f"hard flags: {', '.join(hard_flags)}" if hard_flags else f"score {score:.4f} < threshold {self.min_score:.4f}"
            reason = why + "; remediation requested, output left unchanged"
            recommendations = _recommendations(components, mode)
        else:
            decision, allow = "fail", False
            if hard_flags and score >= self.min_score:
                reason = f"hard flags ({', '.join(hard_flags)}) force fail even though weighted score {score:.4f} >= {self.min_score:.4f}"
            else:
                reason = f"score {score:.4f} < threshold {self.min_score:.4f}; release not recommended"
            recommendations = _recommendations(components, mode)
        limitations.append("pii, injection_markers and empty output are hard flags: they fail the recommendation even if the weighted mean stays above the threshold.")
        limitations.append("allow_release is a recommendation. It does not block the caller and it is not an assurance decision.")
        evidence = seal_decision(
            self.signer,
            metric_id="guardrail_decision_v1",
            value=score,
            claim=f"guardrail {mode}: {decision}",
            details={
                "decision": decision,
                "threshold": self.min_score,
                "mode": mode,
                "allow_release": allow,
                "output_hash": output_hash,
                "reason": reason,
                "recommendations": recommendations,
                "components": components,
                "hard_flags": hard_flags,
                **detail,
            },
            limitations=limitations,
            prev_hash=self._prev,
            system_hash=self.system_hash,
            profile=self.profile,
            mode=assurance_mode,
            seed=seed,
            n=1 if score is not None else 0,
            untested=untested,
        )
        self._prev = evidence.content_hash
        return GuardrailDecision(
            decision=decision,
            score=score,
            threshold=self.min_score,
            mode=mode,
            allow_release=allow,
            output_hash=output_hash,
            reason=reason,
            recommendations=recommendations,
            components=components,
            limitations=limitations,
            evidence=evidence,
        )


def _numeric_scores(evaluation: Optional[dict[str, Any]]) -> Optional[dict[str, float]]:
    if not evaluation or "scores" not in evaluation:
        return None
    raw = evaluation["scores"]
    if not isinstance(raw, dict) or not raw:
        return None
    out: dict[str, float] = {}
    for key, value in raw.items():
        if value is None:
            continue
        out[str(key)] = float(value)
    return out or None


def _recommendations(components: dict[str, float], mode: str) -> list[str]:
    recs = ["Do not deploy from this signal alone. Record a named human decision if the output will be released or blocked."]
    if mode == "full":
        if components:
            worst = min(components, key=components.get)
            recs.append(f"Lowest supplied score is {worst}={components[worst]:.4f}. Inspect that evidence record, not only this mean.")
        else:
            recs.append("No scores were supplied.")
        return recs
    if components.get("pii", 1) < 1:
        recs.append("PII pattern matched. Review the output before any retention; the pattern list is not a legal definition of personal data.")
    if components.get("injection_markers", 1) < 1:
        recs.append("Injection marker matched. This is a keyword hit, not confirmation of a successful attack.")
    if components.get("non_empty", 1) < 1:
        recs.append("Output is empty.")
    if components.get("policy_keywords", 1) < 1:
        recs.append("must_refuse was set and no refusal marker was found.")
    return recs
