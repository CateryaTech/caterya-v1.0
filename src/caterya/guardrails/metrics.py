"""Registered specs for guardrail decisions so Evidence carries a stable spec hash.

The runner can execute the heuristic metric when ``agent_outputs`` is supplied.
It scores; it does not block.
"""
from __future__ import annotations

from ..core.registry import register_metric
from ..core.types import Domain
from ..metrics.base import Metric, MetricSpec
from ..metrics.stats import mean
from .heuristic import screen


@register_metric
class GuardrailDecisionMetric(Metric):
    spec = MetricSpec(
        id="guardrail_decision_v1",
        domain=Domain.AGENTIC,
        title="Guardrail recommendation score",
        description="Heuristic screen or, outside the runner, a mean of supplied evaluation scores. A number here is not a block.",
        formula="heuristic: weighted lexical components; full: unweighted mean of supplied scores",
        status="research",
        access="black_box",
        pillar="transparency",
        assumptions=("The output text presented to the guardrail is the output under review.",),
        limitations=(
            "Research-grade screen or aggregate. Not a safety proof and not a deployment decision.",
            "The runner path is the heuristic. Full mode is only available through CATERYAGuardrail.check.",
            "Passing the threshold does not authorise release. A named decider is still required to finalise assurance.",
            "Keyword lists have high false-negative and false-positive rates.",
            "Empty output, a PII pattern, or an injection marker is a hard flag. The recommendation fails even if the weighted mean stays above the threshold.",
        ),
    )
    DEFAULTS = {}

    def compute(self, ctx):
        if not ctx.has_dataset("agent_outputs"):
            return self.untested("dataset 'agent_outputs' not provided")
        rows = ctx.dataset("agent_outputs")
        scores = [screen(str(row.get("text", row)), row.get("context") or {})["score"] for row in rows]
        return self.result(mean(scores), None, len(scores), formula="mean of heuristic screens")


@register_metric
class EthicsSwarmMetric(Metric):
    spec = MetricSpec(
        id="ethics_swarm_v1",
        domain=Domain.AGENTIC,
        title="Ethics-swarm consensus",
        description="Weighted mean of non-abstaining agent votes. Abstention is not a pass.",
        formula="sum(weight_i * vote_i) / sum(weight_i) over non-abstaining votes",
        status="research",
        access="black_box",
        pillar="transparency",
        assumptions=("Votes are the deterministic functions in caterya.guardrails.swarm.",),
        limitations=(
            "Not a human panel and not a certificate.",
            "Inside the runner this metric is NOT TESTED unless invoked via EthicsSwarm.evaluate, which seals its own Evidence.",
            "Missing pillar scores cause abstention rather than a default of 0.70.",
        ),
    )
    DEFAULTS = {}

    def compute(self, ctx):
        return self.untested("ethics swarm is sealed by EthicsSwarm.evaluate; the runner does not invent votes")
