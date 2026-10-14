# Roadmap and implementation status

Legend: ✅ implemented and tested in this repo · 🟡 partial / interface only · ⬜ planned · ⛔ explicitly not claimed

## Architecture v1.0 phases

| Phase | Focus | Status |
|---|---|---|
| 0 Foundation | specification, schema, taxonomy, core metrics, reference architecture | ✅ |
| 1 Core v1.0 | Core API, evaluation schema, domains, provenance, evidence, CLI, docs, tests | ✅ (SQLite; PostgreSQL ⬜) |
| 2 Engine | LLM evaluation ✅ · agent evaluation ✅ (scenario traces) · continuous evaluation 🟡 (monitor + scheduler logic; no daemon) · regression ✅ · CI/CD gate ✅ · dashboard ✅ (basic) |
| 3 Evidence infrastructure | registry ✅ · crypto provenance ✅ · attestation 🟡 (DSSE + trust list; no hosted log) · Evidence Graph ✅ (export) · version history ✅ |
| 4 Assurance | independent evaluation 🟡 (level-4 mechanism; no accredited evaluators yet) · enterprise / critical-infrastructure assurance ⬜ |
| 5 Ecosystem | researchers, integrators, auditors, universities, regulators ⬜ |
| 6 Quantum extension | classical statevector + PennyLane + Qiskit adapters; symmetry / fidelity / entanglement evidence ✅ (research). Hardware campaigns and algorithm assurance ⬜ |

## Strategic phases (repositioning analysis)

| Phase | Deliverables | Status |
|---|---|---|
| 1 · 0–12 months — prove technical value | operational metric specs ✅ · open-weight evaluation vs baselines ⬜ (harness ✅ `benchmarks/validate.py`) · paper (arXiv / safety-eval workshop) ⬜ · Evidence schema v0.1 → `v1` ✅ |
| 2 · 12–24 months — easy to install | Python library/middleware ✅ · OpenAI-compatible + Anthropic + HF adapters ✅ · LangChain/LlamaIndex/Inspect/LangGraph/AutoGen integrations ⬜ · regulatory mapping ✅ (indicative) · tamper-evident log ✅ · 2–3 pilots ⬜ |
| 3 · 24+ months — standard & governance | independent foundation/consortium ⬜ (charter drafted ✅) · certification/audit model ⬜ · Indonesia / Global-South vertical packs (finance/OJK, health, energy) ⬜ · approach frontier labs only after adoption evidence ⬜ |

## Whitepaper v4.0 (2026–2030) mapping

| Item | Status |
|---|---|
| Open-source core SDK, systemic-assurance spec | ✅ (this repo) |
| Pilots: RSPAD Digital Health, SPC grant portal | ⬜ (no pilot code or data in this repo) |
| Enterprise control plane, killswitches, alert dispatcher | ⬜ (API + dashboard are the seed) |
| LangGraph / AutoGen integrations | 🟡 node/callback adapters that attach Evidence and do not drop the output (`guardrails/adapters.py`). AutoGen not started. Not a runtime dependency. |
| US data-centre financial-compliance module | ⬜ |
| Hilbert-space quantum assurance module | 🟡 research circuits and evidence metadata; not a device-assurance claim |
| Rust/C++/WASM edge kernel, Go parallel engine | ⬜ |
| Latency < 3.2 ms, > 50 000 req/s, "zero storage bloat" | ⛔ targets, not claims — measure with `benchmarks/latency.py` |
| ISO/IEC AI trust-standard certification | ⛔ not claimed; standards work requires external bodies |
| Open Standard Foundation, steering committee, social-impact trust | ⬜ charter drafted: `governance/` |
| "Mathematical proof of trustworthiness" language | ⛔ replaced by "evidence"; see `docs/CLAIMS.md` |

## Next engineering milestones

1. PostgreSQL store + migrations. 2. Held-out, rotating probe sets + anti-gaming suite (adversarial evaluation, public replication, opacity penalty). 3. Inspect / LangGraph / OpenTelemetry exporters. 4. White/gray-box adapters (activations, logprobs) for interpretability and memorisation tests. 5. Hosted public transparency log + RFC 3161 timestamping. 6. Daemon scheduler for canary / post-release modes. 7. Domain packs with expert-reviewed datasets.
