"""CATERYA Open Score (COS): a DERIVED index. The product is the evidence bundle, not this number.

COS = coverage * (sum_p w_p * P_p / sum_p w_p) * G^gamma, with Golden Triangle G = (E * S * I)^(1/3).
Missing pillars reduce `coverage` (opacity penalty) instead of being silently ignored.
"""
from __future__ import annotations

from ..core.config import CateryaConfig
from .base import MetricResult, MetricSpec
from .stats import mean

PILLARS = ("fairness", "information", "stability", "transparency")


def compute_cos(results: dict[str, MetricResult], specs: dict[str, MetricSpec], cfg: CateryaConfig | None = None) -> dict:
    cfg = cfg or CateryaConfig()
    pil: dict[str, list[float]] = {p: [] for p in PILLARS}
    gold: dict[str, list[float]] = {"entropy": [], "symmetry": [], "information": []}
    for mid, r in results.items():
        s = specs.get(mid)
        if not s or r.value is None or s.kind != "score":
            continue
        if s.pillar in pil:
            pil[s.pillar].append(r.value)
        if s.golden in gold:
            gold[s.golden].append(r.value)
    pv = {p: mean(v) for p, v in pil.items() if v}
    w = cfg.cos_weights
    wsum = sum(w.get(p, 0) for p in pv)
    base = sum(w.get(p, 0) * v for p, v in pv.items()) / wsum if wsum else None
    coverage = sum(w.get(p, 0) for p in pv) / (sum(w.get(p, 0) for p in PILLARS) or 1)
    gv = {k: mean(v) for k, v in gold.items() if v}
    G = (gv["entropy"] * gv["symmetry"] * gv["information"]) ** (1 / 3) if len(gv) == 3 else None
    cos = None if base is None else coverage * base * ((G if G is not None else 1.0) ** cfg.cos_gamma)
    view = {
        "optional": True,
        "status": "research",
        "formula": "G = (entropy * symmetry * information) ** (1/3)",
        "weights": {
            "entropy": 1.0,
            "symmetry": 1.0,
            "information": 1.0,
            "aggregation": "unweighted geometric mean; exponents are equal and are not a second linear weighting",
        },
        "axes": gv,
        "G": G,
        "cos_modulation": {
            "formula": "coverage * pillar_mean * (G ** cos_gamma) when all three axes exist, else G is treated as 1",
            "cos_gamma": cfg.cos_gamma,
            "cos_weights": {p: w.get(p, 0) for p in PILLARS},
        },
        "limitations": [
            "Optional composite view. It does not replace the metric evidence it summarises.",
            "A missing axis leaves G null. The missing axis is not imputed inside G.",
            "When G is null, COS modulation uses 1 for that factor so the pillar mean still appears. That choice is visible here.",
            "Safety, security and privacy are not in this triangle.",
            "Research-grade. Not a certificate and not a claim that the system is safe.",
        ],
    }
    return {"cos": cos, "pillars": pv, "golden_triangle": gv, "golden_triangle_view": view, "G": G, "coverage": coverage,
            "missing_pillars": [p for p in PILLARS if p not in pv],
            "note": "Derived index for comparison only; not a certificate. Inspect the evidence bundle."}
