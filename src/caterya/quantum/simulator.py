"""Stdlib statevector simulator.

Qubit 0 is the least-significant bit. The simulator is exact (no shot noise)
unless the caller samples. It is the default backend so quantum metrics stay
reproducible without PennyLane or Qiskit.
"""
from __future__ import annotations

import math
import random
from typing import Optional, Sequence

from ..core.errors import ConfigError
from .types import CircuitSpec, QuantumRun

_H = 1.0 / math.sqrt(2)


def _initial(n: int) -> list[complex]:
    state = [0j] * (1 << n)
    state[0] = 1.0 + 0.0j
    return state


def _apply_1q(state: Sequence[complex], n: int, qubit: int, mat: tuple[tuple[complex, complex], tuple[complex, complex]]) -> list[complex]:
    a00, a01 = mat[0]
    a10, a11 = mat[1]
    step = 1 << qubit
    out = [0j] * (1 << n)
    span = step << 1
    for base in range(0, 1 << n, span):
        for offset in range(step):
            i0 = base + offset
            i1 = i0 + step
            s0, s1 = state[i0], state[i1]
            out[i0] = a00 * s0 + a01 * s1
            out[i1] = a10 * s0 + a11 * s1
    return out


def _ry(theta: float) -> tuple[tuple[complex, complex], tuple[complex, complex]]:
    c, s = math.cos(theta / 2.0), math.sin(theta / 2.0)
    return ((c, -s), (s, c))


def _rz(theta: float) -> tuple[tuple[complex, complex], tuple[complex, complex]]:
    import cmath

    return ((cmath.exp(-1j * theta / 2.0), 0j), (0j, cmath.exp(1j * theta / 2.0)))


def _apply_cnot(state: Sequence[complex], n: int, control: int, target: int) -> list[complex]:
    if control == target:
        raise ConfigError("cnot control and target must differ")
    out = list(state)
    cs, ts = 1 << control, 1 << target
    for index in range(1 << n):
        if (index & cs) and not (index & ts):
            flipped = index | ts
            out[index] = state[flipped]
            out[flipped] = state[index]
    return out


def _apply_cswap(state: Sequence[complex], n: int, control: int, a: int, b: int) -> list[complex]:
    if len({control, a, b}) < 3:
        raise ConfigError("cswap wires must be distinct")
    out = list(state)
    cs, aa, bb = 1 << control, 1 << a, 1 << b
    for index in range(1 << n):
        if (index & cs) and (index & aa) and not (index & bb):
            flipped = (index ^ aa) ^ bb
            out[index] = state[flipped]
            out[flipped] = state[index]
    return out


def evolve(spec: CircuitSpec) -> list[complex]:
    """Apply ``spec`` to ``|0...0>`` and return the statevector (LSB-0)."""
    if spec.n_qubits < 1 or spec.n_qubits > 12:
        raise ConfigError("classical simulator supports 1 to 12 qubits")
    state = _initial(spec.n_qubits)
    for op in spec.operations:
        name = op["op"]
        if name == "h":
            state = _apply_1q(state, spec.n_qubits, int(op["wire"]), ((_H, _H), (_H, -_H)))
        elif name == "x":
            state = _apply_1q(state, spec.n_qubits, int(op["wire"]), ((0j, 1 + 0j), (1 + 0j, 0j)))
        elif name == "ry":
            state = _apply_1q(state, spec.n_qubits, int(op["wire"]), _ry(float(op["theta"])))
        elif name == "rz":
            state = _apply_1q(state, spec.n_qubits, int(op["wire"]), _rz(float(op["theta"])))
        elif name == "cnot":
            state = _apply_cnot(state, spec.n_qubits, int(op["control"]), int(op["target"]))
        elif name == "cswap":
            state = _apply_cswap(state, spec.n_qubits, int(op["control"]), int(op["a"]), int(op["b"]))
        else:
            raise ConfigError(f"unsupported op {name!r}")
    return state


def probabilities_of(state: Sequence[complex]) -> list[float]:
    return [float(abs(amp) ** 2) for amp in state]


def sample_probabilities(probs: Sequence[float], shots: int, seed: int, *, readout_p: float = 0.0, readout_qubit: int = 0) -> list[float]:
    """Seeded shot sample. Optional independent bit-flip on one qubit (readout)."""
    if shots < 1:
        raise ConfigError("shots must be >= 1")
    cdf: list[float] = []
    acc = 0.0
    for prob in probs:
        acc += prob
        cdf.append(acc)
    if acc <= 0:
        raise ConfigError("cannot sample a zero distribution")
    rng = random.Random(seed)
    counts = [0] * len(probs)
    last = len(cdf) - 1
    for _ in range(shots):
        draw = rng.random() * acc
        lo, hi = 0, last
        while lo < hi:
            mid = (lo + hi) // 2
            if draw <= cdf[mid]:
                hi = mid
            else:
                lo = mid + 1
        index = lo
        if readout_p > 0 and rng.random() < readout_p:
            index ^= 1 << readout_qubit
        counts[index] += 1
    return [c / shots for c in counts]


def simulate(
    spec: CircuitSpec,
    *,
    shots: int = 0,
    seed: int = 0,
    noise: Optional[dict] = None,
    backend_name: str = "classical",
    backend_version: str = "caterya-statevector/1",
    method: str = "statevector",
) -> QuantumRun:
    """Exact statevector, plus an optional seeded shot estimate.

    Readout noise is applied only to the shot estimate. Requesting a non-zero
    readout model with ``shots == 0`` is an error: the exact vector must not be
    labelled as noisy.
    """
    readout_p = 0.0
    recorded: Optional[dict] = None
    limitations = [
        "Ideal statevector (or seeded samples of it). This is not a device execution.",
        "No claim is made that the circuit finds fairness structure beyond its published encoding.",
    ]
    if noise:
        kind = noise.get("type")
        if kind in (None, "none"):
            recorded = None
        elif kind == "readout_flip":
            readout_p = float(noise.get("p", 0.0))
            if not 0.0 <= readout_p <= 1.0:
                raise ConfigError("readout_flip p must be in [0, 1]")
            if readout_p > 0 and shots <= 0:
                raise ConfigError("readout noise requires shots > 0; refusing to report a noiseless statevector as noisy")
            recorded = {"type": "readout_flip", "p": readout_p, "qubit": int(noise.get("qubit", spec.ancilla))}
            if readout_p == 0:
                recorded = None
        else:
            raise ConfigError(f"noise model {kind!r} is not implemented; refusing to ignore it")
    state = evolve(spec)
    probs = probabilities_of(state)
    shot_probs = None
    applied = None
    if shots > 0:
        qubit = int((recorded or {}).get("qubit", spec.ancilla))
        shot_probs = sample_probabilities(probs, shots, seed, readout_p=readout_p if recorded else 0.0, readout_qubit=qubit)
        if recorded:
            applied = "shot_estimate"
            limitations.append("Readout flip was applied only to the shot estimate, not to the statevector probabilities.")
        limitations.append("Shot estimates depend on seed and shot count; the statevector probabilities are the reproducible value.")
    return QuantumRun(
        probabilities=probs,
        backend=backend_name,
        backend_version=backend_version,
        method=method,
        shots=shots,
        circuit_hash=spec.circuit_hash(),
        noise_model=recorded,
        noise_applied_to=applied,
        shot_probabilities=shot_probs,
        state_real=[float(amp.real) for amp in state],
        state_imag=[float(amp.imag) for amp in state],
        limitations=limitations,
        n_qubits=spec.n_qubits,
    )
