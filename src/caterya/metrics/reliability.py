from __future__ import annotations

import re

from ..core.registry import register_metric
from ..core.textutil import answer_key, is_correct
from ..core.types import Domain
from ..datasets import INSTR_CONF
from .base import Metric, MetricSpec
from .stats import bootstrap_ci, ece, mean


@register_metric
class TaskReliability(Metric):
    spec = MetricSpec(
        id="reliability_v1", domain=Domain.RELIABILITY, title="Task success, consistency and error rate",
        description="Repeated attempts per task (seeded); success rate with consistency and adapter error rate.",
        formula="value = mean task success; also pairwise answer agreement across repeats and error rate",
        status="stable", limitations=("Success is judged against the dataset's expected answer only.",))
    DEFAULTS = {"n_prompts": 20, "repeats": 3, "temperature": 0.3}

    def compute(self, ctx):
        tasks, rows = ctx.dataset("tasks")[: ctx.n(self.p["n_prompts"])], []
        cons = []
        for t in tasks:
            outs = [ctx.ask(t["prompt"], temperature=self.p["temperature"], seed=ctx.derive(t["id"], j)).text
                    for j in range(self.p["repeats"])]
            rows.append(mean([1.0 if is_correct(o, t["expected"]) else 0.0 for o in outs]))
            keys = [answer_key(o) for o in outs]
            pairs = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:]]
            cons.append(mean([1.0 if a == b else 0.0 for a, b in pairs]) if pairs else 1.0)
        return self.result(mean(rows), bootstrap_ci(rows, n_boot=ctx.config.n_bootstrap, seed=ctx.seed), len(rows),
                           consistency=mean(cons), error_rate=ctx.errors / max(1, ctx.calls))


@register_metric
class CalibrationECE(Metric):
    spec = MetricSpec(
        id="calibration_ece_v1", domain=Domain.RELIABILITY, title="Verbalised-confidence calibration (ECE)",
        description="Model states confidence; expected calibration error over 10 bins.",
        formula="value = 1 - ECE", status="experimental",
        limitations=("Needs models that verbalise confidence; otherwise reported as untested.",))
    DEFAULTS = {"n_prompts": 30}

    def compute(self, ctx):
        confs, ok = [], []
        tasks = ctx.dataset("tasks")[: ctx.n(self.p["n_prompts"])]
        for t in tasks:
            out = ctx.ask(f"{t['prompt']} {INSTR_CONF}").text
            m = re.search(r"CONFIDENCE:\s*([01](?:\.\d+)?)", out)
            if m:
                confs.append(float(m.group(1)))
                ok.append(is_correct(out, t["expected"]))
        if len(confs) < 0.5 * len(tasks):
            return self.untested("model did not report confidence for >=50% of prompts")
        e = ece(confs, ok)
        stat = lambda idx: 1 - ece([confs[i] for i in idx], [ok[i] for i in idx])  # noqa: E731
        return self.result(1 - e, bootstrap_ci(list(range(len(confs))), stat, ctx.config.n_bootstrap, seed=ctx.seed),
                           len(confs), ece=e, reported=len(confs) / len(tasks))
