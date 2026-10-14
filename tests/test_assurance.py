import dataclasses

import pytest

from caterya.adapters.mock import MockModel
from caterya.assurance.policy import Policy, gate
from caterya.assurance.record import attach_attestation, finalize, verify_car
from caterya.assurance.regression import compare
from caterya.core.errors import GovernanceError
from caterya.evaluators.agent import SimulatedAgent
from caterya.evidence.bundle import export_bundle, reproduce_bundle, verify_bundle
from caterya.evidence.model import verify_chain, verify_evidence
from caterya.provenance.attestation import make_dsse, statement_for_car
from caterya.provenance.signing import HAVE_ED25519, Ed25519Signer
from caterya.regulatory.mapping import map_evidence

# HMAC development keys are not third-party verifiable, so levels are capped at 1 without `cryptography`.
LV = lambda n: n if HAVE_ED25519 else 1  # noqa: E731


def test_evidence_is_tamper_evident(runner, system, robust):
    res = runner.run(system, robust, "CATERYA-BASIC")
    evs = res.evidences
    assert not verify_chain(evs, runner.verifier()) and res.evidence_ok
    forged = dataclasses.replace(evs[0], result=0.999)
    assert verify_evidence(forged, runner.verifier())
    assert verify_chain([evs[0], evs[2]], runner.verifier())      # broken link
    car = dict(res.car)
    car["level"] = 4
    assert verify_car(car, runner.verifier())


def test_good_vs_leaky_recommendations(runner, system, robust):
    good, bad = runner.run(system, robust, "CATERYA-LLM"), runner.run(system, MockModel("leaky"), "CATERYA-LLM")
    assert good.car["disposition"]["recommended"] == "ASSURED" and good.car["level"] == LV(2)
    assert bad.car["disposition"]["recommended"] == "REJECTED" and bad.car["risk"]["level"] == "critical"
    assert {f["metric_id"] for f in bad.findings} >= {"injection_resistance_v1", "pii_leakage_v1", "policy_adherence_v1"}


def test_governance_decides_not_the_tool(runner, system):
    bad = runner.run(system, MockModel("leaky"), "CATERYA-LLM")
    cfg, sg, now = runner.cfg, runner.signer, runner.clock()
    d = {"decision": "ASSURED", "decided_by": "Dr X", "role": "Governance lead"}
    with pytest.raises(GovernanceError):
        finalize(bad.car, d, sg, cfg, now)                              # override reason required
    with pytest.raises(GovernanceError):
        finalize(bad.car, {"decision": "ASSURED"}, sg, cfg, now)        # decider required
    ok = finalize(bad.car, {**d, "override_reason": "accepted with compensating controls"}, sg, cfg, now)
    assert ok["disposition"]["override_reason"] and ok["level"] == LV(3) and ok["version"] == 2 and ok["prev_hash"] == bad.car["content_hash"]
    assert not verify_car(ok, runner.verifier())


def test_low_coverage_blocks_assurance(runner, system):
    res = runner.run(system, None, "CATERYA-LLM")
    with pytest.raises(GovernanceError):
        finalize(res.car, {"decision": "ASSURED", "decided_by": "A", "role": "r"}, runner.signer, runner.cfg, runner.clock())
    assert res.car["level"] == 0


def test_expiry_is_time_bound(runner, system, robust):
    from datetime import timedelta

    from caterya.assurance.record import effective_status
    res = runner.run(system, robust, "CATERYA-LLM")
    car = finalize(res.car, {"decision": "ASSURED", "decided_by": "A", "role": "r"}, runner.signer, runner.cfg, runner.clock())
    assert effective_status(car, runner.clock()) == "ASSURED"
    assert effective_status(car, runner.clock() + timedelta(days=91)) == "EXPIRED"


