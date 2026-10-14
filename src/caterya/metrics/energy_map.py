"""Registered visualisation metric. The value repeats the two-group parity formula.

It exists so the hashed grid can sit in an Evidence record. It is not a new
fairness criterion.
"""
from __future__ import annotations

from ..core.registry import register_metric
from ..core.types import Domain
from ..metrics.base import Metric, MetricSpec
from ..viz.energy import surface_for_rows


@register_metric
class FairnessEnergyMap(Metric):
    spec = MetricSpec(
        id="fairness_energy_map_v1",
        domain=Domain.FAIRNESS,
        title="Two-group parity surface (visualisation)",
        description="Hash of the grid z=1-|rate_a-rate_b|. The value is the marker height, i.e. the same parity gap.",
        formula="value = 1 - |rate_a - rate_b|; artifact_hash = digest(grid)",
        kind="quantity",
        unit="parity",
        status="research",
        access="black_box",
        pillar="fairness",
        golden="symmetry",
        assumptions=("Exactly two group labels are named via params group_a and group_b.",),
        limitations=(
            "Visualisation of demographic parity, not a physical energy and not an independent test.",
            "Only the named pair is drawn. Other groups are ignored, not averaged in.",
            "Requires tabular_predictions or quantum_fairness rows.",
        ),
    )
    DEFAULTS = {"group_a": None, "group_b": None, "grid": 21}

    def compute(self, ctx):
        if self.p["group_a"] is None or self.p["group_b"] is None:
            return self.untested("params group_a and group_b are required; refusing to pick a pair silently")
        if ctx.has_dataset("quantum_fairness"):
            rows = ctx.dataset("quantum_fairness")
        elif ctx.has_dataset("tabular_predictions"):
            rows = ctx.dataset("tabular_predictions")
        else:
            return self.untested("dataset 'quantum_fairness' or 'tabular_predictions' not provided")
        try:
            surface = surface_for_rows(rows, str(self.p["group_a"]), str(self.p["group_b"]), grid=int(self.p["grid"]))
        except Exception as exc:
            return self.untested(f"{type(exc).__name__}: {exc}")
        result = self.result(surface["marker_parity"], None, len(rows), artifact_hash=surface["artifact_hash"], formula=surface["artifact"]["formula"])
        result.details["grid"] = surface["artifact"]["grid"]
        result.details["marker"] = surface["artifact"]["marker"]
        for note in surface["artifact"]["limitations"]:
            if note not in result.limitations:
                result.limitations.append(note)
        return result
