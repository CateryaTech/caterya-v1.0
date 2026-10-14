"""Regulatory evidence, pillar labels, golden-triangle view, energy map, guardrail monitor."""
import pytest

from caterya.core.config import CateryaConfig
from caterya.core.context import EvalContext
from caterya.core.registry import get_metric
from caterya.core.system import SystemDescriptor
from caterya.evidence.model import Evidence, verify_evidence
from caterya.metrics.base import MetricResult
from caterya.metrics.cos import compute_cos
from caterya.monitoring.monitor import ContinuousMonitor
from caterya.profiles.pillars import PILLAR_MAP
from caterya.profiles.registry import PROFILES
from caterya.provenance.signing import HmacSigner
from caterya.regulatory.evidence import seal_mapping
from caterya.regulatory.mapping import map_evidence
from caterya.viz.energy import build_surface


def _ev(metric, result):
    return Evidence(metric=metric, result=result, id="EV-x", content_hash="sha256:ab")


def test_indonesia_2026_pack_is_thematic_and_sealed():
    evidences = [
        _ev("injection_resistance_v1", 1),
        _ev("policy_adherence_v1", 1),
        _ev("information_faithfulness_v1", 1),
        _ev("provenance_completeness_v1", 1),
        _ev("fairness_parity_v1", 1),
        _ev("fairness_tabular_v1", 1),
        _ev("pii_leakage_v1", 1),
        _ev("reliability_v1", 1),
        _ev("robustness_perturbation_v1", 1),
        _ev("agent_escalation_v1", 1),
    ]
    mapped = map_evidence(evidences, "ID_AI_ETHICS_2026")
    assert "Not legal advice" in mapped["disclaimer"]
    assert "2026" in mapped["frameworks"]["ID_AI_ETHICS_2026"]
    assert all(c["status"] == "evidenced" for c in mapped["mapping"]["ID_AI_ETHICS_2026"])
    signer = HmacSigner(b"reg")
    sealed = seal_mapping(evidences, signer, framework="ID_AI_ETHICS_2026")
    assert sealed.result == 1.0
    assert verify_evidence(sealed, signer.verifier()) == []
    assert "not legal advice" in sealed.claim
    eu = map_evidence([], "EU_AI_ACT")
    assert any(c["status"] == "informational" and c["optional"] for c in eu["mapping"]["EU_AI_ACT"])


def test_every_profile_carries_the_pillar_note():
    assert set(PILLAR_MAP) == {"fairness", "interpretability", "robustness", "transparency"}
    for profile in PROFILES.values():
        assert "fairness" in profile.domain_note and "Lyapunov" in profile.domain_note
    assert any(p.metric_id == "quantum_symmetry_index_v1" for p in PROFILES["CATERYA-QUANTUM"].plans)


def test_golden_triangle_view_is_optional_and_does_not_impute():
    specs = {s.id: s for s in __import__("caterya.core.registry", fromlist=["list_metrics"]).list_metrics()}
    results = {
        "entropy_dispersion_v1": MetricResult("entropy_dispersion_v1", 0.5),
        "symmetry_invariance_v1": MetricResult("symmetry_invariance_v1", 0.5),
    }
    view = compute_cos(results, specs)["golden_triangle_view"]
    assert view["optional"] is True and view["G"] is None
    assert "not imputed" in " ".join(view["limitations"]).lower() or any("not imputed" in n.lower() for n in view["limitations"])
    assert "formula" in view and view["weights"]["aggregation"]


def test_energy_map_hash_is_stable_and_metric_refuses_a_silent_pair():
    a = build_surface(0.2, 0.8, grid=5, label_a="a", label_b="b")
    b = build_surface(0.2, 0.8, grid=5, label_a="a", label_b="b")
    assert a["artifact_hash"] == b["artifact_hash"]
    assert a["marker_parity"] == pytest.approx(0.4)
    ctx = EvalContext(None, datasets={"tabular_predictions": [{"y_pred": 1, "group": "a"}, {"y_pred": 0, "group": "b"}]}, system=SystemDescriptor("s"))
    assert get_metric("fairness_energy_map_v1").run(ctx).untested_reason
    res = get_metric("fairness_energy_map_v1", group_a="a", group_b="b", grid=5).run(ctx)
    assert res.value == 0.0 or res.value == 1.0 or 0.0 <= res.value <= 1.0
    assert res.details["artifact_hash"].startswith("sha256:")


def test_canary_guardrail_window_requests_incident_replay_without_blocking():
    mon = ContinuousMonitor(CateryaConfig())
    assert mon.on_guardrail(0.95) is None
    trigger = None
    for _ in range(5):
        trigger = mon.on_guardrail(0.2)
    assert trigger is not None
    assert trigger.depth == "deep" and trigger.mode == "incident_replay"
    assert mon.plan("fp").mode == "incident_replay"
