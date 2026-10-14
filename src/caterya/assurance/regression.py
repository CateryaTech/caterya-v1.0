"""Trustworthiness regression: detect changes in behavioural profile and trade-offs (not 'which model is better')."""
from __future__ import annotations

from ..core.config import CateryaConfig


def _flat(car: dict) -> dict:
    return {mid: m for d in car["domains"].values() for mid, m in d["metrics"].items() if m["status"] != "info"} | {}


def _dom(car: dict, mid: str) -> str:
    return next(dn for dn, d in car["domains"].items() if mid in d["metrics"])


def compare(old: dict, new: dict, cfg: CateryaConfig | None = None) -> dict:
    cfg = cfg or CateryaConfig()
    a, b, rows = _flat(old), _flat(new), []
    for mid in sorted(set(a) | set(b)):
        x, y = a.get(mid), b.get(mid)
        if not x or not y or x["value"] is None or y["value"] is None:
            rows.append({"metric_id": mid, "domain": _dom(new if y else old, mid), "old": x and x["value"], "new": y and y["value"],
                         "delta": None, "change": "n/a"})
            continue
        d = y["value"] - x["value"]
        sep = x["ci_95"] and y["ci_95"] and (y["ci_95"][1] < x["ci_95"][0] or y["ci_95"][0] > x["ci_95"][1])
        arrow = "↑" if d > 0 else "↓"
        change = "=" if abs(d) < cfg.regression_min_effect else (arrow if (sep or not (x["ci_95"] and y["ci_95"])) else "~" + arrow)
        rows.append({"metric_id": mid, "domain": _dom(new, mid), "old": x["value"], "new": y["value"], "delta": d,
                     "change": change, "significant": bool(sep)})
    drops = [r for r in rows if r["change"] in ("↓", "~↓") and -r["delta"] > cfg.regression_max_drop]
    ups = [r for r in rows if r["change"] in ("↑", "~↑")]
    return {"old_car": old["car_id"], "new_car": new["car_id"], "rows": rows, "regressions": drops,
            "tradeoff": bool(drops and ups), "passed": not drops,
            "note": "~ marks a change whose 95% CIs overlap (unconfirmed); it still counts as a regression when larger than the allowed drop. Detects behavioural change and trade-offs; does not rank models."}


def history(cars: list[dict]) -> list[dict]:
    return [{"car_id": c["car_id"], "version": c["version"], "timestamp": c["evaluation"]["timestamp"], "system_version": c["system"]["version"],
             "status": c["disposition"]["status"], "level": c["level"], "risk": c["risk"]["level"],
             "domains": {d: v["score"] for d, v in c["domains"].items()}} for c in cars]
