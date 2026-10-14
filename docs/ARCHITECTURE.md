# Architecture

Reference architecture v1.0 → implemented in `src/caterya`. Principles: model-agnostic · vendor-neutral · framework-agnostic · deployment-agnostic · reproducible · evidence-driven · quantum-ready.

## Layer → module map

| Layer | Responsibility | Modules |
|---|---|---|
| L1 AI system | what is evaluated (model, +tools, +memory, +agent, +environment, socio-technical) | `core/system.py`, `adapters/*`, `evaluators/agent.py` |
| L2 Core / standard | schemas, metric specs, profiles, taxonomy, risk model | `core/*`, `metrics/base.py`, `profiles/`, `assurance/risk.py`, `schemas/` |
| L3 Domains | fairness · interpretability · robustness · safety · security · privacy · reliability · stability · sustainability · provenance · agentic | `metrics/*` |
| L4 Engine | pipeline, continuous monitoring, regression, incident loop | `evaluators/runner.py`, `monitoring/*`, `assurance/regression.py` |
| L5 Evidence & provenance | registry, hashing, signing, Merkle log, attestation, selective disclosure | `evidence/*`, `provenance/*` |
| L6 Assurance & governance | CAR, levels, decisions, policy gate, reports, regulatory map | `assurance/*`, `regulatory/*`, `governance/` |

## Evaluation pipeline

`REGISTER SYSTEM → DEFINE CONTEXT → SELECT PROFILE → PREPARE → EXECUTE → ANALYZE → GENERATE EVIDENCE → PROVENANCE & ATTESTATION → RISK / ASSURANCE → REPORT / API`

Every step is recorded in `EvaluationResult.steps`. Failures of individual metrics never abort a run: they become explicit **untested gaps** with reasons, reduce coverage, and are reported.

## Data model

`ORGANIZATION → AI SYSTEM → MODEL VERSION → DATASET / ENVIRONMENT / EVALUATION → TEST → RESULT → EVIDENCE → ASSURANCE RECORD`. Identifiers are content-derived (`SYS-…` from the system fingerprint, `EV-…` from the evidence hash, `CAR-YYYY-NNNNNN` sequential per year with hash-chained versions).

Evidence Graph (`evidence/store.py: build_graph`): `MODEL evaluated_by EVALUATION · uses DATASET · runs_on ENVIRONMENT · executes TEST · produces RESULT; MODEL produces EVIDENCE; EVIDENCE supports ASSURANCE` — exportable as JSON or Graphviz DOT.

## Assurance decision model

`EVALUATION → FINDINGS → RISK ANALYSIS → (recommendation) → GOVERNANCE DECISION → ASSURED | CONDITIONAL | REJECTED`

- **Findings** are CI-aware: `fail` only if the 95 % CI lies wholly below the threshold; if the CI straddles it the status is `inconclusive` → *review required*, not silently pass or fail.
- **Hard-gate domains** (safety, security, privacy; agent authorisation metrics) turn confirmed failures into a `REJECTED` recommendation.
- **Risk** = (1 − value) × (criticality × domain weight) × exposure × context-multiplier; the level is the max of the numeric level and the worst finding severity. Mitigations reduce residual risk **only when linked to existing evidence**.
- **Levels:** 0 Unverified · 1 Evaluated · 2 Evidence-Backed (chain + third-party-verifiable signature) · 3 Assured (recorded human decision, coverage ≥ minimum) · 4 Independently Attested (DSSE attestation by a *trusted, different* key). HMAC development keys cap at level 1 because they are not third-party verifiable.

## Provenance

```
artifact → canonicalization → hash → signature → timestamp → evidence registry
```
Evidence records hash-chain to their predecessor; each content hash is appended to a Merkle transparency log (RFC 6962/9162 domain separation) with signed tree heads, inclusion proofs and prefix-consistency checks. `provenance/anchor.py` publishes tree heads to a file or (interface) ledger/RFC 3161 TSA. DSSE + in-toto statements carry third-party attestations.

## Privacy architecture

`RAW DATA → PRIVATE EVALUATION ENVIRONMENT → DERIVED METRICS → EVIDENCE → PUBLIC / RESTRICTED ATTESTATION`. Evidence stores hashes of data, never the data; visibility classes `public · restricted · confidential · proprietary`; bundles include datasets only when exported with data; `SelectiveDisclosure` reveals chosen fields with Merkle proofs.

## Continuous assurance & incident loop

Signals → `ContinuousMonitor` (PSI / KS / CUSUM) → `ReEvalTrigger(light|deep)`. Incidents: `CAPTURED → EVIDENCED → REPRODUCED → EVALUATED → MITIGATED → RETESTED → CLOSED`, stages enforced; mitigations are `verified` only after a re-test passes.

## Extension points

`register_metric` (new metrics), `ModelAdapter`/`AgentAdapter` (new systems), `Anchor` (ledgers/TSA), `ZKBackend` (proof systems), `Backend` (quantum), `EvidenceStore` (swap SQLite for PostgreSQL), `Profile`/`MetricPlan` (custom profiles).
