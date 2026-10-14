"""`caterya` command line: register / evaluate / evidence / assurance / compare / gate / monitor / serve ..."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .. import PRODUCT_NAME, __version__
from ..assurance.policy import Policy, gate
from ..assurance.record import finalize
from ..assurance.regression import compare, history
from ..assurance.report import render_html, render_markdown
from ..core.config import CateryaConfig, detect_capabilities
from ..core.errors import CateryaError
from ..core.registry import list_metrics
from ..datasets import builtin_datasets
from ..evaluators.agent import SimulatedAgent
from ..evidence.bundle import export_bundle, reproduce_bundle, verify_bundle
from ..evidence.store import build_graph, graph_to_dot
from ..profiles.registry import PROFILES
from ..regulatory.mapping import map_evidence
from .runtime import load_system, make_adapter, make_runner

_J = lambda o: print(json.dumps(o, indent=2, default=str))  # noqa: E731


def _runner(a):
    return make_runner(a.home)


def _get_car(r, cid):
    car = r.store.get_doc("car", cid)
    if not car:
        raise CateryaError(f"unknown CAR {cid}")
    return car


def cmd_init(a):
    r = _runner(a)
    print(f"initialised {r.cfg.home if not a.home else a.home}; signer {r.signer.alg} key_id={r.signer.key_id}")
    if not r.signer.third_party_verifiable:
        print("note: 'cryptography' not installed -> HMAC dev signatures (not third-party verifiable). pip install caterya[crypto]")


def cmd_register(a):
    r, s = _runner(a), load_system(a.file, a.name, a.version, a.model)
    r.store.put_doc("system", s.id, s.to_dict(), s.name)
    print(s.id, s.name, s.version)


def cmd_evaluate(a):
    r, s = _runner(a), load_system(a.system, a.name, a.version, a.model)
    ad = make_adapter(a.adapter, model=a.model, base_url=a.base_url, api_key_env=a.api_key_env, allowed=r.cfg.allowed_endpoints)
    agent = SimulatedAgent(a.agent) if a.agent else None
    ds = json.loads(Path(a.datasets).read_text()) if a.datasets else None
    res = r.run(s, ad, a.profile, mode=a.mode, claim=a.claim, datasets=ds, agent=agent, depth=a.depth)
    if a.json:
        _J(res.summary())
    else:
        print(f"{PRODUCT_NAME}  ·  {res.id}\n")
        for row in res.rows:
            v = "  n/a " if row["value"] is None else f"{row['value']:6.3f}"
            print(f"  {row['status']:<13} {v}  {row['metric_id']}")
        print()
        _J(res.summary())
    if a.out:
        Path(a.out).mkdir(parents=True, exist_ok=True)
        b = export_bundle(r.store, r, res.id, include_data=True)
        (Path(a.out) / "bundle.json").write_text(json.dumps(b, indent=2))
        (Path(a.out) / "report.md").write_text(render_markdown(res.car))
        (Path(a.out) / "report.html").write_text(render_html(res.car))
        print(f"wrote {a.out}/bundle.json, report.md, report.html")


def cmd_evidence(a):
    r = _runner(a)
    if a.action == "export":
        ev = r.store.get_doc("car", a.target)["evaluation"]["id"] if a.target.startswith("CAR-") else a.target
        Path(a.out).write_text(json.dumps(export_bundle(r.store, r, ev), indent=2))
        print("wrote", a.out)
    elif a.action == "verify":
        secret = bytes.fromhex(a.hmac_secret) if a.hmac_secret else None
        rep = verify_bundle(json.loads(Path(a.target).read_text()), secret)
        _J(rep)
        sys.exit(0 if rep["ok"] else 2)
    elif a.action == "reproduce":
        rep = reproduce_bundle(json.loads(Path(a.target).read_text()), make_adapter(a.adapter, model=a.model, base_url=a.base_url))
        _J(rep)
        sys.exit(0 if rep["all_match"] else 3)
    elif a.action == "graph":
        evs = r.store.list_evidence(evaluation_id=a.target)
        g = build_graph(evs)
        print(graph_to_dot(g) if a.dot else json.dumps(g, indent=2))


def cmd_assurance(a):
    r = _runner(a)
    car = _get_car(r, a.car_id)
    if a.action == "report":
        print(render_html(car) if a.html else render_markdown(car))
    elif a.action == "show":
        _J(car)
    elif a.action == "decide":
        new = finalize(car, {"decision": a.decision, "decided_by": a.by, "role": a.role, "rationale": a.rationale,
                             "override_reason": a.override_reason, "conditions": a.condition or []}, r.signer, r.cfg, r.clock())
        r.store.put_doc("car", a.car_id, new, new["system"]["name"], new["evaluation"]["timestamp"])
        r.store.put_doc("car_version", f"{a.car_id}@{new['version']}", new, new["system"]["name"])
        print(f"{a.car_id} v{new['version']}: {new['disposition']['status']} · level {new['level']} {new['level_label']}")
    elif a.action == "history":
        _J(history(r.store.list_docs("car", a.system)))


def cmd_compare(a):
    r = _runner(a)
    rep = compare(_get_car(r, a.old), _get_car(r, a.new), r.cfg)
    for row in rep["rows"]:
        d = "" if row["delta"] is None else f"{row['delta']:+.3f}"
        print(f"  {row['change']:<18} {d:>8}  {row['metric_id']}")
    print("\nregressions:", [x["metric_id"] for x in rep["regressions"]] or "none", "· trade-off:", rep["tradeoff"])
    sys.exit(0 if rep["passed"] else 4)


def cmd_gate(a):
    r = _runner(a)
    car = _get_car(r, a.car_id)
    reg = compare(_get_car(r, a.baseline), car, r.cfg) if a.baseline else None
    out = gate(car, Policy.load(a.policy), reg, r.clock())
    _J(out)
    sys.exit(1 if out["decision"] == "BLOCK" else 0)


def cmd_list(a):
    if a.what == "profiles":
        for p in PROFILES.values():
            print(f"{p.id:<20} {len(p.plans):>2} metrics  {p.description}")
    elif a.what == "metrics":
        for s in list_metrics():
            print(f"{s.id:<34} {s.domain.value:<16} {s.status:<12} {s.title}")
    elif a.what == "params":
        for p in CateryaConfig.describe():
            print(f"{p['env']:<36} = {p['default']!r:<22} {p['help']}")
    elif a.what == "capabilities":
        _J(detect_capabilities(CateryaConfig.from_env()))
    elif a.what == "datasets":
        for k, v in builtin_datasets().items():
            print(f"{k:<22} {len(v)} records")


def cmd_regmap(a):
    r = _runner(a)
    evs = r.store.list_evidence(evaluation_id=a.evaluation)
    m = map_evidence(evs, a.framework)
    for fw, cs in m["mapping"].items():
        print(f"\n{fw}: {m['frameworks'][fw]}")
        for c in cs:
            print(f"  {c['status']:<16} {c['clause']:<14} {c['title']}")
    print("\n" + m["disclaimer"])
    if a.seal:
        from ..regulatory.evidence import seal_mapping
        ev = seal_mapping(evs, r.signer, framework=a.framework, prev_hash=r.store.head_hash(), profile="", mode="pre_release")
        r.store.put_evidence(ev, "", a.evaluation)
        payload = ev.to_dict()
        if a.out:
            Path(a.out).write_text(json.dumps(payload, indent=2))
            print("wrote", a.out)
        else:
            _J({"id": ev.id, "result": ev.result, "claim": ev.claim, "disclaimer": m["disclaimer"]})


def _load_rows(path: str) -> list:
    raw = json.loads(Path(path).read_text())
    if isinstance(raw, dict) and "predictions" in raw and "sensitive_attributes" in raw:
        preds = raw["predictions"]
        attrs = raw["sensitive_attributes"]
        names = list(attrs)
        rows = []
        for i, pred in enumerate(preds):
            rows.append({"y_pred": pred, "sensitive": {name: attrs[name][i] for name in names}})
        return rows
    if isinstance(raw, dict) and "rows" in raw:
        return list(raw["rows"])
    if isinstance(raw, list):
        return raw
    raise CateryaError("quantum data must be a list of rows or {predictions, sensitive_attributes}")


def cmd_quantum(a):
    from ..guardrails.evidence import seal_decision
    from ..provenance.signing import HmacSigner
    from ..quantum.backend import BACKENDS, fidelity, get_backend
    from ..quantum.entropy import entanglement_from_rates
    from ..quantum.symmetry import evaluate_rows, group_rates
    from ..quantum.types import CircuitSpec

    if a.action == "backends":
        _J({name: {"available": backend.available(), "version": backend.version() if backend.available() else "not-installed"} for name, backend in BACKENDS.items()})
        return
    if not a.data:
        raise CateryaError("quantum " + a.action + " needs --data")
    rows = _load_rows(a.data)
    noise = None
    if a.noise:
        kind, _, p = a.noise.partition(":")
        noise = {"type": kind, "p": float(p or 0)}
    signer = HmacSigner()
    if a.action == "symmetry":
        payload = evaluate_rows(rows, backend=a.backend, shots=a.shots, seed=a.seed, noise=noise, remote=a.remote or None, min_support=a.min_support)
        metric = "quantum_symmetry_index_v1"
        value = payload.get("value")
        limitations = list(payload.get("limitations") or [])
        details = {"per_attribute": {k: {kk: vv for kk, vv in item.items() if kk != "circuit"} for k, item in payload.get("per_attribute", {}).items()}}
        untested = payload.get("untested")
    elif a.action == "entanglement":
        attrs_rows = rows
        rates, _sup = group_rates(attrs_rows, min_support=a.min_support) if not any("sensitive" in r for r in rows) else group_rates(rows, attribute=sorted({k for r in rows for k in (r.get("sensitive") or {})})[0], min_support=a.min_support)
        payload = entanglement_from_rates(rates, backend=a.backend)
        metric = "entanglement_entropy_v1"
        value = payload.get("value")
        limitations = list(payload.get("limitations") or [])
        details = {k: payload.get(k) for k in ("circuit_hash", "groups", "partition_keep", "n_qubits", "backend")}
        untested = payload.get("untested")
    elif a.action == "fidelity":
        if not a.backend_b:
            raise CateryaError("fidelity needs --backend-b")
        spec = CircuitSpec.from_dict(json.loads(Path(a.data).read_text()))
        left = get_backend(a.backend).run(spec, shots=a.shots, seed=a.seed, noise=noise, remote=a.remote or None)
        right = get_backend(a.backend_b).run(spec, shots=a.shots, seed=a.seed, noise=noise)
        value = fidelity(left.probabilities, right.probabilities)
        metric = "quantum_fidelity_v1"
        limitations = list(left.limitations) + list(right.limitations)
        details = {"left": left.to_meta(), "right": right.to_meta()}
        untested = None
        payload = {"value": value}
    else:
        raise CateryaError(a.action)
    ev = seal_decision(
        signer, metric_id=metric, value=value, claim=f"quantum {a.action} ({a.backend})",
        details=details, limitations=limitations, seed=a.seed, n=len(rows), untested=untested, mode="pre_release",
    )
    out = {"value": value, "untested": untested, "evidence": ev.to_dict(), "note": "HMAC development signature unless you seal with the runner's signer. Not a certificate."}
    if a.action == "symmetry":
        out["summary"] = {k: item.get("value") for k, item in payload.get("per_attribute", {}).items()}
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=2, default=str))
        print("wrote", a.out)
    else:
        _J(out)


def cmd_guardrail(a):
    from ..guardrails import CATERYAGuardrail, EthicsSwarm
    text = Path(a.file).read_text() if a.file else a.text
    context = json.loads(a.context) if a.context else {}
    evaluation = json.loads(Path(a.evaluation).read_text()) if a.evaluation else None
    if a.action == "check":
        decision = CATERYAGuardrail(min_score=a.threshold).check(
            text, sensitive_context=context, evaluation=evaluation, mode=a.mode, request_remediation=a.remediate,
        )
        payload = decision.to_dict()
    else:
        agents = [x for x in a.agents.split(",") if x] or None
        report = EthicsSwarm(agents, threshold=a.threshold).evaluate(text, evaluation=evaluation, context=context, mode=a.mode)
        payload = report.to_dict()
    payload["note"] = "Recommendation only. Release, block, or certification still needs a named decider."
    if a.out:
        Path(a.out).write_text(json.dumps(payload, indent=2))
        print("wrote", a.out)
    else:
        _J(payload)


def cmd_serve(a):
    try:
        import uvicorn
    except ImportError:
        sys.exit("pip install 'caterya[api]'")
    from ..api.app import create_app
    cfg = CateryaConfig.from_env()
    uvicorn.run(create_app(a.home), host=a.host or cfg.host, port=a.port or cfg.port)


def cmd_demo(a):
    r = _runner(a)
    from ..core.system import SystemDescriptor
    s = SystemDescriptor("demo-assistant", "1.0.0", provider="caterya-mock", model_id="mock", model_version="1.0",
                         code_hash="sha256:demo", environment={"image": "demo"}, dataset_hashes={"train": "sha256:demo"},
                         deployment={"environment": "staging", "sector": "finance", "criticality": "high", "exposure": 0.6})
    from ..adapters.mock import MockModel
    for beh in ("robust", "leaky"):
        s2 = SystemDescriptor.from_dict({**s.to_dict(), "version": "1.0.0" if beh == "robust" else "1.1.0", "model_id": f"mock-{beh}"})
        res = r.run(s2, MockModel(beh), "CATERYA-LLM")
        print(beh, "->", res.car["car_id"], res.summary()["status"], "recommended:", res.car["disposition"]["recommended"])
    cars = r.store.list_docs("car")
    print("\nTry:  caterya compare", cars[0]["car_id"], cars[1]["car_id"])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("caterya", description=f"{PRODUCT_NAME} v{__version__} — Measure. Verify. Assure.")
    p.add_argument("--home", help="state dir (default $CATERYA_HOME or ./.caterya)")
    p.add_argument("--version", action="version", version=__version__)
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("init").set_defaults(fn=cmd_init)
    s = sp.add_parser("register", help="register a system descriptor"); s.add_argument("--file"); s.add_argument("--name"); s.add_argument("--version", default="0.0.0"); s.add_argument("--model", default=""); s.set_defaults(fn=cmd_register)
    s = sp.add_parser("evaluate", help="run an evaluation profile")
    s.add_argument("--system", help="system.json"); s.add_argument("--name"); s.add_argument("--version", default="0.0.0")
    s.add_argument("--profile", default="CATERYA-LLM"); s.add_argument("--mode", default="pre_release")
    s.add_argument("--adapter", default="mock:robust", help="none | mock[:behavior[:severity]] | openai | anthropic")
    s.add_argument("--model", default=""); s.add_argument("--base-url", default=""); s.add_argument("--api-key-env", default="")
    s.add_argument("--agent", choices=["safe", "reckless"], help="simulated agent for agent profiles")
    s.add_argument("--datasets", help="JSON file of extra datasets"); s.add_argument("--claim"); s.add_argument("--depth", choices=["light", "standard", "deep"])
    s.add_argument("--out", help="export bundle + reports here"); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_evaluate)
    s = sp.add_parser("evidence"); s.add_argument("action", choices=["export", "verify", "reproduce", "graph"]); s.add_argument("target")
    s.add_argument("--out", default="bundle.json"); s.add_argument("--adapter", default="none"); s.add_argument("--model", default=""); s.add_argument("--base-url", default="")
    s.add_argument("--hmac-secret", help="hex secret (dev signatures only)"); s.add_argument("--dot", action="store_true"); s.set_defaults(fn=cmd_evidence)
    s = sp.add_parser("assurance"); s.add_argument("action", choices=["report", "show", "decide", "history"]); s.add_argument("car_id", nargs="?")
    s.add_argument("--html", action="store_true"); s.add_argument("--system", default="")
    s.add_argument("--decision", choices=["ASSURED", "CONDITIONALLY_ASSURED", "REJECTED", "REVIEW_REQUIRED"]); s.add_argument("--by"); s.add_argument("--role")
    s.add_argument("--rationale", default=""); s.add_argument("--override-reason", default=""); s.add_argument("--condition", action="append"); s.set_defaults(fn=cmd_assurance)
    s = sp.add_parser("compare", help="trustworthiness regression between two CARs"); s.add_argument("old"); s.add_argument("new"); s.set_defaults(fn=cmd_compare)
    s = sp.add_parser("gate", help="CI/CD policy gate (exit 1 = BLOCK)"); s.add_argument("car_id"); s.add_argument("--policy", required=True); s.add_argument("--baseline"); s.set_defaults(fn=cmd_gate)
    s = sp.add_parser("list"); s.add_argument("what", choices=["profiles", "metrics", "params", "capabilities", "datasets"]); s.set_defaults(fn=cmd_list)
    s = sp.add_parser("regmap", help="regulatory mapping of an evaluation's evidence"); s.add_argument("evaluation"); s.add_argument("--framework"); s.add_argument("--seal", action="store_true"); s.add_argument("--out"); s.set_defaults(fn=cmd_regmap)
    s = sp.add_parser("quantum", help="run a research-grade quantum metric and seal Evidence")
    s.add_argument("action", choices=["symmetry", "fidelity", "entanglement", "backends"])
    s.add_argument("--data", help="rows JSON, or a circuit JSON for fidelity")
    s.add_argument("--backend", default="classical")
    s.add_argument("--backend-b", default="")
    s.add_argument("--shots", type=int, default=0)
    s.add_argument("--seed", type=int, default=1337)
    s.add_argument("--noise", default="", help="readout_flip:0.01")
    s.add_argument("--remote", default="", help="Qiskit backend name; no local fallback")
    s.add_argument("--min-support", type=int, default=1)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_quantum)
    s = sp.add_parser("guardrail", help="score an output and seal a recommendation; does not block")
    s.add_argument("action", choices=["check", "swarm"])
    s.add_argument("--text", default="")
    s.add_argument("--file")
    s.add_argument("--mode", choices=["heuristic", "full"], default="heuristic")
    s.add_argument("--threshold", type=float, default=0.70)
    s.add_argument("--remediate", action="store_true")
    s.add_argument("--evaluation", help="JSON file with a scores object (full mode)")
    s.add_argument("--context", help="JSON object")
    s.add_argument("--agents", default="", help="comma-separated swarm agents")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_guardrail)
    s = sp.add_parser("serve", help="start API + dashboard"); s.add_argument("--host"); s.add_argument("--port", type=int); s.set_defaults(fn=cmd_serve)
    sp.add_parser("demo", help="evaluate two mock systems end-to-end").set_defaults(fn=cmd_demo)
    return p


def main(argv: list[str] | None = None) -> None:
    a = build_parser().parse_args(argv)
    try:
        a.fn(a)
    except CateryaError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