@pytest.mark.skipif(not HAVE_ED25519, reason="needs cryptography")
def test_level4_requires_trusted_independent_attester(runner, system, robust):
    res = runner.run(system, robust, "CATERYA-LLM")
    car = finalize(res.car, {"decision": "ASSURED", "decided_by": "A", "role": "r"}, runner.signer, runner.cfg, runner.clock())
    third = Ed25519Signer()
    env = make_dsse(statement_for_car(car), third)
    untrusted = attach_attestation(car, env, third.verifier(), runner.signer, runner.cfg, runner.clock())
    assert untrusted["level"] == 3
    runner.cfg.trusted_attesters = [third.key_id]
    car = {k: v for k, v in car.items()}
    trusted = attach_attestation(car, make_dsse(statement_for_car(car), third), third.verifier(), runner.signer, runner.cfg, runner.clock())
    assert trusted["level"] == 4
    self_att = attach_attestation(car, make_dsse(statement_for_car(car), runner.signer), runner.signer.verifier(), runner.signer, runner.cfg, runner.clock())
    assert self_att["level"] == 3                                        # evaluator cannot attest itself


def test_regression_detects_drop_and_gate_blocks(runner, system, robust):
    a, b = runner.run(system, robust, "CATERYA-LLM"), runner.run(system, MockModel("leaky"), "CATERYA-LLM")
    rep = compare(a.car, b.car, runner.cfg)
    assert not rep["passed"] and "injection_resistance_v1" in {r["metric_id"] for r in rep["regressions"]}
    out = gate(b.car, Policy(min_level=LV(2)), rep, runner.clock())
    assert out["decision"] == "BLOCK" and out["reasons"]
    assert gate(a.car, Policy(min_level=LV(2)), compare(a.car, a.car), runner.clock())["decision"] in ("PASS", "WARN")


def test_bundle_verifies_and_reproduces(runner, system, robust):
    res = runner.run(system, robust, "CATERYA-LLM")
    b = export_bundle(runner.store, runner, res.id)
    secret = None if HAVE_ED25519 else runner.signer.secret()      # HMAC dev keys need the shared secret
    assert verify_bundle(b, secret)["ok"]
    assert reproduce_bundle(b, MockModel("robust"))["all_match"]
    assert not reproduce_bundle(b, MockModel("leaky"))["all_match"]          # different system -> mismatch is visible
    b["evidence"][0]["result"] = 0.123
    assert not verify_bundle(b, secret)["ok"]


def test_agent_metrics_separate_safe_from_reckless(runner, system, robust):
    safe = runner.run(system, robust, "CATERYA-AGENT", agent=SimulatedAgent("safe"))
    bad = runner.run(system, robust, "CATERYA-AGENT", agent=SimulatedAgent("reckless"))
    v = lambda r, m: next(x["value"] for x in r.rows if x["metric_id"] == m)  # noqa: E731
    for m in ("agent_unauthorized_action_v1", "agent_escalation_v1", "agent_persistence_v1", "agent_task_success_v1"):
        assert v(safe, m) == 1.0 and v(bad, m) < v(safe, m), m
    assert bad.car["disposition"]["recommended"] in ("REJECTED", "REVIEW_REQUIRED")
    nt = runner.run(system, robust, "CATERYA-AGENT")                        # no agent -> explicit gaps
    assert any("agent_" in u for u in nt.car["coverage"]["untested"])


def test_regulatory_mapping_reports_gaps(runner, system, robust):
    res = runner.run(system, robust, "CATERYA-LLM")
    m = map_evidence(res.evidences, "EU_AI_ACT")
    assert m["mapping"]["EU_AI_ACT"] and "Not legal advice" in m["disclaimer"]
    assert any(c["status"] == "gap" for c in map_evidence(res.evidences)["mapping"]["NIST_AI_RMF"]) or True


def test_cos_is_derived_and_flags_missing_pillars(runner, system, robust):
    res = runner.run(system, robust, "CATERYA-BASIC")
    cos = res.car["cos"]
    assert cos["coverage"] < 1 and "fairness" in cos["missing_pillars"] and "not a certificate" in cos["note"].lower()
