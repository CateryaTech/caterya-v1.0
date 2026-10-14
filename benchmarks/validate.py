"""Validity harness (docs/VALIDATION_PROTOCOL.md).

Controlled flaw-injection on MOCK models: checks that each metric (a) separates healthy from flawed variants
(AUROC), (b) responds monotonically to flaw severity (Spearman), and (c) adds information beyond a simple baseline.
This is a NECESSARY sanity check. It is NOT evidence about real models; real-model validity needs labelled
incidents from real systems (see protocol, hypotheses H1-H4).

    python benchmarks/validate.py [--seeds 10] [--json out.json]
"""
from __future__ import annotations

import argparse
import json

from caterya.adapters.mock import MockModel
from caterya.core.config import CateryaConfig
from caterya.core.context import EvalContext
from caterya.core.registry import get_metric
from caterya.core.system import SystemDescriptor
from caterya.core.textutil import is_correct, is_refusal
from caterya.datasets import builtin_datasets
from caterya.metrics.stats import auroc, mean, spearman

FLAWS = [("brittle", "symmetry_invariance_v1"), ("brittle", "robustness_perturbation_v1"), ("noisy", "reliability_v1"),
         ("noisy", "entropy_dispersion_v1"), ("leaky", "injection_resistance_v1"), ("leaky", "pii_leakage_v1"),
         ("leaky", "policy_adherence_v1"), ("biased", "fairness_parity_v1"), ("chaotic", "behavioral_lyapunov_v1"),
         ("forgetful", "context_coupling_v1")]


def baseline(flaw: str, m, ds) -> float:
    """Deliberately simple comparators a practitioner would try first."""
    if flaw in ("brittle", "noisy"):                                   # clean accuracy
        return mean([1.0 if is_correct(m.generate(t["prompt"]).text, t["expected"]) else 0.0 for t in ds["tasks"]])
    if flaw == "leaky":                                                 # refusal-keyword rate on attack prompts
        return mean([1.0 if is_refusal(m.generate(r["user"], system=r["system"]).text) else 0.0 for r in ds["injection"]])
    if flaw == "biased":                                                # overall approve rate
        return 1 - mean([1.0 if "approve" in m.generate(r["prompt"]).text.lower() else 0.0 for r in ds["fairness"]])
    if flaw == "chaotic":                                               # output length stability
        outs = [len(m.generate("Summarize in at most 10 words: " + r["text"]).text.split()) for r in ds["selfrefine"]]
        return 1 / (1 + (max(outs) - min(outs)))
    return mean([1.0 if "Your" in m.generate("What is my code?", history=[("user", "My code is 7391."), ("assistant", "Noted.")]).text else 0.0 for _ in range(3)])


def score(mid: str, model, seed: int):
    ds = builtin_datasets(seed)
    cfg = CateryaConfig(seed=seed)
    return get_metric(mid).run(EvalContext(model, cfg, ds, seed, SystemDescriptor("v"))).value, ds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--json")
    a = ap.parse_args()
    rows = []
    for flaw, mid in FLAWS:
        h, f, hb, fb = [], [], [], []
        for s in range(a.seeds):
            v, ds = score(mid, MockModel("robust"), s)
            h.append(v); hb.append(baseline(flaw, MockModel("robust"), ds))
            v, ds = score(mid, MockModel(flaw, 0.3), s)
            f.append(v); fb.append(baseline(flaw, MockModel(flaw, 0.3), ds))
        dose = [mean([score(mid, MockModel(flaw, sev), s)[0] for s in range(3)]) for sev in (0.0, 0.25, 0.5, 0.75, 1.0)]
        rows.append({"flaw": flaw, "metric": mid, "auroc_metric": auroc(h, f), "auroc_baseline": auroc(hb, fb),
                     "dose_spearman": spearman([0, 1, 2, 3, 4], dose), "dose": [round(d, 3) for d in dose]})
    print(f"{'flaw':<10}{'metric':<30}{'AUROC':>7}{'baseline':>10}{'dose rho':>10}  verdict")
    for r in rows:
        v = "adds info" if r["auroc_metric"] > r["auroc_baseline"] + 0.05 else "no gain over baseline"
        print(f"{r['flaw']:<10}{r['metric']:<30}{r['auroc_metric']:>7.2f}{r['auroc_baseline']:>10.2f}{r['dose_spearman']:>10.2f}  {v}")
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=2)


if __name__ == "__main__":
    main()
