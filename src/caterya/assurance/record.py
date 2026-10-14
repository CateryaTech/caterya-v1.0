"""CATERYA Assurance Record (CAR): structured, versioned, time-bound, signed."""
from __future__ import annotations

from datetime import timedelta

from ..core.canonical import digest
from ..core.clock import iso, parse_iso
from ..core.config import CateryaConfig
from ..core.errors import GovernanceError
from ..core.types import AssuranceLevel, Disposition
from ..provenance.attestation import verify_dsse
from ..provenance.signing import Signer, Verifier

SPEC = "caterya.car/v1"


def seal_car(car: dict, signer: Signer, algo: str = "sha256") -> dict:
    body = {k: v for k, v in car.items() if k not in ("content_hash", "signature")}
    ch = digest(body, algo)
    return {**body, "content_hash": ch, "signature": signer.sign(ch.encode()), "signer": signer.identity()}


def verify_car(car: dict, verifier: Verifier | None = None) -> list[str]:
    body_h = {k: v for k, v in car.items() if k not in ("content_hash", "signature")}
    probs = []
    algo = car["content_hash"].split(":", 1)[0]
    if digest(body_h, algo) != car["content_hash"]:
        probs.append("CAR content_hash mismatch (record altered)")
    if verifier and not verifier.verify(car["content_hash"].encode(), car["signature"]):
        probs.append("CAR signature invalid")
    return probs


def effective_status(car: dict, now) -> str:
    st = car["disposition"]["status"]
    if st in (Disposition.ASSURED.value, Disposition.CONDITIONALLY_ASSURED.value) and now > parse_iso(car["validity"]["valid_until"]):
        return Disposition.EXPIRED.value
    return st


def determine_level(car: dict, evidence_ok: bool, cfg: CateryaConfig) -> AssuranceLevel:
    cov = car["coverage"]["measured_required"] / max(1, car["coverage"]["required"])
    if car["evidence"]["count"] == 0 or cov < 0.5:
        return AssuranceLevel.UNVERIFIED
    lvl = AssuranceLevel.EVALUATED
    sig_ok = car["signer"].get("third_party_verifiable") or not cfg.require_signature  # HMAC dev keys cap at level 1
    if evidence_ok and sig_ok:
        lvl = AssuranceLevel.EVIDENCE_BACKED
    d = car["disposition"]
    if lvl >= AssuranceLevel.EVIDENCE_BACKED and cov >= cfg.min_coverage and d["status"] in ("ASSURED", "CONDITIONALLY_ASSURED") and d.get("decided_by"):
        lvl = AssuranceLevel.ASSURED
        if any(a.get("verified") for a in car.get("attestations", [])):
            lvl = AssuranceLevel.INDEPENDENTLY_ATTESTED
    return lvl


def build_car(*, system, evaluation_id: str, profile, mode: str, evidences: list, rows: list[dict], risk: dict,
              recommended: str, conditions: list, cos: dict, regulatory: dict, untested: list, evaluator: dict,
              sth: dict, seq: int, now, cfg: CateryaConfig, evidence_ok: bool, signer: Signer, findings: list,
              req_total: int, req_measured: int) -> dict:
    doms: dict[str, dict] = {}
    for r in rows:
        d = doms.setdefault(r["domain"], {"score": None, "metrics": {}, "status": "pass"})
        d["metrics"][r["metric_id"]] = {k: r[k] for k in ("value", "ci_95", "n", "status", "threshold", "warn")}
    order = ["pass", "info", "untested", "warn", "inconclusive", "fail"]
    for dn, d in doms.items():
        vals = [m["value"] for m in d["metrics"].values() if m["value"] is not None and m["status"] != "info"]
        d["score"] = sum(vals) / len(vals) if vals else None
        d["status"] = max((m["status"] for m in d["metrics"].values()), key=order.index)
    ttl = profile.ttl_days or cfg.ttl_days
    status = "REVIEW_REQUIRED" if recommended in ("REJECTED", "REVIEW_REQUIRED") else "EVALUATED"
    car = {
        "spec_version": SPEC, "car_id": f"CAR-{now.year}-{seq:06d}", "version": 1, "prev_hash": "",
        "system": {"name": system.name, "type": system.kind, "version": system.version, "id": system.id,
                   "fingerprint": system.fingerprint_hash()},
        "model": {"provider": system.provider, "model_id": system.model_id, "model_version": system.model_version},
        "deployment": system.deployment,
        "evaluation": {"id": evaluation_id, "profile": profile.id, "mode": mode, "evaluator": evaluator,
                       "timestamp": iso(now), "methodology": "caterya.methodology/v1 (see docs/METRICS.md)"},
        "domains": doms, "risk": {**risk, "findings": findings,
                                  "unresolved": [f for f in findings if f.get("unresolved", True)]},
        "evidence": {"count": len(evidences), "artifacts": [e.id for e in evidences],
                     "hashes": [e.content_hash for e in evidences], "merkle_root": sth.get("root", ""), "sth": sth},
        "coverage": {"required": req_total, "measured_required": req_measured, "untested": untested},
        "cos": cos, "regulatory": regulatory,
        "disposition": {"status": status, "recommended": recommended, "conditions": conditions, "decided_by": "",
                        "role": "", "rationale": "", "override_reason": "", "decided_at": ""},
        "validity": {"issued_at": iso(now), "valid_until": iso(now + timedelta(days=ttl)), "ttl_days": ttl},
        "attestations": [], "level": 0, "level_label": "",
        "disclaimer": "CATERYA measures and documents; governance decides. Not a certification or safety guarantee.",
    }
    car = _with_level(car, evidence_ok, cfg, signer)
    return car


