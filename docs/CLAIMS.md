# Claims register — "Verify it" applied to CATERYA

Every public claim, its status, and the command that checks it. Claims without a check are **not** made.

| Claim | Status | How to check |
|---|---|---|
| Evidence/CAR records are tamper-evident (hash, chain, signature) | verified by tests | `pytest tests/test_assurance.py::test_evidence_is_tamper_evident` |
| Merkle inclusion proofs verify for all tree sizes 1–11 | verified by tests | `pytest tests/test_core.py -k merkle` |
| A third party can verify and reproduce a bundle without trusting the evaluator | verified by tests (deterministic adapters) | `caterya evidence verify bundle.json` · `caterya evidence reproduce bundle.json` |
| Governance decision is separate from measurement; overrides need a reason | verified by tests | `pytest -k governance` |
| Each injected flaw lowers its metric monotonically (mock models) | verified, **sanity only** | `python benchmarks/validate.py` |
| Metrics add information beyond simple baselines | **partially**: yes for perturbation/symmetry/fairness/context on mocks; **no gain** for leakage, reliability and chaos on mocks | `python benchmarks/validate.py` (see `docs/VALIDATION_PROTOCOL.md`) |
| Metrics predict real-world harmful behaviour | **unproven** | requires protocol H1 on real systems |
| Lyapunov-style metric certifies stability | **not claimed** — empirical divergence rate only | `docs/METRICS.md` |
| COS is a trust score | **not claimed** — derived index; ignores safety/security domains | `docs/METRICS.md`, `metrics/cos.py` |
| Python hook overhead | measured per machine, no number asserted | `python benchmarks/latency.py` |
| Quantum symmetry index certifies fairness or runs a trained VQE | **not claimed** — data-encoded swap test; see `docs/QUANTUM.md` | `pytest tests/test_quantum.py` |
| PennyLane and Qiskit are required | **not claimed** — classical statevector is the default; a missing backend is an error, not a silent substitute | `caterya quantum backends` |
| Guardrail pass means safe to deploy | **not claimed** — recommendation plus Evidence; `finalize()` still needs a named decider | `pytest tests/test_guardrails.py` |
| Ethics swarm is a human panel | **not claimed** — deterministic votes; missing inputs abstain | `pytest tests/test_guardrails.py::test_swarm_abstains_instead_of_a_default_score` |
| Regulatory mapping is legal compliance or an Indonesia 2026 certification | **not claimed** — thematic technical map; clause labels must be checked against official texts | `pytest tests/test_extensions.py::test_indonesia_2026_pack_is_thematic_and_sealed` |
| Golden Triangle or the fairness surface is a physical certificate | **not claimed** — optional composite / visualisation of published formulas | `docs/PILLARS.md` |
| Zero-knowledge proofs | **not claimed** — salted commitments / selective disclosure only | `provenance/zk.py` |
| Mandatory in every frontier-lab backend | **not claimed** — long-term outcome of adoption, regulation and reputation | `docs/ROADMAP.md` |
