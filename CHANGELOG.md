# Changelog

## 1.0.0-alpha.2 — 2026-10

Research extensions ported from Framework 3.0 without turning them into certificates.

- Quantum: classical statevector default; PennyLane `default.qubit` and Qiskit Statevector/remote (no silent fallback). `quantum_symmetry_index_v1` (data-encoded swap test, VQC form, not a trained VQE), fidelity and entanglement entropy record circuit hash, backend version, shots, noise model, and limitations.
- Guardrails: `CATERYAGuardrail`, `EthicsSwarm`, LangGraph/CrewAI adapters that keep the output. Every pass/fail/remediate/untested is signed Evidence. Canary window below `guardrail_min_score` requests `incident_replay`.
- Pillar labels on profiles; Golden Triangle remains an optional view inside the COS object.
- Optional fairness-parity surface (`fairness_energy_map_v1`, Plotly via `caterya[viz]`). The hashed artifact is the grid.
- Regulatory map gains `ID_AI_ETHICS_2026` (thematic labels, not statute numbers) and `seal_mapping`.
- Extras: `quantum`, `quantum-backends`, `viz`.

## 1.0.0-alpha.1 — 2026-10
Initial release of **CATERYA AI ASSURANCE INFRASTRUCTURE** (successor of Framework 3.0), implementing Architecture v1.0, the repositioning strategy and the whitepaper roadmap phase 1 foundations.
- Evidence schema `caterya.evidence/v1`, CAR `caterya.car/v1`, trace `caterya.trace/v1`; JSON Schemas.
- Provenance: canonical hashing (SHA-256 / SHA3-256), Ed25519 / HMAC-dev signing, hash chain, Merkle transparency log with signed tree heads, DSSE/in-toto attestation, salted commitments + selective disclosure, anchor interfaces.
- 27 metrics across 11 domains incl. Golden Triangle, Lyapunov-style stability, fairness, robustness, safety, security, privacy, reliability, agentic, quantum helpers; derived COS index.
- 7 profiles; runner pipeline; CI-aware findings; risk model; levels 0–4; governance decision with guard-rails; regression; policy gate.
- Continuous monitoring (PSI/KS/CUSUM), tiered re-evaluation, incident loop.
- Regulatory mapping (EU AI Act, NIST AI RMF, ISO/IEC 42001, OECD, Indonesia) — indicative.
- Python SDK (`AssuranceEngine`, `AgentGuard`, `ProofToken`), CLI, FastAPI service, white-background dashboard.
- Adapters: OpenAI-compatible, Anthropic, Hugging Face, callable, mock-with-injectable-flaws.
- Validation harness, latency benchmark, 58 tests.
