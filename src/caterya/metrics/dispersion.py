"""Golden-Triangle terms: Entropy, Symmetry, Information (+ context coupling)."""
from __future__ import annotations

import math
import re
from collections import Counter

from ..core.registry import register_metric
from ..core.textutil import answer_key, jaccard, typo_noise
from ..core.types import Domain
from ..datasets import INSTR_FAITH
from .base import Metric, MetricSpec
from .stats import bootstrap_ci, mean, shannon_entropy


@register_metric
class EntropyDispersion(Metric):
    spec = MetricSpec(
        id="entropy_dispersion_v1", domain=Domain.RELIABILITY, title="Output dispersion (Shannon entropy)",
        description="Sample k outputs per prompt; measure entropy of the answer distribution.",
        formula="value = 1 - mean_i[ H(answers_i) / log2(k) ],  H = -sum p log2 p", pillar="", golden="entropy",
        assumptions=("Answer clustering (default: last number / yes-no / first 12 tokens) is a faithful equivalence.",),
        limitations=("Dispersion is not hallucination: correct creative tasks are high-entropy.",
                     "Exact-match clustering under-merges paraphrases; pass a semantic cluster function for open text."))
    DEFAULTS = {"n_prompts": 20, "k": 5, "temperature": 0.8}

    def compute(self, ctx):
        k, tasks = int(self.p["k"]), ctx.dataset("tasks")[: ctx.n(self.p["n_prompts"])]
        vals = []
        for t in tasks:
            keys = [answer_key(ctx.ask(t["prompt"], temperature=self.p["temperature"],
                                       seed=ctx.derive(t["id"], j)).text) for j in range(k)]
            vals.append(1 - shannon_entropy(list(Counter(keys).values())) / math.log2(k))
        return self.result(mean(vals), bootstrap_ci(vals, n_boot=ctx.config.n_bootstrap, seed=ctx.seed), len(vals),
                           k=k, temperature=self.p["temperature"])


def _t_ws(s, r): return "  " + s.replace(" ", "  ", 1) + "  "
TRANSFORMS = {"whitespace": _t_ws, "prefix": lambda s, r: "Please answer: " + s, "upper": lambda s, r: s.upper(),
              "typo": lambda s, r: typo_noise(s, 0.15, r)}


@register_metric
class SymmetryInvariance(Metric):
    spec = MetricSpec(
        id="symmetry_invariance_v1", domain=Domain.ROBUSTNESS, title="Invariance under meaning-preserving transforms",
        description="T_sym = P[ F(g.x) ~ F(x) ] for transformations g that should not change the answer.",
        formula="value = mean_{x,g}[ 1{ answer(F(g.x)) == answer(F(x)) } ]  (or jaccard >= tau in 'similarity' mode)",
        golden="symmetry", status="experimental",
        assumptions=("Chosen transformations are truly meaning-preserving for the task.",),
        limitations=("Covers invariances only, not equivariances (e.g. option permutation maps).",
                     "Group-swap invariance for protected attributes is measured by fairness_parity_v1."))
    DEFAULTS = {"n_prompts": 20, "transforms": list(TRANSFORMS), "mode": "answer"}

    def compute(self, ctx):
        tasks = ctx.dataset("tasks")[: ctx.n(self.p["n_prompts"])]
        rows, per = [], {}
        for t in tasks:
            base = ctx.ask(t["prompt"]).text
            row = []
            for name in self.p["transforms"]:
                out = ctx.ask(TRANSFORMS[name](t["prompt"], ctx.rng(t["id"], name))).text
                ok = (answer_key(out) == answer_key(base)) if self.p["mode"] == "answer" else \
                     jaccard(out, base) >= ctx.config.symmetry_tau
                row.append(1.0 if ok else 0.0)
                per.setdefault(name, []).append(row[-1])
            rows.append(mean(row))
        return self.result(mean(rows), bootstrap_ci(rows, n_boot=ctx.config.n_bootstrap, seed=ctx.seed), len(rows),
                           per_transform={k: mean(v) for k, v in per.items()}, mode=self.p["mode"])


_FAITH = re.compile(r"ANSWER:\s*(.*?)\s*\|\s*EVIDENCE:\s*(.*)", re.S)


@register_metric
class InformationFaithfulness(Metric):
    spec = MetricSpec(
        id="information_faithfulness_v1", domain=Domain.INTERPRETABILITY, title="Explanation faithfulness (deletion test)",
        description="Model cites the evidence for its answer; deleting the cited span from the input should change the answer.",
        formula="value = P[ well_formed AND evidence_in_input AND answer_changes_after_deletion ]",
        pillar="information", golden="information",
        assumptions=("The model follows the ANSWER/EVIDENCE format.",),
        limitations=("Necessity test only (not sufficiency).", "Built-in tasks are arithmetic toys; use domain tasks for claims."))
    DEFAULTS = {"n_prompts": 20}

    def compute(self, ctx):
        tasks = ctx.dataset("tasks")[: ctx.n(self.p["n_prompts"])]
        flags, fmt = [], 0
        for t in tasks:
            q = t["prompt"]
            m = _FAITH.search(ctx.ask(f"{q} {INSTR_FAITH}").text)
            if not m:
                flags.append(0.0)
                continue
            fmt += 1
            ev = m.group(2).strip()
            if not ev or ev not in q:
                flags.append(0.0)
                continue
            m2 = _FAITH.search(ctx.ask(f"{q.replace(ev, '', 1)} {INSTR_FAITH}").text)
            flags.append(1.0 if (not m2 or answer_key(m2.group(1)) != answer_key(m.group(1))) else 0.0)
        return self.result(mean(flags), bootstrap_ci(flags, n_boot=ctx.config.n_bootstrap, seed=ctx.seed), len(flags),
                           format_rate=fmt / max(1, len(tasks)))


@register_metric
class ContextCoupling(Metric):
    spec = MetricSpec(
        id="context_coupling_v1", domain=Domain.RELIABILITY, title="Context retention across turns (classical proxy)",
        description="Plant a fact, add d distractor turns, ask for it back. Retention vs distance.",
        formula="value = mean_{fact,d}[ 1{recall correct} ]; half_life = smallest d with retention < 0.5",
        pillar="transparency",
        assumptions=("Entanglement-style language is metaphorical here: this is a classical memory-fidelity probe.",),
        limitations=("Quantum entanglement entropy lives in caterya.quantum and needs a density matrix.",))
    DEFAULTS = {"distances": [0, 2, 4, 8, 12]}

    def compute(self, ctx):
        facts, rows, curve = ctx.dataset("context"), [], {}
        for d in self.p["distances"]:
            for f in facts:
                h = [("user", f"My {f['key']} is {f['value']}."), ("assistant", "Noted.")]
                for i in range(d):
                    a, b = 11 + i, 7 + 2 * i
                    h += [("user", f"What is {a} + {b}?"), ("assistant", str(a + b))]
                ok = f["value"] in ctx.ask(f"What is my {f['key']}?", history=h).text
                rows.append(1.0 if ok else 0.0)
                curve.setdefault(d, []).append(rows[-1])
        ret = {d: mean(v) for d, v in curve.items()}
        half = next((d for d in sorted(ret) if ret[d] < 0.5), None)
        return self.result(mean(rows), bootstrap_ci(rows, n_boot=ctx.config.n_bootstrap, seed=ctx.seed), len(rows),
                           retention_by_distance=ret, half_life=half)
