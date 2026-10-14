# CATERYA AI ASSURANCE INFRASTRUCTURE

**Measure! Verify! Assure!**
Open, vendor-neutral infrastructure that evaluates AI systems, produces **verifiable evidence** about their behaviour and risk, preserves **tamper-evident provenance**, and supports **continuous assurance** across the AI lifecycle.

> Repository: `cateryatech/caterya-v1.0` · License: Apache-2.0 · Status: **v1.0.0-alpha.2 — reference implementation**

AI should not only produce outputs. It should produce evidence.

---

## What it is — and is not

| CATERYA **is** | CATERYA **is not** |
|---|---|
| an evaluation + evidence + assurance layer | a foundation model or LLM provider |
| vendor-neutral, model-agnostic, black-box first | a regulator or universal certification authority |
| a producer of reproducible, signed evidence | an absolute safety guarantee |
| decision *support* (governance decides) | a replacement for human governance or domain experts |

The most important boundary: CATERYA **measures, analyzes, documents, verifies**. It never declares an AI "good" or "bad". Deployment decisions stay with the responsible organization, domain experts and governance authority — the code enforces this (`finalize()` requires a named decider and role; overriding a `REJECTED` recommendation requires a recorded reason).

## Quick start

```bash
pip install -e ".[all,dev]"          # core is stdlib-only; extras: api, crypto (Ed25519), yaml, quantum, viz, hf
# quantum-backends (PennyLane, Qiskit, Aer) stays out of `all` — it is large and optional
caterya demo                         # evaluates a healthy and a flawed mock system end to end
caterya evaluate --name my-system --version 1.0 --profile CATERYA-LLM --adapter mock:robust --out out/
caterya evidence verify out/bundle.json        # third-party verification: hash chain, signatures, Merkle proofs
caterya evidence reproduce out/bundle.json --adapter mock:robust   # re-run every metric from the recorded seed + data
caterya serve                        # REST API + dashboard on http://127.0.0.1:8080/ui/
```

```python
from caterya import AssuranceEngine, SystemConfig, MockModel   # swap MockModel for a real adapter

engine = AssuranceEngine(SystemConfig("support-assistant", "2.3.0", provider="acme", model_id="m", model_version="1"))
result = engine.evaluate(MockModel("robust"), "CATERYA-LLM")
print(result.summary())                                            # level, recommendation, risk, coverage
engine.decide(result.car["car_id"], "CONDITIONALLY_ASSURED", decided_by="Dr. Putri", role="AI governance lead",
              rationale="staging only", conditions=["re-test on production sample"])
```

Real models: `OpenAICompatAdapter` (any OpenAI-compatible endpoint), `AnthropicAdapter`, `HuggingFaceAdapter`, or wrap any SDK with `CallableAdapter`. Remote endpoints are checked against `CATERYA_ALLOWED_ENDPOINTS`.

## Architecture (v1.0)

```
L6 Assurance & Governance   independent evaluation · attestation (DSSE/in-toto) · decisions · policy gate
L5 Evidence & Provenance    evidence registry · SHA-256/SHA3-256 · Ed25519 · hash chain · Merkle transparency log
L4 Evaluation Engine        runner · profiles · metrics · agent traces · continuous monitor · incident loop
L3 Evaluation Domains       fairness · interpretability · robustness · safety · security · privacy · reliability
                            stability · sustainability · provenance · agentic
L2 CATERYA Core / Standard  schemas · metric specs (hash-bound) · profiles · risk model · regulatory map
L1 AI System / Data / Model LLM · ML · agent · multimodal · quantum  (model ≠ system)
```

The unit of evaluation is the **system** (model + tools + memory + policy + humans), not only the model. Agent evaluation consumes **system traces** (`evaluate(system_trace)`), not just labelled predictions.

### Core ideas that make it verifiable

