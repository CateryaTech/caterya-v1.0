"""Policy gate: AI Trustworthiness Gate for CI/CD (GIT PUSH -> BUILD -> EVALUATE -> REGRESSION -> EVIDENCE -> POLICY GATE -> DEPLOY/BLOCK)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..core.clock import parse_iso
from .record import effective_status

_RISK = ["low", "moderate", "high", "critical"]


@dataclass
class Policy:
    min_level: int = 2
    require_domains: list = field(default_factory=list)
    min_metric: dict = field(default_factory=dict)
    max_risk: str = "high"
    block_dispositions: list = field(default_factory=lambda: ["REJECTED", "EXPIRED"])
    max_regression_drop: float = 0.05
    max_age_days: int | None = None
    fail_on_untested_required: bool = False

    @classmethod
    def load(cls, path: str | Path) -> "Policy":
        text = Path(path).read_text()
        if str(path).endswith((".yaml", ".yml")):
            import yaml
            d = yaml.safe_load(text)
        else:
            d = json.loads(text)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def gate(car: dict, policy: Policy, regression: dict | None = None, now=None) -> dict:
    reasons, warns = [], []
    if car["level"] < policy.min_level:
        reasons.append(f"assurance level {car['level']} < required {policy.min_level}")
    if now is not None:
        st = effective_status(car, now)
        if st in policy.block_dispositions:
            reasons.append(f"disposition {st} is blocked by policy")
        if policy.max_age_days is not None and (now - parse_iso(car["evaluation"]["timestamp"])).days > policy.max_age_days:
            reasons.append("evaluation older than max_age_days")
    elif car["disposition"]["status"] in policy.block_dispositions:
        reasons.append(f"disposition {car['disposition']['status']} is blocked by policy")
    if _RISK.index(car["risk"]["level"]) > _RISK.index(policy.max_risk):
        reasons.append(f"risk level {car['risk']['level']} above allowed {policy.max_risk}")
    for d in policy.require_domains:
        if d not in car["domains"]:
            reasons.append(f"required domain '{d}' not evaluated")
    flat = {mid: m for dd in car["domains"].values() for mid, m in dd["metrics"].items()}
    for mid, mn in policy.min_metric.items():
        v = flat.get(mid, {}).get("value")
        if v is None:
            reasons.append(f"metric {mid} untested")
        elif v < mn:
            reasons.append(f"{mid}={v:.3f} < {mn}")
    for f in car["risk"]["findings"]:
        if f["severity"] in ("high", "critical"):
            reasons.append(f"finding: {f['message']}")
    if regression:
        for r in regression["regressions"]:
            if -r["delta"] > policy.max_regression_drop:
                reasons.append(f"regression {r['metric_id']}: {r['old']:.3f} -> {r['new']:.3f}")
    if policy.fail_on_untested_required and car["coverage"]["untested"]:
        reasons.append("required tests untested: " + ", ".join(map(str, car["coverage"]["untested"][:5])))
    elif car["coverage"]["untested"]:
        warns.append(f"{len(car['coverage']['untested'])} untested gap(s)")
    return {"decision": "BLOCK" if reasons else ("WARN" if warns else "PASS"), "reasons": reasons, "warnings": warns,
            "car_id": car["car_id"]}
