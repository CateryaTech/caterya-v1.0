# Benchmarks

- `validate.py` — validity harness: AUROC vs simple baselines and dose–response on mock models with injectable flaws (docs/VALIDATION_PROTOCOL.md). Sanity check, not real-model evidence.
- `latency.py` — overhead of the Python `AgentGuard` hook on your hardware. Publish its output with any performance statement.
- Add real-model studies here (scripts + result JSON + the evidence bundles that produced them) so they can be reproduced with `caterya evidence reproduce`.