def _with_level(car: dict, evidence_ok: bool, cfg: CateryaConfig, signer: Signer) -> dict:
    car = {k: v for k, v in car.items() if k not in ("content_hash", "signature", "signer")}
    car["signer"] = signer.identity()
    lvl = determine_level(car, evidence_ok, cfg)
    car["level"], car["level_label"] = int(lvl), lvl.label
    return seal_car(car, signer, cfg.hash_algo)


def finalize(car: dict, decision: dict, signer: Signer, cfg: CateryaConfig, now, evidence_ok: bool = True) -> dict:
    """Human/governance decision. Guard-rails: no assurance on weak evidence; overriding a REJECTED recommendation needs a reason."""
    dec = decision.get("decision")
    valid = {d.value for d in Disposition} - {"EXPIRED", "EVALUATED"}
    if dec not in valid:
        raise GovernanceError(f"decision must be one of {sorted(valid)}")
    if not decision.get("decided_by") or not decision.get("role"):
        raise GovernanceError("decided_by and role are required: governance decides, CATERYA measures")
    if dec in ("ASSURED", "CONDITIONALLY_ASSURED"):
        if not evidence_ok:
            raise GovernanceError("evidence chain/signatures not verified: cannot assure")
        if car["coverage"]["measured_required"] / max(1, car["coverage"]["required"]) < cfg.min_coverage:
            raise GovernanceError("coverage below minimum: cannot assure")
        if car["disposition"]["recommended"] == "REJECTED" and not decision.get("override_reason"):
            raise GovernanceError("recommendation is REJECTED: override_reason required to assure")
        if dec == "CONDITIONALLY_ASSURED" and not (decision.get("conditions") or car["disposition"]["conditions"]):
            raise GovernanceError("CONDITIONALLY_ASSURED needs stated conditions")
    new = {**car, "version": car["version"] + 1, "prev_hash": car["content_hash"]}
    new["disposition"] = {**car["disposition"], "status": dec, "decided_by": decision["decided_by"], "role": decision["role"],
                          "rationale": decision.get("rationale", ""), "override_reason": decision.get("override_reason", ""),
                          "conditions": decision.get("conditions") or car["disposition"]["conditions"], "decided_at": iso(now)}
    return _with_level(new, evidence_ok, cfg, signer)


def attach_attestation(car: dict, envelope: dict, verifier: Verifier, signer: Signer, cfg: CateryaConfig,
                       now, evidence_ok: bool = True) -> dict:
    """Level 4: third-party DSSE attestation by a trusted key different from the evaluator's."""
    ok, stmt = verify_dsse(envelope, verifier)
    trusted = verifier.key_id in cfg.trusted_attesters and verifier.key_id != car["evaluation"]["evaluator"].get("key_id")
    rec = {"key_id": verifier.key_id, "verified": bool(ok and trusted and stmt and stmt["subject"][0]["name"] == car["car_id"]),
           "signature_valid": ok, "trusted": trusted, "attested_at": iso(now)}
    new = {**car, "version": car["version"] + 1, "prev_hash": car["content_hash"],
           "attestations": car.get("attestations", []) + [rec]}
    return _with_level(new, evidence_ok, cfg, signer)
