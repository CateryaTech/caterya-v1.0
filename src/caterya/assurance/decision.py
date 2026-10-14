"""Assurance decision model: EVALUATION -> FINDINGS -> RISK -> GOVERNANCE DECISION."""
from __future__ import annotations

from ..core.types import HARD_GATE_DOMAINS, RiskLevel

_HARD = {d.value for d in HARD_GATE_DOMAINS}


def classify(row: dict) -> str:
    """Status of one metric against its thresholds, CI-aware."""
    v, mn, warn, ci = row["value"], row["threshold"], row["warn"], row["ci_95"]
    if row.get("info"):
        return "info"
    if v is None:
        return "untested"
    if mn is not None and v < mn:
        return "fail" if (ci is None or ci[1] < mn) else "inconclusive"
    if warn is not None and v < warn:
        return "warn"
    return "pass"


def make_findings(rows: list[dict]) -> tuple[list[dict], list[RiskLevel]]:
    out, levels = [], []
    for r in rows:
        st = r["status"]
        if st not in ("fail", "inconclusive", "warn"):
            continue
        hard = r["domain"] in _HARD
        if st == "fail":
            sev = RiskLevel.CRITICAL if (hard and r["value"] < (r["threshold"] or 0) * 0.5) else RiskLevel.HIGH
        elif st == "inconclusive":
            sev = RiskLevel.MODERATE
        else:
            sev = RiskLevel.LOW
        levels.append(sev)
        out.append({"metric_id": r["metric_id"], "domain": r["domain"], "status": st, "severity": sev.value,
                    "value": r["value"], "threshold": r["threshold"], "ci_95": r["ci_95"], "hard_gate": hard,
                    "unresolved": True,
                    "message": f"{r['metric_id']}={r['value']:.3f} vs threshold {r['threshold']}"
                               + (" (CI straddles threshold: inconclusive)" if st == "inconclusive" else "")})
    return out, levels


def recommend(findings: list[dict], rows: list[dict], coverage: float, min_cov: float) -> tuple[str, list[str]]:
    """Recommendation only. The disposition is set by a recorded governance decision."""
    conds: list[str] = []
    if coverage < min_cov:
        return "EVALUATED", [f"coverage {coverage:.0%} below required {min_cov:.0%}: measure remaining required metrics"]
    if any(f["severity"] == "critical" for f in findings) or any(f["status"] == "fail" and f["hard_gate"] for f in findings):
        return "REJECTED", [f"remediate {f['metric_id']}" for f in findings if f["status"] == "fail"]
    if any(f["status"] == "fail" for f in findings) or any(f["status"] == "inconclusive" for f in findings):
        return "REVIEW_REQUIRED", [f"review {f['metric_id']} ({f['status']})" for f in findings if f["status"] in ("fail", "inconclusive")]
    gaps = [r["metric_id"] for r in rows if r["status"] == "untested"]
    conds += [f"improve {f['metric_id']} (below warn level)" for f in findings if f["status"] == "warn"]
    conds += [f"close test gap: {g}" for g in gaps]
    return ("CONDITIONALLY_ASSURED" if conds else "ASSURED"), conds
