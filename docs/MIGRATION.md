# From Framework 3.0 / Whitepaper 4.0 to v1.0 — what changed and why

| Earlier statement | v1.0 treatment | Reason |
|---|---|---|
| "Ethical AI Framework / evaluator" | AI Assurance Infrastructure; ethics = *why*, trustworthiness = *what is measured* | the market needs verifiable evidence; the humanist identity stays |
| Single Assurance Index `A = S·T_sym·V_L` | Evidence bundle is primary; **COS** is a derived index with pillar weights, Golden-Triangle modulation and a coverage (opacity) penalty | a product of three research quantities is easy to game and hides which one failed |
| "Mathematical proof of trustworthiness", "guarantees convergence" | "evidence"; Lyapunov-**style** empirical divergence rate; numeric decrease check for control trajectories | black-box LLMs have no state equation to prove stability on |
| "Zero hallucination variance (S(x) < 0.05)" | not claimed; entropy = answer **dispersion**, explicitly *not* a hallucination detector | high entropy ≠ wrong; low entropy ≠ right |
| Entanglement `E(ρ)` for context memory | classical context-retention probe; true von Neumann entropy only for supplied density matrices (`quantum/`) | no density matrix exists for a text model |
| Operates "directly on inference streams in real time" | batch / sidecar / CI gate by default; inline hook for **high-risk actions only** | full per-token evaluation is slow, costly and gameable |
| Latency < 3.2 ms; > 50 000 req/s; "zero storage bloat" | targets, not claims; Python hook measured by `benchmarks/latency.py` | Verify it |
| "Distributed tamper-evident ledger" | hash chain + Merkle transparency log + signed tree heads; ledger anchoring optional | same properties, no blockchain cost |
| Quantum AI product | `enable_quantum` capability flag; slot, not SKU | no near-term market need |
| "Mandatory on every frontier backend" | long-term outcome of adoption, regulation, reputation | claim before evidence reads as hype |
| Label-based `evaluate(output, ground_truth)` | `evaluate(system_trace)` plus labelled tasks where labels exist | generative outputs and agent traces lack ground truth |
| Framework 3.0 Python API | `caterya.AssuranceEngine`, `EvaluationRunner`, `register_metric`; evidence + CAR schemas | port 3.0 metrics as `Metric` subclasses with a `MetricSpec` |

Porting a 3.0 metric: subclass `Metric`, write a `MetricSpec` (formula, assumptions, **limitations**), implement `compute(ctx)` using `ctx.ask(...)` for every model call (so the call log is hashed), return `self.result(value, ci, n, **details)`, register with `@register_metric`, add it to a `Profile`. See `examples/custom_metric.py`.
