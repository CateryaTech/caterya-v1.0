"""Evidence bundles: portable, third-party verifiable and reproducible."""
from __future__ import annotations

from typing import Optional

from ..assurance.record import verify_car
from ..core.canonical import digest
from ..core.config import CateryaConfig
from ..core.context import EvalContext
from ..core.registry import get_metric
from ..core.system import SystemDescriptor
from ..provenance.log import verify_inclusion_proof, verify_sth
from ..provenance.signing import verifier_from_info
from .model import Evidence, verify_chain
from .store import EvidenceStore

BUNDLE_SPEC = "caterya.bundle/v1"


def export_bundle(store: EvidenceStore, runner, evaluation_id: str, include_data: bool = True, include_raw: bool = False) -> dict:
    ev_doc = store.get_doc("evaluation", evaluation_id)
    evs = store.list_evidence(evaluation_id=evaluation_id)
    car = store.get_doc("car", ev_doc["car_id"])
    datasets = {}
    if include_data:
        for name, h in ev_doc["datasets"].items():
            d = store.get_doc("dataset", h)
            if d:
                datasets[name] = {"hash": h, "data": d["data"]}
    leaves = store.leaves()
    idx = {h: i for i, h in enumerate(leaves)}
    proofs = {e.id: runner.log.inclusion_proof(idx[e.content_hash]) for e in evs if e.content_hash in idx}
    return {"spec": BUNDLE_SPEC, "evaluation": ev_doc, "system": store.get_doc("system", ev_doc["system"]["id"]) if "id" in ev_doc["system"] else ev_doc["system"],
            "evidence": [e.to_dict() for e in evs], "car": car, "datasets": datasets, "inclusion_proofs": proofs,
            "sth": runner.log.signed_tree_head(), "verifier": runner.signer.verifier().public_info(),
            "third_party_verifiable": runner.signer.third_party_verifiable}


def verify_bundle(b: dict, hmac_secret: Optional[bytes] = None) -> dict:
    v = verifier_from_info(b["verifier"], hmac_secret)
    evs = [Evidence.from_dict(e) for e in b["evidence"]]
    problems = verify_chain(evs, v)
    problems += [f"CAR: {p}" for p in verify_car(b["car"], v)] if b.get("car") else []
    for eid, p in b.get("inclusion_proofs", {}).items():
        if not verify_inclusion_proof(p):
            problems.append(f"inclusion proof invalid for {eid}")
    if b.get("sth") and not verify_sth(b["sth"], v):
        problems.append("signed tree head invalid")
    for name, d in b.get("datasets", {}).items():
        if digest(d["data"]) != d["hash"]:
            problems.append(f"dataset '{name}' hash mismatch")
    return {"ok": not problems, "problems": problems, "records": len(evs), "signer": b["verifier"],
            "third_party_verifiable": b.get("third_party_verifiable", False)}


def reproduce_bundle(b: dict, adapter=None, cfg: Optional[CateryaConfig] = None, tol: float = 1e-9) -> dict:
    """Re-run each metric with the recorded seed, params and datasets; compare with the recorded result.
    Deterministic adapters should match exactly (tol); stochastic APIs should be judged by CI overlap."""
    cfg = cfg or CateryaConfig()
    data = {n: d["data"] for n, d in b["datasets"].items()}
    sysd = SystemDescriptor.from_dict(b["system"]) if b.get("system") else None
    rows = []
    for e in b["evidence"]:
        ev = Evidence.from_dict(e)
        if ev.result is None:
            rows.append({"metric": ev.metric, "status": "not_tested_originally"})
            continue
        m = get_metric(ev.metric, **ev.context.get("params", {}))
        if m.spec.spec_hash() != ev.metric_spec_hash:
            rows.append({"metric": ev.metric, "status": "spec_changed", "detail": "metric definition differs from the recorded hash"})
            continue
        need = {k: data[k] for k in ev.context.get("datasets", {}) if k in data}
        if len(need) != len(ev.context.get("datasets", {})):
            rows.append({"metric": ev.metric, "status": "data_unavailable"})
            continue
        ctx = EvalContext(adapter, cfg, need, seed=ev.seed, system=sysd)
        try:
            new = m.run(ctx)
        except Exception as ex:
            rows.append({"metric": ev.metric, "status": "error", "detail": str(ex)})
            continue
        ok = new.value is not None and abs(new.value - ev.result) <= tol
        overlap = bool(new.ci95 and ev.ci_95 and new.ci95[0] <= ev.ci_95[1] and ev.ci_95[0] <= new.ci95[1])
        rows.append({"metric": ev.metric, "status": "match" if ok else ("ci_overlap" if overlap else "mismatch"),
                     "recorded": ev.result, "reproduced": new.value,
                     "raw_outputs_match": new.raw_outputs_hash == ev.raw_outputs_hash})
    return {"rows": rows, "all_match": all(r["status"] in ("match", "not_tested_originally") for r in rows)}
