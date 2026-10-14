"""EvaluationRunner: REGISTER -> CONTEXT -> PROFILE -> PREPARE -> EXECUTE -> ANALYZE -> EVIDENCE -> PROVENANCE -> RISK/ASSURANCE -> REPORT."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field, replace
from typing import Optional

from ..assurance import decision as dec
from ..assurance.record import build_car
from ..assurance.report import render_markdown
from ..assurance.risk import Mitigation, assess_risk
from ..core.canonical import digest, short
from ..core.clock import Clock, iso, utcnow
from ..core.config import CateryaConfig
from ..core.context import EvalContext
from ..core.registry import get_metric
from ..core.system import SystemDescriptor, capture_environment
from ..core.types import Mode
from ..datasets import builtin_datasets
from ..evidence.model import Evidence, seal_evidence, unsealed_from_result, verify_chain
from ..evidence.store import EvidenceStore
from ..metrics.cos import compute_cos
from ..profiles.registry import Profile, get_profile
from ..provenance.anchor import Anchor, NullAnchor
from ..provenance.log import TransparencyLog
from ..provenance.signing import HAVE_ED25519, Ed25519Signer, HmacSigner, Signer, load_or_create_signer
from ..regulatory.mapping import summary as reg_summary
from .agent import AgentAdapter, collect_traces

_INFO_LAST = lambda p: (p.info, p.metric_id)  # noqa: E731


@dataclass
class EvaluationResult:
    id: str
    system: SystemDescriptor
    profile: str
    mode: str
    evidences: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    risk: dict = field(default_factory=dict)
    car: dict = field(default_factory=dict)
    steps: list = field(default_factory=list)
    sth: dict = field(default_factory=dict)
    evidence_ok: bool = True
    dataset_names: dict = field(default_factory=dict)

    def summary(self) -> dict:
        c = self.car
        return {"evaluation_id": self.id, "car_id": c["car_id"], "profile": self.profile, "level": f"{c['level']} {c['level_label']}",
                "status": c["disposition"]["status"], "recommended": c["disposition"]["recommended"], "risk": c["risk"]["level"],
                "evidence": len(self.evidences), "coverage": c["coverage"], "cos": c["cos"].get("cos")}

    def report(self) -> str:
        return render_markdown(self.car, self.evidences)

    def to_dict(self) -> dict:
        return {"id": self.id, "system": self.system.to_dict(), "profile": self.profile, "mode": self.mode, "rows": self.rows,
                "findings": self.findings, "risk": self.risk, "car_id": self.car["car_id"], "steps": self.steps,
                "evidence_ids": [e.id for e in self.evidences], "sth": self.sth, "evidence_ok": self.evidence_ok,
                "datasets": self.dataset_names}


class EvaluationRunner:
    def __init__(self, store: Optional[EvidenceStore] = None, signer: Optional[Signer] = None,
                 config: Optional[CateryaConfig] = None, clock: Clock = utcnow, anchor: Optional[Anchor] = None,
                 home: Optional[str] = None):
        self.cfg = config or CateryaConfig()
        self.store = store or EvidenceStore(":memory:")
        self.signer = signer or (load_or_create_signer(home) if home else (Ed25519Signer() if HAVE_ED25519 else HmacSigner()))
        self.clock = clock
        self.anchor = anchor or NullAnchor()
        self.log = TransparencyLog(self.signer, self.store.leaves(), clock)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    def run(self, system: SystemDescriptor, adapter=None, profile: str | Profile = "CATERYA-LLM", *,
            mode: str | Mode = Mode.PRE_RELEASE, claim: Optional[str] = None, datasets: Optional[dict] = None,
            agent: Optional[AgentAdapter] = None, depth: Optional[str] = None, visibility: Optional[str] = None,
            mitigations: Optional[list[Mitigation]] = None) -> EvaluationResult:
        with self._lock:
            return self._run(system, adapter, profile, mode, claim, datasets, agent, depth, visibility, mitigations)

    def _run(self, system, adapter, profile, mode, claim, datasets, agent, depth, visibility, mitigations) -> EvaluationResult:
        cfg = replace(self.cfg, depth=depth) if depth else self.cfg
        prof = profile if isinstance(profile, Profile) else get_profile(profile)
        mode = Mode(mode).value
        now = self.clock()
        eid = "EVAL-" + short(digest([system.id, prof.id, iso(now), cfg.seed]), 10)
        steps: list[dict] = []

        def step(name: str, ok: bool = True, note: str = "") -> None:
            steps.append({"step": name, "ts": iso(self.clock()), "ok": ok, "note": note})

        # 1-3 register, context, profile
        sys_hash = system.fingerprint_hash(cfg.hash_algo)
        self.store.put_doc("system", system.id, system.to_dict(), system.name, iso(now))
        step("REGISTER_SYSTEM", note=system.id)
        step("DEFINE_CONTEXT", note=str({k: system.deployment.get(k) for k in ("environment", "sector", "criticality")}))
        step("SELECT_PROFILE", note=prof.id)

        # 4 prepare
        ds = {**builtin_datasets(cfg.seed), **(datasets or {})}
        if prof.needs_traces:
            if agent is not None:
                ds["traces"] = collect_traces(agent, ds["agent_scenarios"], ds["agent_policy"][0])
            elif "traces" not in ds:
                step("PREPARE_EVALUATION", False, "profile needs system traces but no agent supplied: agent metrics will be NOT TESTED")
        ctx = EvalContext(adapter, cfg, ds, seed=cfg.seed, system=system)
        step("PREPARE_EVALUATION", note=f"datasets={sorted(ds)} depth={cfg.depth}")

        # 5 execute (informational metrics last so they can see token usage)
        results, usage = {}, {"tokens_in": 0, "tokens_out": 0, "calls": 0}
        for plan in sorted(prof.plans, key=_INFO_LAST):
            m = get_metric(plan.metric_id, **plan.params)
            ds["__usage__"] = [dict(usage)]
            try:
                res = m.run(ctx)
            except Exception as e:  # never hidden: becomes an explicit test gap
                res = m.untested(f"{type(e).__name__}: {e}")
                res.params, res.seed = dict(m.p), ctx.seed
            usage["tokens_in"] += res.tokens_in
            usage["tokens_out"] += res.tokens_out
            usage["calls"] += res.calls
            results[plan.metric_id] = (plan, m.spec, res)
        step("EXECUTE_TESTS", note=f"{len(results)} metrics, {usage['calls']} model calls")

        # 6 analyze
        rows = []
        for mid, (plan, spec, res) in results.items():
            row = {"metric_id": mid, "domain": spec.domain.value, "value": res.value, "ci_95": list(res.ci95) if res.ci95 else None,
                   "n": res.n, "threshold": plan.min_value, "warn": plan.warn, "info": plan.info or spec.kind != "score",
                   "required": plan.required and not plan.info}
            row["status"] = "untested" if res.value is None else dec.classify(row)
            rows.append(row)
        findings, flevels = dec.make_findings(rows)
        step("ANALYZE_RESULTS", note=f"{len(findings)} finding(s)")

        # 7-8 evidence + provenance
        env = capture_environment()
        evaluator = {**self.signer.identity(), "caterya": env["caterya"], "environment": env, "environment_hash": digest(env)}
        sealed: list[Evidence] = []
        prev = self.store.head_hash()
        vis = visibility or cfg.default_visibility
        for row in rows:
            plan, spec, res = results[row["metric_id"]]
            text = claim or (f"{system.name} {system.version}: {spec.title}" +
                             (f" >= {plan.min_value}" if plan.min_value is not None else ""))
            ev = unsealed_from_result(res, spec, claim=text, system_hash=sys_hash, profile=prof.id, mode=mode, ts=iso(self.clock()),
                                      evaluator=evaluator, visibility=vis,
                                      extra_context={"evaluation_id": eid, "status": row["status"], "threshold": plan.min_value,
                                                     "warn": plan.warn, "required": row["required"], "depth": cfg.depth})
            ev = seal_evidence(ev, prev, self.signer, cfg.hash_algo)
            self.store.put_evidence(ev, system.id, eid)
            self.store.put_leaf(self.log.append(ev.content_hash), ev.content_hash)
            sealed.append(ev)
            prev = ev.content_hash
        step("GENERATE_EVIDENCE", note=f"{len(sealed)} records")
        problems = verify_chain(sealed, self.signer.verifier())
        sth = self.log.signed_tree_head()
        anchor = self.anchor.publish(sth) if cfg.enable_chain_anchor else {"anchor": "disabled"}
        self.store.put_doc("sth", f"{sth['size']}", {**sth, **anchor}, ts=sth["timestamp"])
        step("PROVENANCE_ATTESTATION", not problems, "; ".join(problems) or f"STH size={sth['size']}")

        # 9 risk / assurance
        scored = {r["metric_id"]: (r["domain"], r["value"]) for r in rows if r["value"] is not None and not r["info"]}
        risk = assess_risk(scored, system.deployment, cfg, flevels, mitigations, {e.id for e in sealed})
        req = [r for r in rows if r["required"]]
        meas = [r for r in req if r["value"] is not None]
        coverage = len(meas) / max(1, len(req))
        rec, conds = dec.recommend(findings, rows, coverage, cfg.min_coverage)
        untested = [f"{r['metric_id']}: {results[r['metric_id']][2].untested_reason or 'not measured'}" for r in rows if r["value"] is None]
        cos = compute_cos({m: r[2] for m, r in results.items()}, {m: r[1] for m, r in results.items()}, cfg)
        regs = {fw: reg_summary(sealed, fw)[fw] for fw in prof.regulatory if fw in reg_summary(sealed)}
        seq = self.store.next_counter(f"car-{now.year}")
        car = build_car(system=system, evaluation_id=eid, profile=prof, mode=mode, evidences=sealed, rows=rows, risk=risk,
                        recommended=rec, conditions=conds, cos=cos, regulatory=regs, untested=untested, evaluator=evaluator,
                        sth=sth, seq=seq, now=now, cfg=cfg, evidence_ok=not problems, signer=self.signer, findings=findings,
                        req_total=len(req), req_measured=len(meas))
        self.store.put_doc("car", car["car_id"], car, system.name, iso(now))
        self.store.put_doc("car_version", f"{car['car_id']}@{car['version']}", car, system.name, iso(now))
        step("RISK_ASSURANCE", note=f"level={car['level']} recommended={rec} risk={risk['level']}")

        # persist datasets by content hash (enables third-party reproduction)
        names = {}
        for _, (_, _, res) in results.items():
            names.update(res.dataset_hashes)
        for n_, h in names.items():
            self.store.put_doc("dataset", h, {"name": n_, "data": ds[n_]})
        step("REPORT_API", note=car["car_id"])
        out = EvaluationResult(eid, system, prof.id, mode, sealed, rows, findings, risk, car, steps, sth, not problems, names)
        self.store.put_doc("evaluation", eid, out.to_dict(), system.name, iso(now))
        return out

    # ------------------------------------------------------------------
    def verifier(self):
        return self.signer.verifier()
