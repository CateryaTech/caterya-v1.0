"""REST API (FastAPI). Endpoints follow architecture v1.0 §19: /v1/evaluations, /v1/evidence, /v1/assurance."""
from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import PRODUCT_NAME, __version__
from ..adapters.mock import BEHAVIORS
from ..assurance.policy import Policy, gate
from ..assurance.record import finalize, verify_car
from ..assurance.regression import compare, history
from ..assurance.report import render_html, render_markdown
from ..cli.runtime import make_adapter, make_runner
from ..core.canonical import jsonable
from ..core.config import CateryaConfig, detect_capabilities
from ..core.errors import CateryaError, GovernanceError
from ..core.registry import list_metrics
from ..core.system import SystemDescriptor
from ..evaluators.agent import SimulatedAgent
from ..evidence.bundle import export_bundle
from ..evidence.model import Evidence, verify_evidence
from ..evidence.store import build_graph
from ..monitoring.incident import IncidentLoop
from ..monitoring.monitor import ContinuousMonitor
from ..profiles.registry import PROFILES
from ..provenance.log import verify_inclusion_proof
from ..regulatory.mapping import FRAMEWORKS, map_evidence


class AdapterSpec(BaseModel):
    kind: str = Field("mock:robust", description="mock[:behavior[:severity]] | openai | anthropic | none")
    model: str = ""
    base_url: str = ""
    api_key_env: str = ""


class EvaluationRequest(BaseModel):
    system: dict
    profile: str = "CATERYA-LLM"
    mode: str = "pre_release"
    adapter: AdapterSpec = AdapterSpec()
    agent: Optional[str] = None
    depth: Optional[str] = None
    claim: Optional[str] = None
    datasets: Optional[dict] = None


class DecisionRequest(BaseModel):
    decision: str
    decided_by: str
    role: str
    rationale: str = ""
    override_reason: str = ""
    conditions: list[str] = []


class AssuranceRequest(BaseModel):
    evaluation_id: str
    decision: Optional[DecisionRequest] = None


class CompareRequest(BaseModel):
    old: str
    new: str


class GateRequest(BaseModel):
    car_id: str
    baseline: Optional[str] = None
    policy: dict = {}


class SignalRequest(BaseModel):
    system: str
    signal: str
    values: list[float]


class IncidentRequest(BaseModel):
    system: str
    description: str
    prompt: str
    output: str
    failure_pattern: str
    system_prompt: Optional[str] = None


