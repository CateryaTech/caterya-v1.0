"""Evidence record (spec: caterya.evidence/v1). A result is never a bare number."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Optional

from ..core.canonical import digest, short
from ..provenance.signing import Signer, Verifier

SPEC = "caterya.evidence/v1"
_UNSIGNED = ("id", "content_hash", "signature")


@dataclass(frozen=True)
class Evidence:
    spec_version: str = SPEC
    id: str = ""
    claim: str = ""
    system_under_test: str = ""            # hash of system fingerprint (model+tools+config)
    metric: str = ""
    metric_spec_hash: str = ""
    dataset_hash: str = ""
    seed: int = 0
    result: Optional[float] = None         # None = NOT TESTED (reason in `untested`)
    unit: str = "score[0,1]"
    ci_95: Optional[tuple] = None
    n: int = 0
    limitations: list = field(default_factory=list)
    untested: list = field(default_factory=list)
    raw_outputs_hash: str = ""
    timestamp: str = ""
    domain: str = ""
    profile: str = ""
    mode: str = ""
    evaluator: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)   # params, dataset names->hashes, thresholds, details
    visibility: str = "public"
    prev_hash: str = ""
    content_hash: str = ""
    signature: str = ""

    def payload(self) -> dict:
        d = asdict(self)
        for k in _UNSIGNED:
            d.pop(k)
        if d["ci_95"] is not None:
            d["ci_95"] = list(d["ci_95"])
        return d

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["ci_95"] is not None:
            d["ci_95"] = list(d["ci_95"])
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Evidence":
        d = dict(d)
        if d.get("ci_95") is not None:
            d["ci_95"] = tuple(d["ci_95"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def seal_evidence(ev: Evidence, prev_hash: str, signer: Signer, algo: str = "sha256") -> Evidence:
    ev = replace(ev, prev_hash=prev_hash)
    ch = digest(ev.payload(), algo)
    return replace(ev, content_hash=ch, id="EV-" + short(ch, 16), signature=signer.sign(ch.encode()))


def verify_evidence(ev: Evidence, verifier: Verifier | None = None, expected_prev: str | None = None) -> list[str]:
    """Returns a list of problems (empty = valid)."""
    problems = []
    algo = ev.content_hash.split(":", 1)[0] if ":" in ev.content_hash else "sha256"
    if digest(ev.payload(), algo) != ev.content_hash:
        problems.append("content_hash mismatch (record altered)")
    if ev.id != "EV-" + short(ev.content_hash, 16):
        problems.append("id does not match content_hash")
    if verifier is not None and not verifier.verify(ev.content_hash.encode(), ev.signature):
        problems.append("signature invalid")
    if expected_prev is not None and ev.prev_hash != expected_prev:
        problems.append("prev_hash does not link to preceding record")
    return problems


def verify_chain(evs: list[Evidence], verifier: Verifier | None = None) -> list[str]:
    problems, prev = [], evs[0].prev_hash if evs else ""
    for i, e in enumerate(evs):
        problems += [f"[{i}:{e.id}] {p}" for p in verify_evidence(e, verifier, prev if i else None)]
        prev = e.content_hash
    return problems


def unsealed_from_result(res, spec, *, claim: str, system_hash: str, profile: str, mode: str, ts: str,
                         evaluator: dict, visibility: str, extra_context: dict) -> Evidence:
    ctx = {"params": res.params, "datasets": res.dataset_hashes, "details": res.details,
           "calls": res.calls, "tokens_in": res.tokens_in, "tokens_out": res.tokens_out, **extra_context}
    return Evidence(
        claim=claim, system_under_test=system_hash, metric=res.metric_id, metric_spec_hash=spec.spec_hash(),
        dataset_hash=res.dataset_hash, seed=res.seed, result=res.value, unit=res.unit,
        ci_95=tuple(res.ci95) if res.ci95 else None, n=res.n, limitations=list(res.limitations),
        untested=[res.untested_reason] if res.untested_reason else [], raw_outputs_hash=res.raw_outputs_hash,
        timestamp=ts, domain=spec.domain.value, profile=profile, mode=mode, evaluator=evaluator,
        context=ctx, visibility=visibility)
