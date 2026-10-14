"""Quantum extension: classical simulator, optional backends, evidence metadata."""
import math

import pytest

from caterya.core.context import EvalContext
from caterya.core.errors import CapabilityUnavailable, ConfigError
from caterya.core.registry import get_metric
from caterya.core.system import SystemDescriptor
from caterya.evidence.model import verify_evidence
from caterya.guardrails.evidence import seal_decision
from caterya.provenance.signing import HmacSigner
from caterya.quantum.backend import fidelity, get_backend, von_neumann_entropy_of_reduced
from caterya.quantum.symmetry import build_symmetry_circuit, evaluate_rates, evaluate_rows
from caterya.quantum.types import CircuitSpec


def _rows(rates):
    rows = []
    for label, rate in rates.items():
        ones = int(round(rate * 10))
        for i in range(10):
            rows.append({"y_pred": 1 if i < ones else 0, "group": label})
    return rows


def test_equal_rates_are_symmetric_and_biased_rates_are_lower():
    even = evaluate_rates({"a": 0.5, "b": 0.5}, backend="classical")
    gap = evaluate_rates({"a": 1.0, "b": 0.0}, backend="classical")
    assert even["value"] == pytest.approx(1.0, abs=1e-9)
    assert gap["value"] < 0.8
    assert even["circuit_hash"].startswith("sha256:")
    assert even["circuit_hash"] == build_symmetry_circuit([0.5, 0.5]).circuit_hash()
    assert "statevector" in even["value_source"]
    assert even["backend"]["shots"] == 0
    assert even["backend"]["noise_model"] is None


def test_single_group_is_untested_not_perfect():
    payload = evaluate_rows([{"y_pred": 1, "group": "only"}])
    assert payload["value"] is None
    assert "not scored as perfect" in payload["per_attribute"]["group"]["untested"]


def test_shots_are_reproducible_and_noise_is_not_applied_to_the_value():
    spec = build_symmetry_circuit([1.0, 0.0])
    backend = get_backend("classical")
    a = backend.run(spec, shots=400, seed=7)
    b = backend.run(spec, shots=400, seed=7)
    assert a.shot_probabilities == b.shot_probabilities
    noisy = backend.run(spec, shots=400, seed=7, noise={"type": "readout_flip", "p": 0.2, "qubit": 0})
    assert noisy.noise_applied_to == "shot_estimate"
    assert noisy.probabilities == a.probabilities
    assert noisy.shot_probabilities != a.shot_probabilities
    with pytest.raises(ConfigError):
        backend.run(spec, shots=0, noise={"type": "readout_flip", "p": 0.2})
    with pytest.raises(ConfigError):
        backend.run(spec, shots=10, noise={"type": "depolarizing", "p": 0.1})


def test_supplied_distribution_shortcut_and_bell_entropy():
    assert get_backend("classical").distribution({"probabilities": [0.2, 0.8]}) == [0.2, 0.8]
    assert abs(fidelity([0.5, 0.5], [0.5, 0.5]) - 1) < 1e-12
    assert abs(von_neumann_entropy_of_reduced([1, 0, 0, 1], 2, 2) - 1.0) < 1e-9


def test_metric_seals_backend_metadata_and_refuses_missing_data():
    ctx = EvalContext(None, datasets={}, system=SystemDescriptor("s"))
    assert get_metric("quantum_symmetry_index_v1").run(ctx).untested_reason
    rows = _rows({"a": 0.2, "b": 0.8})
    ctx = EvalContext(None, datasets={"quantum_fairness": rows}, system=SystemDescriptor("s"))
    res = get_metric("quantum_symmetry_index_v1", backend="classical", min_support=1, shots=0).run(ctx)
    assert res.value is not None and 0.0 <= res.value < 1.0
    assert res.details["circuit_hash"].startswith("sha256:")
    assert res.details["backend"] == "classical"
    assert res.details["shots"] == 0
    assert any("Research-grade" in note for note in res.limitations)
    signer = HmacSigner(b"test-secret")
    ev = seal_decision(
        signer, metric_id="quantum_symmetry_index_v1", value=res.value, claim="qsi",
        details=res.details, limitations=res.limitations, seed=ctx.seed, n=res.n,
    )
    assert verify_evidence(ev, signer.verifier()) == []


def test_remote_qiskit_does_not_fall_back(monkeypatch):
    monkeypatch.delenv("QISKIT_IBM_TOKEN", raising=False)
    monkeypatch.delenv("IBM_QUANTUM_TOKEN", raising=False)
    spec = CircuitSpec("x", 1, ({"op": "h", "wire": 0},))
    with pytest.raises(CapabilityUnavailable, match="No local"):
        get_backend("qiskit").run(spec, shots=16, remote="ibm_dummy")


@pytest.mark.parametrize("name", ["pennylane", "qiskit"])
def test_optional_backend_matches_classical_swap_test(name):
    pytest.importorskip(name if name != "qiskit" else "qiskit")
    rates = {"a": 0.25, "b": 0.75}
    classical = evaluate_rates(rates, backend="classical")
    other = evaluate_rates(rates, backend=name)
    assert other["value"] == pytest.approx(classical["value"], abs=1e-6)
    assert other["circuit_hash"] == classical["circuit_hash"]
    assert name in other["backend"]["backend_version"]


def test_entanglement_quantity_is_not_a_score_and_needs_a_cut():
    from caterya.quantum.entropy import entanglement_from_rates
    same = entanglement_from_rates({"a": 0.5, "b": 0.5})
    gap = entanglement_from_rates({"a": 1.0, "b": 0.0})
    assert same["value"] is not None and same["value"] >= 0.0
    assert gap["value"] is not None
    assert "not a trustworthiness score" in " ".join(same["limitations"]).lower() or any("not a trustworthiness" in n.lower() or "Higher is not" in n for n in same["limitations"])
    ctx = EvalContext(None, datasets={"quantum_states": [{"state": [(1, 0), (0, 0), (0, 0), (1, 0)], "dim_a": 2, "dim_b": 2}]}, system=SystemDescriptor("s"))
    res = get_metric("entanglement_entropy_v1").run(ctx)
    assert res.value == pytest.approx(1.0, abs=1e-6)
    assert res.unit == "bits"


def test_fidelity_metric_executes_two_backends_when_present():
    spec = CircuitSpec("ry", 1, ({"op": "ry", "wire": 0, "theta": round(math.pi / 5, 10)},))
    ctx = EvalContext(None, datasets={"quantum_circuits": [{"circuit": spec.to_dict(), "backend_a": "classical", "backend_b": "classical"}]}, system=SystemDescriptor("s"))
    res = get_metric("quantum_fidelity_v1").run(ctx)
    assert res.value == pytest.approx(1.0, abs=1e-9)
    assert res.details["circuit_hash"] == spec.circuit_hash()