def create_app(home: Optional[str] = None) -> FastAPI:
    runner = make_runner(home)
    cfg: CateryaConfig = runner.cfg
    store = runner.store
    monitors: dict[str, ContinuousMonitor] = {}
    incidents = IncidentLoop(store, runner.clock)
    api_key = os.environ.get("CATERYA_API_KEY", "")

    def auth(authorization: str = Header(default="")) -> None:
        if api_key and not hmac.compare_digest(authorization.removeprefix("Bearer ").strip(), api_key):
            raise HTTPException(401, "missing or invalid bearer token")

    app = FastAPI(title=PRODUCT_NAME, version=__version__,
                  description="Open, vendor-neutral AI evaluation, evidence and assurance. CATERYA measures; governance decides.")

    @app.exception_handler(CateryaError)
    async def _err(_, e: CateryaError):  # noqa: ANN001
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": str(e)}, status_code=409 if isinstance(e, GovernanceError) else 400)

    @app.get("/v1/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__, "signer": runner.signer.identity(), "log_size": len(runner.log.items)}

    @app.get("/v1/capabilities")
    def caps() -> dict:
        return detect_capabilities(cfg)

    @app.get("/v1/profiles")
    def profiles() -> list:
        return [{"id": p.id, "description": p.description, "metrics": [m.metric_id for m in p.plans], "continuous": p.continuous,
                 "requires_human": p.requires_human, "ttl_days": p.ttl_days or cfg.ttl_days, "regulatory": list(p.regulatory)}
                for p in PROFILES.values()]

    @app.get("/v1/metrics")
    def metrics() -> list:
        return [jsonable(s) | {"spec_hash": s.spec_hash()} for s in list_metrics()]

    @app.get("/v1/parameters")
    def params() -> list:
        return CateryaConfig.describe()

    @app.get("/v1/mock-behaviors")
    def behaviors() -> list:
        return list(BEHAVIORS)

    # evaluations ------------------------------------------------------
    @app.post("/v1/evaluations", dependencies=[Depends(auth)])
    def run_eval(req: EvaluationRequest) -> dict:
        sysd = SystemDescriptor.from_dict(req.system)
        ad = make_adapter(req.adapter.kind, model=req.adapter.model, base_url=req.adapter.base_url,
                          api_key_env=req.adapter.api_key_env, allowed=cfg.allowed_endpoints or ["__none__"])
        res = runner.run(sysd, ad, req.profile, mode=req.mode, claim=req.claim, datasets=req.datasets,
                         agent=SimulatedAgent(req.agent) if req.agent else None, depth=req.depth)
        return {**res.to_dict(), "summary": res.summary(), "car": res.car}

    @app.get("/v1/evaluations")
    def list_evals(system: str = "") -> list:
        return [{k: e[k] for k in ("id", "profile", "mode", "car_id")} | {"system": e["system"]["name"], "version": e["system"]["version"]}
                for e in store.list_docs("evaluation", system)]

    @app.get("/v1/evaluations/{eid}")
    def get_eval(eid: str) -> dict:
        e = store.get_doc("evaluation", eid)
        if not e:
            raise HTTPException(404, "evaluation not found")
        return e

    @app.get("/v1/evaluations/{eid}/bundle")
    def bundle(eid: str) -> dict:
        if not store.get_doc("evaluation", eid):
            raise HTTPException(404, "evaluation not found")
        return export_bundle(store, runner, eid)

    # evidence ---------------------------------------------------------
    @app.get("/v1/evidence")
    def list_ev(system_id: str = "", evaluation_id: str = "", metric: str = "", limit: int = Query(200, le=1000)) -> list:
        return [e.to_dict() for e in store.list_evidence(system_id, evaluation_id, metric, limit)]

    @app.post("/v1/evidence", dependencies=[Depends(auth)])
    def post_ev(ev: dict[str, Any]) -> dict:
        """Ingest externally produced evidence. It is verified (hash + signature when the key is ours) before registry entry."""
        e = Evidence.from_dict(ev)
        probs = verify_evidence(e, None, None)
        if probs:
            raise HTTPException(422, {"problems": probs})
        if e.evaluator.get("key_id") == runner.signer.key_id:
            probs = verify_evidence(e, runner.verifier())
            if probs:
                raise HTTPException(422, {"problems": probs})
        if store.get_evidence(e.id):
            raise HTTPException(409, "evidence already registered")
        store.put_evidence(e, "", "external")
        store.put_leaf(runner.log.append(e.content_hash), e.content_hash)
        return {"id": e.id, "registered": True, "signature_checked_against_local_key": e.evaluator.get("key_id") == runner.signer.key_id}

    @app.get("/v1/evidence/{eid}")
    def get_ev(eid: str) -> dict:
        e = store.get_evidence(eid)
        if not e:
            raise HTTPException(404, "evidence not found")
        return e.to_dict()

    @app.get("/v1/evidence/{eid}/verify")
    def verify_ev(eid: str) -> dict:
        e = store.get_evidence(eid)
        if not e:
            raise HTTPException(404, "evidence not found")
        probs = verify_evidence(e, runner.verifier() if e.evaluator.get("key_id") == runner.signer.key_id else None)
        proof = None
        if e.content_hash in runner.log.items:
            proof = runner.log.inclusion_proof(runner.log.items.index(e.content_hash))
        return {"id": eid, "valid": not probs, "problems": probs, "inclusion_proof_valid": bool(proof and verify_inclusion_proof(proof)),
                "proof": proof}

    @app.get("/v1/log/head")
    def log_head() -> dict:
        return runner.log.signed_tree_head()

    @app.get("/v1/graph/{evaluation_id}")
    def graph(evaluation_id: str) -> dict:
        evs = store.list_evidence(evaluation_id=evaluation_id)
        e = store.get_doc("evaluation", evaluation_id)
        return build_graph(evs, e["system"] if e else None, (e or {}).get("car_id", ""))

    # assurance --------------------------------------------------------
    @app.post("/v1/assurance", dependencies=[Depends(auth)])
    def assure(req: AssuranceRequest) -> dict:
        e = store.get_doc("evaluation", req.evaluation_id)
        if not e:
            raise HTTPException(404, "evaluation not found")
        car = store.get_doc("car", e["car_id"])
        if req.decision:
            car = _decide(car, req.decision)
        return car

    def _decide(car: dict, d: DecisionRequest) -> dict:
        new = finalize(car, d.model_dump(), runner.signer, cfg, runner.clock(), evidence_ok=bool(store.get_doc("evaluation", car["evaluation"]["id"])["evidence_ok"]))
        store.put_doc("car", new["car_id"], new, new["system"]["name"], new["evaluation"]["timestamp"])
        store.put_doc("car_version", f"{new['car_id']}@{new['version']}", new, new["system"]["name"])
        return new

    @app.get("/v1/assurance")
    def list_cars(system: str = "") -> list:
        return [{"car_id": c["car_id"], "version": c["version"], "system": c["system"]["name"], "system_version": c["system"]["version"],
                 "profile": c["evaluation"]["profile"], "status": c["disposition"]["status"], "recommended": c["disposition"]["recommended"],
                 "level": c["level"], "level_label": c["level_label"], "risk": c["risk"]["level"], "timestamp": c["evaluation"]["timestamp"]}
                for c in store.list_docs("car", system)]

    @app.get("/v1/assurance/{cid}")
    def get_car(cid: str) -> dict:
        c = store.get_doc("car", cid)
        if not c:
            raise HTTPException(404, "assurance record not found")
        return c

    @app.post("/v1/assurance/{cid}/decision", dependencies=[Depends(auth)])
    def decide(cid: str, d: DecisionRequest) -> dict:
        return _decide(get_car(cid), d)

    @app.get("/v1/assurance/{cid}/verify")
    def verify_c(cid: str) -> dict:
        c = get_car(cid)
        probs = verify_car(c, runner.verifier() if c["signer"]["key_id"] == runner.signer.key_id else None)
        return {"car_id": cid, "valid": not probs, "problems": probs}

    @app.get("/v1/assurance/{cid}/report")
    def report(cid: str, format: str = "md"):
        c = get_car(cid)
        return HTMLResponse(render_html(c)) if format == "html" else PlainTextResponse(render_markdown(c))

    @app.get("/v1/assurance/{cid}/regulatory")
    def regulatory(cid: str, framework: Optional[str] = None) -> dict:
        c = get_car(cid)
        return map_evidence(store.list_evidence(evaluation_id=c["evaluation"]["id"]), framework)

    @app.get("/v1/regulatory/frameworks")
    def frameworks() -> dict:
        return FRAMEWORKS

    @app.post("/v1/compare")
    def cmp(req: CompareRequest) -> dict:
        return compare(get_car(req.old), get_car(req.new), cfg)

    @app.get("/v1/history/{system}")
    def hist(system: str) -> list:
        return history(store.list_docs("car", system))

    @app.post("/v1/gate")
    def do_gate(req: GateRequest) -> dict:
        car = get_car(req.car_id)
        pol = Policy(**{k: v for k, v in req.policy.items() if k in Policy.__dataclass_fields__})
        return gate(car, pol, compare(get_car(req.baseline), car, cfg) if req.baseline else None, runner.clock())

    # monitoring / incidents -----------------------------------------------
    @app.post("/v1/monitor/signals", dependencies=[Depends(auth)])
    def signals(req: SignalRequest) -> dict:
        m = monitors.setdefault(req.system, ContinuousMonitor(cfg, runner.clock))
        for v in req.values:
            m.ingest(req.signal, v)
        trig = m.plan()
        return {"alerts": [a.__dict__ for a in m.check()], "trigger": trig and {"depth": trig.depth, "reason": trig.reason, "mode": trig.mode}}

    @app.post("/v1/incidents", dependencies=[Depends(auth)])
    def open_incident(r: IncidentRequest) -> dict:
        return incidents.capture(r.system, r.description, r.prompt, r.output, r.failure_pattern, r.system_prompt)

    @app.get("/v1/incidents")
    def list_incidents() -> list:
        return store.list_docs("incident")

    # UI ---------------------------------------------------------------
    ui = Path(__file__).resolve().parent.parent / "ui" / "static"
    if ui.exists():
        app.mount("/ui", StaticFiles(directory=str(ui), html=True), name="ui")

        @app.get("/", include_in_schema=False)
        def root():
            return RedirectResponse("/ui/")
    return app
