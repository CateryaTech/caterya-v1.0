# Quantum extension

Research-grade. The default backend is a classical statevector in `caterya.quantum.simulator`. PennyLane (`default.qubit`) and Qiskit (Statevector, optional Aer sampling, optional IBM Runtime) are extras. A missing backend raises `CapabilityUnavailable`. Nothing is silently replaced with another backend.

Install:

```bash
pip install -e ".[quantum]"              # numpy, used by entanglement eigenvalues
pip install -e ".[quantum-backends]"     # pennylane, qiskit, qiskit-aer
```

## What `quantum_symmetry_index_v1` is

For each sensitive attribute, positive rates are clipped to `[0, 1]` and encoded as:

1. `RY(π · rate)` on one qubit per group (at most four groups, by sorted label; omitted groups are listed).
2. A CNOT ladder.
3. `RZ(π · (rate − mean))`.

That state is swap-tested against the same circuit run on the constant mean rate. The reported value is the statevector fidelity `2 P(ancilla=0) − 1`. Shot estimates, when requested, are stored beside it and do not replace it.

This circuit has a variational *form*. The angles are a deterministic function of the rates. They are **not** the result of a trained VQE, and the number does not see anything that was not put into the rates. Equal rates, including the all-zero vector, score near 1 by construction. Fewer than two groups above `min_support` is `NOT TESTED`, not a perfect score.

Every run records `circuit_hash`, backend name and version, shot count, noise model, and limitations on the Evidence context. The only implemented noise model is `readout_flip`, and only on the shot estimate. `shots=0` plus a non-zero noise model is an error.

Remote Qiskit (`--remote BACKEND` plus `QISKIT_IBM_TOKEN`) does not fall back to the simulator if the token, package, or job fails.

## Fidelity and entanglement

- `quantum_fidelity_v1` is the Bhattacharyya fidelity of computational-basis distributions. Relative phase is not observed. Supplied pairs (`quantum_states`) or an executed pair of backends (`quantum_circuits`) are both accepted.
- `entanglement_entropy_v1` is the von Neumann entropy, in bits, of a reduced pure state. Supplied states win over the observed-register preparation. The half-wire cut is a convention. Higher is not better. Remote shots do not produce this quantity.

## Profile

`CATERYA-QUANTUM` runs the classical basic metrics plus the three quantum metrics. The quantum metrics are not required, so a missing dataset stays an explicit gap instead of failing coverage. Thresholds in the profile are defaults, not a standard.

```bash
caterya quantum backends
caterya quantum symmetry --data rows.json --backend classical --shots 0 --out evidence.json
caterya quantum fidelity --data circuit.json --backend classical --backend-b pennylane
caterya quantum entanglement --data rows.json --backend classical
```

`rows.json` is either a list of `{y_pred, group}` / `{y_pred, sensitive}` or `{predictions, sensitive_attributes}`. See `examples/quantum_symmetry.py`.
