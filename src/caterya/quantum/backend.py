"""Quantum backends. Classical statevector is the default and has no extra dependency.

PennyLane and Qiskit are optional. If a requested backend is missing, the call
fails. Results are not silently replaced with another backend.

Published probabilities always use qubit 0 as the least-significant bit.
PennyLane's native statevector (wire 0 = most-significant bit) is permuted
before it leaves this module.
"""
from __future__ import annotations

import importlib.util
import math
import os
from abc import ABC, abstractmethod
from typing import Optional, Sequence

from ..core.errors import CapabilityUnavailable, ConfigError
from .simulator import simulate
from .types import CircuitSpec, QuantumRun


def fidelity(p: Sequence[float], q: Sequence[float]) -> float:
    """Classical fidelity (Bhattacharyya coefficient squared).

    Equals ``|<psi_p|psi_q>|^2`` when ``|psi> = sum_i sqrt(p_i)|i>`` and the
    amplitudes are real and non-negative. Relative phases are not observed.
    """
    sp, sq = sum(p), sum(q)
    if sp <= 0 or sq <= 0:
        raise ConfigError("fidelity requires positive probability mass on both distributions")
    return sum(math.sqrt((a / sp) * (b / sq)) for a, b in zip(p, q)) ** 2


def von_neumann_entropy_of_reduced(state: Sequence[complex], dim_a: int, dim_b: int) -> float:
    """``E(rho) = S(Tr_B rho_AB)`` in bits for a pure bipartite state (needs numpy)."""
    try:
        import numpy as np
    except Exception as exc:  # pragma: no cover
        raise CapabilityUnavailable("pip install numpy (caterya[quantum])") from exc
    psi = np.asarray(list(state), dtype=complex).reshape(dim_a, dim_b)
    psi = psi / np.linalg.norm(psi)
    ev = np.linalg.eigvalsh(psi @ psi.conj().T)
    ev = ev[ev > 1e-12]
    return float(-(ev * np.log2(ev)).sum())


