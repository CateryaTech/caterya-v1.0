"""Risk = Probability x Impact x Exposure x Context. Conceptual: calibrate with domain experts."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..core.config import CateryaConfig
from ..core.types import RiskLevel

CRIT = {"low": 0.25, "moderate": 0.5, "high": 0.75, "critical": 1.0}
DOMAIN_W = {"safety": 1.0, "security": 1.0, "privacy": 0.9, "fairness": 0.8, "reliability": 0.7, "robustness": 0.7,
            "stability": 0.7, "agentic": 0.9, "provenance": 0.6, "interpretability": 0.5, "sustainability": 0.3}
SECTOR_CTX = {"health": 1.25, "finance": 1.2, "energy": 1.2, "public": 1.2, "critical_infrastructure": 1.3, "general": 1.0}
_ORDER = [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL]


@dataclass
class Mitigation:
    id: str
    description: str
    effectiveness: float                         # 0..1
    evidence_ids: list = field(default_factory=list)   # unverified mitigations count as 0


@dataclass
class RiskItem:
    metric_id: str
    domain: str
    probability: float
    impact: float
    exposure: float
    context: float
    risk: float


def level_of(score: float, thresholds) -> RiskLevel:
    for lvl, t in zip(_ORDER, thresholds):
        if score < t:
            return lvl
    return RiskLevel.CRITICAL


def max_level(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    return a if _ORDER.index(a) >= _ORDER.index(b) else b


def assess_risk(scored: dict[str, tuple[str, float]], deployment: dict, cfg: CateryaConfig,
                finding_levels: list[RiskLevel] | None = None, mitigations: list[Mitigation] | None = None,
                known_evidence: set[str] | None = None) -> dict:
    """scored: metric_id -> (domain, value in [0,1])."""
    crit = CRIT.get(deployment.get("criticality", cfg.default_criticality), 0.5)
    expo = float(deployment.get("exposure", cfg.default_exposure))
    ctx = SECTOR_CTX.get(deployment.get("sector", "general"), 1.0)
    items = []
    for mid, (dom, v) in scored.items():
        imp = crit * DOMAIN_W.get(dom, 0.5)
        items.append(RiskItem(mid, dom, 1 - v, imp, expo, ctx, min(1.0, (1 - v) * imp * expo * ctx)))
    top = max((i.risk for i in items), default=0.0)
    agg = 1 - _prod(1 - i.risk for i in items)
    lvl = level_of(top, cfg.risk_thresholds)
    for fl in finding_levels or []:
        lvl = max_level(lvl, fl)
    verified = [m for m in (mitigations or []) if m.evidence_ids and (known_evidence is None or all(e in known_evidence for e in m.evidence_ids))]
    residual = top * _prod(1 - m.effectiveness for m in verified)
    return {"score": top, "aggregate": agg, "level": lvl.value, "residual": residual,
            "residual_level": max_level(level_of(residual, cfg.risk_thresholds), RiskLevel.LOW).value,
            "formula": "risk_i = (1-value_i) x (criticality x domain_weight) x exposure x context",
            "items": [i.__dict__ for i in sorted(items, key=lambda i: -i.risk)[:12]],
            "mitigations": [{"id": m.id, "effectiveness": m.effectiveness, "verified": m in verified} for m in (mitigations or [])]}


def _prod(xs) -> float:
    r = 1.0
    for x in xs:
        r *= x
    return r
