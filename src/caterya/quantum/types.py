"""Circuit specifications and run records for the quantum extension.

Qubit 0 is the least-significant bit of every probability index published by
CATERYA, regardless of the backend's native ordering. Complex amplitudes are
never stored in Evidence; only JSON-safe floats and hashes are.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..core.canonical import digest


def stable_float(value: float, digits: int = 10) -> float:
    """Round a gate parameter so circuit hashes do not depend on binary noise."""
    return round(float(value), digits)


@dataclass(frozen=True)
class CircuitSpec:
    """Canonical, hashable description of a small circuit.

    ``operations`` is a tuple of JSON-ready dicts. Supported ops:
    ``h``, ``x``, ``ry``, ``rz``, ``cnot``, ``cswap``.
    """

    name: str
    n_qubits: int
    operations: tuple[dict[str, Any], ...]
    ancilla: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "n_qubits": self.n_qubits,
            "ancilla": self.ancilla,
            "operations": [dict(op) for op in self.operations],
        }

    def circuit_hash(self, algo: str = "sha256") -> str:
        """Content hash of the canonical spec. Parameters are part of the hash."""
        return digest(self.to_dict(), algo)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CircuitSpec":
        ops = tuple(dict(op) for op in raw.get("operations", ()))
        return cls(str(raw.get("name", "circuit")), int(raw["n_qubits"]), ops, int(raw.get("ancilla", 0)))


@dataclass
class QuantumRun:
    """One backend execution.

    ``probabilities`` uses LSB-0 indexing. ``fidelity_from_ancilla`` is set by
    the caller when the circuit is a swap test; the backend does not assume that.
    """

    probabilities: list[float]
    backend: str
    backend_version: str
    method: str
    shots: int
    circuit_hash: str
    noise_model: Optional[dict[str, Any]] = None
    noise_applied_to: Optional[str] = None
    shot_probabilities: Optional[list[float]] = None
    state_real: Optional[list[float]] = None
    state_imag: Optional[list[float]] = None
    limitations: list[str] = field(default_factory=list)
    n_qubits: int = 0

    def probability_bit_zero(self, qubit: int) -> float:
        """Probability that ``qubit`` measures 0. Index bit ``qubit`` is that qubit."""
        if not self.probabilities:
            return 0.0
        total = 0.0
        for index, prob in enumerate(self.probabilities):
            if ((index >> qubit) & 1) == 0:
                total += prob
        return float(total)

    def to_meta(self) -> dict[str, Any]:
        """JSON-safe metadata suitable for an Evidence ``context``."""
        return {
            "backend": self.backend,
            "backend_version": self.backend_version,
            "method": self.method,
            "shots": self.shots,
            "circuit_hash": self.circuit_hash,
            "noise_model": self.noise_model,
            "noise_applied_to": self.noise_applied_to,
            "n_qubits": self.n_qubits,
            "limitations": list(self.limitations),
        }
