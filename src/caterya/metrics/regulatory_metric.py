"""Spec for a regulatory mapping record.

The runner cannot compute this inside the metric loop: the mapping describes
the other evidence of the same evaluation. ``regulatory.seal_mapping`` seals it
afterwards. Invoking the metric directly is an explicit gap, not a score.
"""
from __future__ import annotations

from ..core.registry import register_metric
from ..core.types import Domain
from ..metrics.base import Metric, MetricSpec


@register_metric
class RegulatoryMappingMetric(Metric):
    spec = MetricSpec(
        id="regulatory_mapping_v1",
        domain=Domain.PROVENANCE,
        title="Technical regulatory-mapping coverage",
        description="Fraction of normative mapped clauses that have linked evidence. Not conformity.",
        formula="evidenced_clauses / normative_clauses, after regulatory.map_evidence",
        kind="quantity",
        unit="fraction",
        status="research",
        access="black_box",
        pillar="transparency",
        assumptions=("Clause identifiers are the labels in regulatory/mapping.py and must be checked against official texts.",),
        limitations=(
            "Technical mapping of evidence to themes. Not legal advice, not a conformity assessment, not certification.",
            "A higher fraction means more of the mapped tests were run, not that a statute is satisfied.",
            "Optional research clauses do not count as legal gaps when absent.",
            "Inside the evaluation loop this metric is NOT TESTED; seal it after the other evidence exists.",
        ),
    )
    DEFAULTS = {}

    def compute(self, ctx):
        return self.untested("regulatory mapping is sealed after an evaluation by regulatory.seal_mapping, not inside the metric loop")