- **Score → Evidence.** Every result is an `Evidence` record: claim, system hash, metric-spec hash, dataset hash, seed, result, 95 % CI, limitations, *untested* gaps, raw-output hash, timestamp, previous-record hash, signature. See [`docs/SPEC_EVIDENCE.md`](docs/SPEC_EVIDENCE.md).
- **Verify it, don't trust it.** `caterya evidence verify` and `reproduce` let a third party re-check integrity and re-run the measurement. Untested ≠ passed: gaps are first-class and lower coverage.
- **Static → Continuous.** Modes `pre_release · canary · post_release · incident_replay · drift`; tiered depth (`light` on change, `deep` on schedule/alert); PSI, KS and CUSUM drift detection; incident loop with enforced stages.
- **Assurance is contextual, versioned, time-bound.** CAR (CATERYA Assurance Record) has validity windows, versions chained by hash, and levels **0 Unverified → 4 Independently Attested** that describe *process depth*, not model quality.
- **Governance decides.** Risk = Probability × Impact × Exposure × Context produces a *recommendation*; a human decision is a separate, signed, recorded step.
- **Cryptographic provenance first; blockchain when justified.** Hash chain + Merkle transparency log + signed tree heads; optional anchors (file, ledger/TSA interface). Salted commitments and Merkle selective disclosure for private evidence (not zero-knowledge — `ZKBackend` is an interface only).
- **Quantum-ready, not quantum-dependent.** Classical statevector by default. PennyLane and Qiskit are optional and are not substituted if missing. `quantum_symmetry_index_v1` is a data-encoded swap test (research). See [`docs/QUANTUM.md`](docs/QUANTUM.md).
- **Guardrails recommend; they do not silently block.** Heuristic and full modes seal Evidence. A canary window under the configured threshold asks for `incident_replay`. See [`docs/GUARDRAILS.md`](docs/GUARDRAILS.md).

### Profiles

`CATERYA-BASIC` · `-LLM` · `-GENAI` · `-AGENT` · `-CRITICAL` · `-ENTERPRISE` · `-QUANTUM` — list with `caterya list profiles`; thresholds in [`docs/PARAMETERS.md`](docs/PARAMETERS.md) are **defaults to be replaced by your own risk appetite**.

### Metrics (32 registered)

Golden Triangle (entropy dispersion, invariance symmetry, explanation faithfulness) as an **optional view**, not a replacement for the records · Lyapunov-style stability (empirical divergence rate) · fairness, including a research quantum symmetry index and an optional two-group parity surface · robustness · policy adherence · prompt-injection resistance · PII leakage · reliability · calibration · sustainability estimate · provenance completeness · regulatory mapping coverage (not conformity) · agent metrics · guardrail recommendation and swarm consensus · quantum fidelity / entanglement entropy. Specs, assumptions, limitations, and the pillar label map: [`docs/METRICS.md`](docs/METRICS.md), [`docs/PILLARS.md`](docs/PILLARS.md). The composite **COS** is a *derived index only* and deliberately ignores safety/security domains — read the evidence, not the number.

## Honesty policy ("Verify it" applies to CATERYA itself)

- Physics-inspired metrics are **research metrics**: `behavioral_lyapunov_v1` estimates a divergence rate; it is *not* a proof of Lyapunov stability. Their value over simple baselines is **unproven** — see [`docs/VALIDATION_PROTOCOL.md`](docs/VALIDATION_PROTOCOL.md) (including results where baselines match).
- Mock-model results validate the *pipeline and metric sensitivity*, never real-model trustworthiness.
- Whitepaper v4.0 performance targets (< 3.2 ms edge overhead, > 50 000 req/s) are **not claimed**; `benchmarks/latency.py` measures the Python hook on your hardware.
- Regulatory mapping is indicative technical evidence mapping, not legal advice or conformity assessment.
- Every public claim is tracked in [`docs/CLAIMS.md`](docs/CLAIMS.md) with the command that checks it.

## Repository layout

```
src/caterya/   core · adapters · metrics · evaluators · profiles · evidence · provenance · assurance
               regulatory · monitoring · quantum · guardrails · viz · api · cli · ui · sdk.py · datasets.py
schemas/       JSON Schemas (evidence, CAR, system trace)         governance/  charter, succession, accreditation
docs/          architecture, specs, roadmap, claims, validation   benchmarks/  validity + latency harness
examples/      quickstart, quantum symmetry, guardrail, agent     tests/       pytest
```

## Development

```bash
make install   # editable install with all extras
make test      # pytest
make lint      # ruff
make docs      # regenerate docs/PARAMETERS.md, docs/METRICS.md, schemas/
make serve     # API + dashboard
```

Contributions welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md). Security reports: [`SECURITY.md`](SECURITY.md). Roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md).

> *An open infrastructure that **Ary** initiated and the ecosystem can continue.*
