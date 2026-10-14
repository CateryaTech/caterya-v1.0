from __future__ import annotations

from ..core.registry import register_metric
from ..core.types import Domain
from .base import Metric, MetricSpec


@register_metric
class SustainabilityEstimate(Metric):
    spec = MetricSpec(
        id="sustainability_estimate_v1", domain=Domain.SUSTAINABILITY, title="Energy and carbon estimate of the evaluation",
        description="Token-based energy estimate for the evaluation run itself, with PUE and grid carbon intensity.",
        formula="kWh = (tok_in*J_in + tok_out*J_out)/3.6e6 * PUE;  gCO2e = kWh * grid_intensity",
        kind="quantity", unit="kWh", status="experimental",
        assumptions=("J/token and grid intensity are user-supplied; defaults are PLACEHOLDERS.",),
        limitations=("Informational: excluded from COS and risk scoring. Not a lifecycle assessment.",))
    DEFAULTS = {}

    def compute(self, ctx):
        c = ctx.config
        # Totals consumed by earlier metrics are passed by the runner as dataset '__usage__' (hashed, reproducible).
        u = ctx.dataset("__usage__")[0] if ctx.has_dataset("__usage__") else {"tokens_in": 0, "tokens_out": 0, "calls": 0}
        kwh = (u["tokens_in"] * c.joules_per_input_token + u["tokens_out"] * c.joules_per_output_token) / 3.6e6 * c.pue
        return self.result(kwh, None, int(u["calls"]), gco2e=kwh * c.grid_gco2_per_kwh, tokens_in=u["tokens_in"],
                           tokens_out=u["tokens_out"], placeholders=True)


@register_metric
class ProvenanceCompleteness(Metric):
    spec = MetricSpec(
        id="provenance_completeness_v1", domain=Domain.PROVENANCE, title="Provenance completeness of the system record",
        description="Share of required identity/provenance fields (model, version, code, environment, data) that are declared.",
        formula="value = declared_fields / required_fields", pillar="transparency", status="stable",
        limitations=("Measures declaration, not truthfulness; truthfulness needs attestation (level 4).",))
    DEFAULTS = {}

    def compute(self, ctx):
        if ctx.system is None:
            return self.untested("no system descriptor supplied")
        v, missing = ctx.system.completeness()
        return self.result(v, None, 8, missing=missing)
