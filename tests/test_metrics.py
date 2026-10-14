import pytest

from caterya.adapters.mock import MockModel
from caterya.core.context import EvalContext
from caterya.core.registry import get_metric, list_metrics
from caterya.core.system import SystemDescriptor
from caterya.datasets import builtin_datasets
from caterya.metrics.fairness import group_metrics
from caterya.metrics.privacy import redact, scan_pii
from caterya.metrics.stability import estimate_lambda
from caterya.metrics.stats import spearman
from caterya.quantum.backend import fidelity, von_neumann_entropy_of_reduced


def run(mid, model, **p):
    ctx = EvalContext(model, datasets=builtin_datasets(), system=SystemDescriptor("s"))
    return get_metric(mid, **p).run(ctx)


def test_all_specs_have_hashes_and_limitations():
    specs = list_metrics()
    assert len(specs) >= 27
    for s in specs:
        assert s.spec_hash().startswith("sha256:") and s.limitations, s.id


def test_metrics_deterministic():
    a, b = run("reliability_v1", MockModel("noisy")), run("reliability_v1", MockModel("noisy"))
    assert a.value == b.value and a.raw_outputs_hash == b.raw_outputs_hash


@pytest.mark.parametrize("beh,mid", [("brittle", "symmetry_invariance_v1"), ("brittle", "robustness_perturbation_v1"),
                                     ("noisy", "reliability_v1"), ("noisy", "entropy_dispersion_v1"),
                                     ("leaky", "injection_resistance_v1"), ("leaky", "pii_leakage_v1"),
                                     ("leaky", "policy_adherence_v1"), ("biased", "fairness_parity_v1"),
                                     ("chaotic", "behavioral_lyapunov_v1"), ("forgetful", "context_coupling_v1")])
def test_each_flaw_is_detected_by_its_metric(beh, mid):
    assert run(mid, MockModel("robust")).value > run(mid, MockModel(beh)).value + 0.15


@pytest.mark.parametrize("beh,mid", [("leaky", "injection_resistance_v1"), ("brittle", "symmetry_invariance_v1"),
                                     ("biased", "fairness_parity_v1"), ("noisy", "reliability_v1")])
def test_dose_response_is_monotone(beh, mid):
    vals = [run(mid, MockModel(beh, severity=s)).value for s in (0.0, 0.3, 0.6, 0.9)]
    assert spearman(list(range(4)), vals) < -0.8, vals


def test_robust_mock_scores_high_everywhere():
    for mid in ("reliability_v1", "robustness_perturbation_v1", "symmetry_invariance_v1", "policy_adherence_v1",
                "injection_resistance_v1", "pii_leakage_v1", "fairness_parity_v1", "information_faithfulness_v1"):
        assert run(mid, MockModel("robust")).value >= 0.99, mid


def test_untested_not_zero_when_model_cannot_report():
    r = run("calibration_ece_v1", MockModel("chaotic", 1.0))
    assert r.value is None and r.untested_reason


def test_no_adapter_is_a_gap_not_a_crash(runner, system):
    res = runner.run(system, None, "CATERYA-LLM")
    assert any(r["status"] == "untested" for r in res.rows)
    assert res.car["disposition"]["recommended"] == "EVALUATED"


def test_lambda_estimator():
    assert estimate_lambda([0.1, 0.05, 0.02, 0.01]) < 0
    assert estimate_lambda([0.01, 0.03, 0.09, 0.27, 0.8]) > 0.5
    assert estimate_lambda([0.0, 0.0]) is None


def test_fairness_tabular_gaps_and_suppression():
    m = group_metrics([1, 1, 0, 0] * 10, [1, 1, 0, 0] * 5 + [0, 0, 0, 0] * 5, ["a"] * 20 + ["b"] * 20, 5)
    assert m["equal_opportunity_gap"] > 0.9
    assert group_metrics([1], [1], ["tiny"], 5)["suppressed_small_groups"] == ["tiny"]


def test_pii_scan_and_redact():
    t = "mail a.b@example.org call +62 812 0000 0000 card 4111 1111 1111 1111"
    assert {"email", "phone_id", "card"} <= set(scan_pii(t))
    assert "example.org" not in redact(t)


def test_quantum_helpers():
    assert abs(fidelity([.5, .5], [.5, .5]) - 1) < 1e-12 and fidelity([1, 0], [0, 1]) == 0
    pytest.importorskip("numpy")
    assert abs(von_neumann_entropy_of_reduced([1, 0, 0, 1], 2, 2) - 1.0) < 1e-9   # Bell state
    assert abs(von_neumann_entropy_of_reduced([1, 0, 0, 0], 2, 2)) < 1e-9
