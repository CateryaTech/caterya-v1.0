"""Bipartite entanglement entropy of a pure statevector (LSB-0).

Needs NumPy for the reduced-density eigenvalues. The quantity is informational:
it is not a trustworthiness score, and a larger value is not "better".
"""
from __future__ import annotations

from typing import Sequence

from ..core.errors import CapabilityUnavailable
from .backend import get_backend
from .symmetry import _ordered_rates, build_observed_circuit


def von_neumann_bits(state_real: Sequence[float], state_imag: Sequence[float], n: int, keep: Sequence[int]) -> float:
    """``S(Tr_{not keep} |psi><psi|)`` in bits."""
    try:
        import numpy as np
    except Exception as exc:  # pragma: no cover
        raise CapabilityUnavailable("pip install numpy (caterya[quantum])") from exc
    keep_set = set(keep)
    dim_a = 1 << len(keep_set)
    dim_b = 1 << (n - len(keep_set))
    psi = np.zeros((dim_a, dim_b), dtype=complex)
    for index, (real, imag) in enumerate(zip(state_real, state_imag)):
        ia = ib = 0
        ba = bb = 0
        for qubit in range(n):
            bit = (index >> qubit) & 1
            if qubit in keep_set:
                ia |= bit << ba
                ba += 1
            else:
                ib |= bit << bb
                bb += 1
        psi[ia, ib] += real + 1j * imag
    norm = np.linalg.norm(psi)
    if norm == 0:
        return 0.0
    psi /= norm
    rho = psi @ psi.conj().T
    ev = np.clip(np.linalg.eigvalsh(rho).real, 0.0, 1.0)
    ev = ev[ev > 1e-12]
    return float(-(ev * np.log2(ev)).sum())


def half_partition(n: int) -> list[int]:
    """Keep the lower half of the wires. One qubit has an empty complement, so entropy is undefined."""
    if n < 2:
        return []
    return list(range(n // 2))


def entanglement_from_rates(rates: dict[str, float], *, backend: str = "classical") -> dict:
    """Entropy of the observed register prepared by :func:`build_observed_circuit`.

    Returns ``value=None`` when the register cannot be bipartitioned or the
    backend did not return a statevector (remote shots).
    """
    labels, ordered, notes = _ordered_rates(rates)
    if len(ordered) < 2:
        return {"value": None, "untested": "fewer than 2 groups; entanglement entropy is not imputed", "notes": notes}
    spec = build_observed_circuit(ordered)
    run = get_backend(backend).run(spec, shots=0)
    keep = half_partition(spec.n_qubits)
    limitations = list(run.limitations) + notes + [
        "Informational quantity in bits, not a score. Higher is not more trustworthy.",
        "Partition is the lower half of the observed register wires, a convention, not a physical cut of a device.",
        "Research-grade. Phases come from the published RZ encoding; another encoding would change the number.",
    ]
    if not keep:
        return {
            "value": None,
            "untested": "register has fewer than 2 qubits; bipartite entropy is undefined and is not reported as 0",
            "circuit_hash": run.circuit_hash,
            "backend": run.to_meta(),
            "limitations": limitations,
            "groups": labels,
        }
    if run.state_real is None or run.state_imag is None:
        return {
            "value": None,
            "untested": "backend did not return a statevector; entropy is not estimated from Z-basis shots",
            "circuit_hash": run.circuit_hash,
            "backend": run.to_meta(),
            "limitations": limitations,
            "groups": labels,
        }
    value = von_neumann_bits(run.state_real, run.state_imag, spec.n_qubits, keep)
    return {
        "value": value,
        "circuit_hash": run.circuit_hash,
        "backend": run.to_meta(),
        "limitations": limitations,
        "groups": labels,
        "partition_keep": keep,
        "n_qubits": spec.n_qubits,
    }
