from __future__ import annotations

from ..core.registry import register_metric
from ..core.textutil import is_correct, typo_noise
from ..core.types import Domain
from .base import Metric, MetricSpec
from .stats import bootstrap_ci, mean


def _drop_word(s, r):
    ws = s.split(" ")
    idx = [i for i, w in enumerate(ws) if w.isalpha()]
    if len(idx) > 1:
        del ws[r.choice(idx)]
    return " ".join(ws)


PERTURB = {
    "typo": lambda s, r, rate: typo_noise(s, rate, r),
    "whitespace": lambda s, r, rate: "  " + s.replace(" ", "  ", 2) + " ",
    "case": lambda s, r, rate: s.upper(),
    "word_drop": lambda s, r, rate: _drop_word(s, r),
}


@register_metric
class RobustnessPerturbation(Metric):
    spec = MetricSpec(
        id="robustness_perturbation_v1", domain=Domain.ROBUSTNESS, title="Worst-case accuracy retention under perturbation",
        description="Accuracy on perturbed inputs relative to clean accuracy; worst perturbation family reported.",
        formula="value = min_p [ acc(perturbed_p) / acc(clean) ] clipped to [0,1]", pillar="stability",
        status="stable", assumptions=("Tasks have checkable expected answers.",),
        limitations=("Perturbation families are a sample of possible shifts, not a complete shift model.",))
    DEFAULTS = {"n_prompts": 30, "families": ["typo", "whitespace", "case", "word_drop"]}

    def compute(self, ctx):
        tasks = ctx.dataset("tasks")[: ctx.n(self.p["n_prompts"])]
        rate, fams = ctx.config.perturbation_rate, self.p["families"]
        rows = []
        for t in tasks:
            row = {"clean": float(is_correct(ctx.ask(t["prompt"]).text, t["expected"]))}
            for f in fams:
                row[f] = float(is_correct(ctx.ask(PERTURB[f](t["prompt"], ctx.rng(t["id"], f), rate)).text, t["expected"]))
            rows.append(row)

        def stat(rs):
            a0 = mean([r["clean"] for r in rs])
            return min([min(1.0, mean([r[f] for r in rs]) / a0) if a0 else 0.0 for f in fams]) if fams else 1.0

        return self.result(stat(rows), bootstrap_ci(rows, stat, ctx.config.n_bootstrap, seed=ctx.seed), len(rows),
                           clean_accuracy=mean([r["clean"] for r in rows]), accuracy_by_family={f: mean([r[f] for r in rows]) for f in fams})
