"""Quantum symmetry index.

The circuit has the *form* of a variational quantum circuit (per-group RY
encoding, a CNOT ladder, and an RZ layer whose angles are a deterministic
function of the rate gaps) followed by a swap test against the equal-rate
reference. The angles are **not** the output of a variational optimisation.
On an ideal simulator the index is a smooth function of the supplied positive
rates. It does not see features that were not encoded into those rates.

Reported value
    Exact swap-test fidelity ``|⟨ψ_obs|ψ_ref⟩|² = 2 P(ancilla=0) − 1`` when a
    statevector is available. Shot estimates are returned beside it and are
    not silently used as the value.
"""
from __future__ import annotations

import math
from typing import Any, Optional, Sequence

from ..core.errors import ConfigError
from .backend import get_backend
from .types import CircuitSpec, stable_float

_MAX_GROUPS = 4
_TRUNCATION_NOTE = (
    f"At most {_MAX_GROUPS} groups are encoded, chosen by sorted label. "
    "Omitted groups are listed and are not merged into another group."
)


def binary_entropy(p: float) -> float:
    """Shannon entropy in bits of a Bernoulli(p)."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return float(-(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p)))


def _as_rate(value: Any) -> float:
    if value in (1, True, "1"):
        return 1.0
    if value in (0, False, "0"):
        return 0.0
    rate = float(value)
    if not 0.0 <= rate <= 1.0:
        raise ConfigError("predictions used as rates must lie in [0, 1]")
    return rate


def group_rates(rows: Sequence[dict], *, attribute: Optional[str] = None, min_support: int = 1) -> tuple[dict[str, float], list[str]]:
    """Positive rates keyed by group label. Small groups are listed, not dropped quietly from the note."""
    buckets: dict[str, list[float]] = {}
    for row in rows:
        if attribute is not None:
            sensitive = row.get("sensitive") or {}
            if attribute not in sensitive:
                raise ConfigError(f"row is missing sensitive attribute {attribute!r}")
            label = str(sensitive[attribute])
        else:
            if "group" not in row:
                raise ConfigError("row is missing 'group'")
            label = str(row["group"])
        pred = row["y_pred"] if "y_pred" in row else row["prediction"]
        buckets.setdefault(label, []).append(_as_rate(pred))
    kept: dict[str, float] = {}
    suppressed: list[str] = []
    for label, values in buckets.items():
        if len(values) < min_support:
            suppressed.append(label)
            continue
        kept[label] = sum(values) / len(values)
    return kept, suppressed


def attributes_of(rows: Sequence[dict]) -> list[str]:
    """Sensitive-attribute names, if rows carry a ``sensitive`` dict. Else ``[]`` (single ``group`` column)."""
    names: set[str] = set()
    for row in rows:
        sensitive = row.get("sensitive")
        if isinstance(sensitive, dict):
            names.update(str(k) for k in sensitive)
    return sorted(names)


def build_symmetry_circuit(rates: Sequence[float]) -> CircuitSpec:
    """Swap-test circuit for one attribute.

    Wire 0 is the ancilla. Wires ``1..n`` encode the observed rates.
    Wires ``n+1..2n`` encode the constant mean-rate reference.
    """
    if len(rates) < 2:
        raise ConfigError("symmetry circuit needs at least two group rates")
    if len(rates) > _MAX_GROUPS:
        raise ConfigError(f"encode at most {_MAX_GROUPS} rates; truncate before calling")
    clipped = [min(1.0, max(0.0, float(r))) for r in rates]
    mean_rate = sum(clipped) / len(clipped)
    n = len(clipped)
    obs = list(range(1, n + 1))
    ref = list(range(n + 1, 2 * n + 1))
    ops: list[dict] = []

    def encode(wires: list[int], values: Sequence[float]) -> None:
        for wire, rate in zip(wires, values):
            ops.append({"op": "ry", "wire": wire, "theta": stable_float(math.pi * rate)})
        for left, right in zip(wires, wires[1:]):
            ops.append({"op": "cnot", "control": left, "target": right})
        for wire, rate in zip(wires, values):
            ops.append({"op": "rz", "wire": wire, "theta": stable_float(math.pi * (rate - mean_rate))})

    encode(obs, clipped)
    encode(ref, [mean_rate] * n)
    ops.append({"op": "h", "wire": 0})
    for a, b in zip(obs, ref):
        ops.append({"op": "cswap", "control": 0, "a": a, "b": b})
    ops.append({"op": "h", "wire": 0})
    return CircuitSpec("swap_test_symmetry_v1", 1 + 2 * n, tuple(ops), ancilla=0)


def build_observed_circuit(rates: Sequence[float]) -> CircuitSpec:
    """Observed register only (no ancilla, no reference), for entanglement entropy."""
    if len(rates) < 2:
        raise ConfigError("observed circuit needs at least two group rates")
    clipped = [min(1.0, max(0.0, float(r))) for r in rates][:_MAX_GROUPS]
    mean_rate = sum(clipped) / len(clipped)
    n = len(clipped)
    ops: list[dict] = []
    for wire, rate in enumerate(clipped):
        ops.append({"op": "ry", "wire": wire, "theta": stable_float(math.pi * rate)})
    for wire in range(n - 1):
        ops.append({"op": "cnot", "control": wire, "target": wire + 1})
    for wire, rate in enumerate(clipped):
        ops.append({"op": "rz", "wire": wire, "theta": stable_float(math.pi * (rate - mean_rate))})
    return CircuitSpec("observed_register_v1", n, tuple(ops), ancilla=0)


def _ordered_rates(rates: dict[str, float]) -> tuple[list[str], list[float], list[str]]:
    """Stable label order. Truncation is explicit and recorded."""
    labels = sorted(rates)
    notes: list[str] = []
    if len(labels) > _MAX_GROUPS:
        omitted = labels[_MAX_GROUPS:]
        labels = labels[:_MAX_GROUPS]
        notes.append(_TRUNCATION_NOTE + " Omitted: " + ", ".join(omitted) + ".")
    return labels, [rates[label] for label in labels], notes


def swap_fidelity(run_probs: Sequence[float], ancilla: int = 0) -> float:
    """``2 P(ancilla=0) − 1``, clipped to [0, 1] only after the linear map."""
    p0 = sum(prob for index, prob in enumerate(run_probs) if ((index >> ancilla) & 1) == 0)
    return float(max(0.0, min(1.0, 2.0 * p0 - 1.0)))


def evaluate_rates(
    rates: dict[str, float],
    *,
    backend: str = "classical",
    shots: int = 0,
    seed: int = 0,
    noise: Optional[dict] = None,
    remote: Optional[str] = None,
) -> dict[str, Any]:
    """Run one attribute. Returns the score payload; does not seal Evidence."""
    labels, ordered, notes = _ordered_rates(rates)
    if len(ordered) < 2:
        return {
            "value": None,
            "untested": "fewer than 2 groups passed min_support; symmetry is not scored as perfect",
            "groups": labels,
            "notes": notes,
        }
    spec = build_symmetry_circuit(ordered)
    run = get_backend(backend).run(spec, shots=shots, seed=seed, noise=noise, remote=remote)
    value_probs = run.shot_probabilities if run.method == "remote_shots" else run.probabilities
    value = swap_fidelity(value_probs, spec.ancilla)
    shot_estimate = swap_fidelity(run.shot_probabilities, spec.ancilla) if run.shot_probabilities else None
    limitations = list(run.limitations) + notes + [
        "Research-grade. The ideal value is a function of the encoded positive rates only.",
        "VQC form with data-determined angles; not a trained VQE and not a global fairness optimum.",
        "Demographic parity is one of several mutually incompatible fairness criteria.",
        "Equal rates yield a value near 1 by construction of the reference state, including when every rate is 0.",
    ]
    if all(abs(r) <= 1e-15 for r in ordered):
        limitations.append("All encoded rates are 0. The index is vacuously high and is not evidence of fair outcomes.")
    return {
        "value": value,
        "shot_estimate": shot_estimate,
        "groups": labels,
        "rates": {label: stable_float(rates[label]) for label in labels},
        "circuit_hash": run.circuit_hash,
        "circuit": spec.to_dict(),
        "n_qubits": spec.n_qubits,
        "p_ancilla0": run.probability_bit_zero(spec.ancilla) if run.method != "remote_shots" else None,
        "backend": run.to_meta(),
        "limitations": limitations,
        "value_source": "remote_shots" if run.method == "remote_shots" else "statevector",
        "notes": notes,
    }


def evaluate_rows(
    rows: Sequence[dict],
    *,
    backend: str = "classical",
    shots: int = 0,
    seed: int = 0,
    noise: Optional[dict] = None,
    remote: Optional[str] = None,
    min_support: int = 1,
) -> dict[str, Any]:
    """Mean swap-test fidelity across sensitive attributes (or the single ``group`` column)."""
    if not rows:
        return {"value": None, "untested": "no rows", "per_attribute": {}, "limitations": ["Empty input is not tested, not passed."]}
    attrs = attributes_of(rows)
    per: dict[str, Any] = {}
    if attrs:
        targets = attrs
        for name in targets:
            rates, suppressed = group_rates(rows, attribute=name, min_support=min_support)
            payload = evaluate_rates(rates, backend=backend, shots=shots, seed=seed, noise=noise, remote=remote)
            payload["suppressed_small_groups"] = suppressed
            per[name] = payload
    else:
        rates, suppressed = group_rates(rows, min_support=min_support)
        payload = evaluate_rates(rates, backend=backend, shots=shots, seed=seed, noise=noise, remote=remote)
        payload["suppressed_small_groups"] = suppressed
        per["group"] = payload
    values = [item["value"] for item in per.values() if item.get("value") is not None]
    limitations: list[str] = []
    for item in per.values():
        for note in item.get("limitations") or []:
            if note not in limitations:
                limitations.append(note)
        if item.get("untested"):
            limitations.append(str(item["untested"]))
    untested = None if values else "no attribute had two groups above min_support"
    return {
        "value": (sum(values) / len(values)) if values else None,
        "untested": untested,
        "per_attribute": per,
        "limitations": limitations,
        "n_attributes_scored": len(values),
        "n_rows": len(rows),
    }