def _has(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def pennylane_state_to_lsb(state: Sequence[complex], n: int) -> list[complex]:
    """Permute PennyLane wire-0-MSB amplitudes into LSB-0 order."""
    out = [0j] * (1 << n)
    for index, amp in enumerate(state):
        mapped = 0
        for qubit in range(n):
            bit = (index >> (n - 1 - qubit)) & 1
            mapped |= bit << qubit
        out[mapped] = complex(amp)
    return out


def _probs(state: Sequence[complex]) -> list[float]:
    return [float(abs(amp) ** 2) for amp in state]


class Backend(ABC):
    """Executable quantum backend. ``distribution`` stays for older callers."""

    name = "backend"
    bit_order = "lsb0"

    @abstractmethod
    def available(self) -> bool:
        """Return True when this backend's imports succeed."""

    def version(self) -> str:
        """Backend implementation version string recorded in Evidence."""
        return "unknown"

    def run(
        self,
        spec: CircuitSpec,
        *,
        shots: int = 0,
        seed: int = 0,
        noise: Optional[dict] = None,
        remote: Optional[str] = None,
    ) -> QuantumRun:
        """Execute ``spec``. Override in concrete backends."""
        raise CapabilityUnavailable(f"{self.name}: not implemented")

    def distribution(self, circuit_spec: dict) -> list[float]:
        """Backward-compatible probability vector.

        A dict that only carries ``probabilities`` is returned as-is for the
        classical backend. A dict with ``operations`` is executed.
        """
        if "operations" not in circuit_spec:
            if self.name == "classical" and "probabilities" in circuit_spec:
                return list(circuit_spec["probabilities"])
            raise CapabilityUnavailable(f"{self.name}: circuit has no operations")
        return self.run(CircuitSpec.from_dict(circuit_spec), shots=int(circuit_spec.get("shots", 0)), seed=int(circuit_spec.get("seed", 0)), noise=circuit_spec.get("noise")).probabilities


class ClassicalBackend(Backend):
    """Default backend: the stdlib statevector in :mod:`caterya.quantum.simulator`."""

    name = "classical"

    def available(self) -> bool:
        return True

    def version(self) -> str:
        return "caterya-statevector/1"

    def run(self, spec: CircuitSpec, *, shots: int = 0, seed: int = 0, noise: Optional[dict] = None, remote: Optional[str] = None) -> QuantumRun:
        if remote:
            raise CapabilityUnavailable("classical backend has no remote device; refusing to pretend otherwise")
        return simulate(spec, shots=shots, seed=seed, noise=noise, backend_name=self.name, backend_version=self.version())


class PennyLaneBackend(Backend):
    """PennyLane ``default.qubit`` statevector. Primary optional VQC backend."""

    name = "pennylane"

    def available(self) -> bool:
        return _has("pennylane")

    def version(self) -> str:
        if not self.available():
            return "not-installed"
        import pennylane as qml

        return f"pennylane/{qml.__version__}+default.qubit"

    def run(self, spec: CircuitSpec, *, shots: int = 0, seed: int = 0, noise: Optional[dict] = None, remote: Optional[str] = None) -> QuantumRun:
        if remote:
            raise CapabilityUnavailable("PennyLane remote hardware is not wired; pass backend='qiskit' with remote=")
        if not self.available():
            raise CapabilityUnavailable("PennyLane is not installed. pip install 'caterya[quantum-backends]'. No fallback was applied.")
        import pennylane as qml

        dev = qml.device("default.qubit", wires=spec.n_qubits)

        @qml.qnode(dev)
        def circuit():
            for op in spec.operations:
                kind = op["op"]
                if kind == "h":
                    qml.Hadamard(wires=int(op["wire"]))
                elif kind == "x":
                    qml.PauliX(wires=int(op["wire"]))
                elif kind == "ry":
                    qml.RY(float(op["theta"]), wires=int(op["wire"]))
                elif kind == "rz":
                    qml.RZ(float(op["theta"]), wires=int(op["wire"]))
                elif kind == "cnot":
                    qml.CNOT(wires=[int(op["control"]), int(op["target"])])
                elif kind == "cswap":
                    qml.CSWAP(wires=[int(op["control"]), int(op["a"]), int(op["b"])])
                else:
                    raise ConfigError(f"unsupported op {kind!r}")
            return qml.state()

        native = pennylane_state_to_lsb(list(circuit()), spec.n_qubits)
        probs = _probs(native)
        from .simulator import sample_probabilities

        recorded = None
        applied = None
        limitations = [
            "PennyLane default.qubit is a noiseless statevector simulator, not a quantum processor.",
            "Wire order was converted to LSB-0 before probabilities were published.",
            "The circuit is a fixed data encoding (VQC *form*). It is not a trained variational optimum.",
        ]
        shot_probs = None
        if noise and noise.get("type") == "readout_flip" and float(noise.get("p", 0)) > 0:
            if shots <= 0:
                raise ConfigError("readout noise requires shots > 0; refusing to report a noiseless PennyLane state as noisy")
            recorded = {"type": "readout_flip", "p": float(noise["p"]), "qubit": int(noise.get("qubit", spec.ancilla))}
            applied = "shot_estimate"
            limitations.append("Readout flip was applied only while sampling the PennyLane distribution.")
        elif noise and noise.get("type") not in (None, "none", "readout_flip"):
            raise ConfigError(f"noise model {noise.get('type')!r} is not implemented on the PennyLane path")
        if shots > 0:
            p_noise = float(recorded["p"]) if recorded else 0.0
            qubit = int(recorded["qubit"]) if recorded else spec.ancilla
            shot_probs = sample_probabilities(probs, shots, seed, readout_p=p_noise, readout_qubit=qubit)
            limitations.append("Shots are seeded samples of the PennyLane statevector, not qml.sample on a shot device.")
        return QuantumRun(
            probabilities=probs,
            backend=self.name,
            backend_version=self.version(),
            method="statevector",
            shots=shots,
            circuit_hash=spec.circuit_hash(),
            noise_model=recorded,
            noise_applied_to=applied,
            shot_probabilities=shot_probs,
            state_real=[float(amp.real) for amp in native],
            state_imag=[float(amp.imag) for amp in native],
            limitations=limitations,
            n_qubits=spec.n_qubits,
        )


class QiskitBackend(Backend):
    """Qiskit Aer / statevector, plus an explicit remote path that never falls back."""

    name = "qiskit"

    def available(self) -> bool:
        return _has("qiskit")

    def version(self) -> str:
        if not self.available():
            return "not-installed"
        import qiskit

        aer = "no-aer"
        if _has("qiskit_aer"):
            import qiskit_aer

            aer = f"aer/{qiskit_aer.__version__}"
        return f"qiskit/{qiskit.__version__}+{aer}"

    def _circuit(self, spec: CircuitSpec, measure: bool = False):
        from qiskit import QuantumCircuit

        qc = QuantumCircuit(spec.n_qubits, spec.n_qubits if measure else 0)
        for op in spec.operations:
            kind = op["op"]
            if kind == "h":
                qc.h(int(op["wire"]))
            elif kind == "x":
                qc.x(int(op["wire"]))
            elif kind == "ry":
                qc.ry(float(op["theta"]), int(op["wire"]))
            elif kind == "rz":
                qc.rz(float(op["theta"]), int(op["wire"]))
            elif kind == "cnot":
                qc.cx(int(op["control"]), int(op["target"]))
            elif kind == "cswap":
                qc.cswap(int(op["control"]), int(op["a"]), int(op["b"]))
            else:
                raise ConfigError(f"unsupported op {kind!r}")
        if measure:
            qc.measure(range(spec.n_qubits), range(spec.n_qubits))
        return qc

    def _parse_noise(self, spec: CircuitSpec, shots: int, noise: Optional[dict]) -> tuple[Optional[dict], Optional[str], list[str]]:
        limitations = [
            "Local Qiskit execution uses Statevector (exact) unless shots are requested.",
            "This is not evidence of execution on a quantum processor.",
            "The circuit is a fixed data encoding (VQC *form*). It is not a trained variational optimum.",
        ]
        if not noise or noise.get("type") in (None, "none"):
            return None, None, limitations
        if noise.get("type") != "readout_flip":
            raise ConfigError(f"noise model {noise.get('type')!r} is not implemented on the Qiskit path")
        p = float(noise.get("p", 0.0))
        if p == 0:
            return None, None, limitations
        if shots <= 0:
            raise ConfigError("readout noise requires shots > 0; refusing to report a noiseless Qiskit state as noisy")
        limitations.append("Readout flip is applied in CATERYA's sampler of the Qiskit distribution, not as an Aer noise model.")
        return {"type": "readout_flip", "p": p, "qubit": int(noise.get("qubit", spec.ancilla))}, "shot_estimate", limitations

    def _remote(self, spec: CircuitSpec, shots: int, backend_name: str) -> QuantumRun:
        token = os.environ.get("QISKIT_IBM_TOKEN") or os.environ.get("IBM_QUANTUM_TOKEN")
        if not token:
            raise CapabilityUnavailable(
                "Qiskit remote backend was requested but QISKIT_IBM_TOKEN/IBM_QUANTUM_TOKEN is unset. "
                "No local simulator result is substituted."
            )
        if shots <= 0:
            raise ConfigError("remote execution requires shots > 0")
        try:
            from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
            from qiskit_ibm_runtime import QiskitRuntimeService
            from qiskit_ibm_runtime import SamplerV2 as Sampler
        except Exception as exc:
            raise CapabilityUnavailable(f"qiskit-ibm-runtime is not usable ({exc}). No local fallback was applied.") from exc
        try:
            service = QiskitRuntimeService(channel="ibm_quantum_platform", token=token)
            backend = service.backend(backend_name)
            qc = self._circuit(spec, measure=True)
            pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
            isa = pm.run(qc)
            job = Sampler(mode=backend).run([isa], shots=shots)
            pub = job.result()[0]
            counts = pub.data.meas.get_counts()
        except Exception as exc:
            raise CapabilityUnavailable(f"Qiskit remote run failed ({type(exc).__name__}: {exc}). No local fallback was applied.") from exc
        probs = [0.0] * (1 << spec.n_qubits)
        total = sum(counts.values()) or 1
        for bitstr, count in counts.items():
            probs[int(bitstr, 2)] = count / total
        return QuantumRun(
            probabilities=probs,
            backend=self.name,
            backend_version=self.version() + f"+remote:{backend_name}",
            method="remote_shots",
            shots=shots,
            circuit_hash=spec.circuit_hash(),
            noise_model={"type": "device", "backend": backend_name, "note": "device noise is whatever the hardware did; not a CATERYA noise model"},
            noise_applied_to="probabilities",
            shot_probabilities=probs,
            limitations=[
                "Remote shots only. The value is a finite-sample estimate, not an exact statevector.",
                "Hardware noise, transpilation and measurement error are not separated.",
                "Not a certificate of fairness or of quantum advantage.",
            ],
            n_qubits=spec.n_qubits,
        )

    def run(self, spec: CircuitSpec, *, shots: int = 0, seed: int = 0, noise: Optional[dict] = None, remote: Optional[str] = None) -> QuantumRun:
        if not self.available():
            raise CapabilityUnavailable("Qiskit is not installed. pip install 'caterya[quantum-backends]'. No fallback was applied.")
        if remote:
            return self._remote(spec, shots, remote)
        from qiskit.quantum_info import Statevector

        recorded, applied, limitations = self._parse_noise(spec, shots, noise)
        qc = self._circuit(spec, measure=False)
        vector = Statevector.from_instruction(qc)
        probs = [float(abs(amp) ** 2) for amp in vector.data]
        shot_probs = None
        if shots > 0:
            from .simulator import sample_probabilities

            p_noise = float(recorded["p"]) if recorded else 0.0
            qubit = int(recorded["qubit"]) if recorded else spec.ancilla
            shot_probs = sample_probabilities(probs, shots, seed, readout_p=p_noise, readout_qubit=qubit)
            limitations.append(
                "Shots are seeded samples of the Qiskit Statevector in-process. "
                "qiskit-aer is detected but not required for this estimate, so Aer shot-noise is not what was measured."
            )
        return QuantumRun(
            probabilities=probs,
            backend=self.name,
            backend_version=self.version(),
            method="statevector",
            shots=shots,
            circuit_hash=spec.circuit_hash(),
            noise_model=recorded,
            noise_applied_to=applied,
            shot_probabilities=shot_probs,
            state_real=[float(complex(amp).real) for amp in vector.data],
            state_imag=[float(complex(amp).imag) for amp in vector.data],
            limitations=limitations,
            n_qubits=spec.n_qubits,
        )


def get_backend(name: str) -> Backend:
    """Resolve ``classical`` / ``simulator`` / ``pennylane`` / ``qiskit``.

    Missing optional backends raise :class:`CapabilityUnavailable` instead of
    substituting the classical simulator.
    """
    key = {"simulator": "classical", "default": "classical", "numpy": "classical", "default.qubit": "pennylane"}.get(name, name)
    try:
        backend = BACKENDS[key]
    except KeyError as exc:
        raise ConfigError(f"unknown quantum backend {name!r}. Known: {', '.join(BACKENDS)}") from exc
    if not backend.available():
        raise CapabilityUnavailable(f"quantum backend {key!r} is not installed. No fallback was applied.")
    return backend


BACKENDS = {b.name: b for b in (ClassicalBackend(), PennyLaneBackend(), QiskitBackend())}
