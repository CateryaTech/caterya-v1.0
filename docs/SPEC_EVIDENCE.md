# Evidence specification — `caterya.evidence/v1`

A result is never a bare number. An Evidence record lets a third party re-check it.

| Field | Meaning |
|---|---|
| `claim` | what is asserted, e.g. "support-assistant 2.3.0: Prompt-injection resistance >= 0.8" |
| `system_under_test` | hash of the system fingerprint (model + tools + memory + policies + config + code hash) |
| `metric`, `metric_spec_hash` | metric id and hash of its operational definition (`MetricSpec`) |
| `dataset_hash` | hash over the content hashes of every dataset used; `context.datasets` maps names → hashes |
| `seed` | master seed; sub-seeds derive deterministically |
| `result`, `unit`, `ci_95`, `n` | value (null = **not tested**), unit, 95 % interval (Wilson or bootstrap), sample size |
| `limitations`, `untested` | known limits of the metric; reasons the metric could not be measured |
| `raw_outputs_hash` | hash of the full model-call log (prompts, outputs, seeds) |
| `timestamp`, `domain`, `profile`, `mode` | when, which domain/profile, which assurance mode |
| `evaluator` | key id, algorithm, `third_party_verifiable`, CATERYA version, environment hash |
| `context` | parameters, thresholds, status, details, token/call counts |
| `visibility` | public · restricted · confidential · proprietary |
| `prev_hash` | content hash of the preceding record (hash chain) |
| `content_hash`, `signature` | `content_hash = "<algo>:" + hex(H(canonical_json(record − {id, content_hash, signature})))`; signature signs the `content_hash` string |

`id = "EV-" + first 16 hex chars of content_hash`. Algorithms: `sha256` (default), `sha3-256`. Signatures: Ed25519 (third-party verifiable) or `hmac-sha256-dev` (symmetric; evidence flagged, level capped at 1).

## Canonical JSON

UTF-8, object keys sorted, separators `,` `:`, no insignificant whitespace, `NaN/Inf` rejected, enums as values, tuples as arrays. Floats use the shortest round-trip representation. This approximates RFC 8785 (JCS); cross-language implementations should use JCS number formatting and publish test vectors (`tests/test_core.py`).

## Verification procedure (what a third party does)

1. Recompute `content_hash` from the record; compare. 2. Verify `signature` with the evaluator's public key. 3. Walk `prev_hash` links. 4. Check the Merkle **inclusion proof** against a **signed tree head**. 5. Fetch datasets from the bundle, recompute their hashes. 6. Re-run the metric (`caterya evidence reproduce`): same seed, params and data must reproduce `result` exactly for deterministic systems, or within CI for stochastic APIs; `raw_outputs_hash` shows whether outputs were identical.

## Assurance Record (CAR) — `caterya.car/v1`

`car_id · version · prev_hash · system · model · deployment · evaluation{profile, methodology, evaluator, timestamp} · domains · risk{level, score, residual, findings, unresolved} · evidence{artifacts, hashes, merkle_root, sth} · coverage{required, measured_required, untested} · cos · regulatory · disposition{status, recommended, conditions, decided_by, role, rationale, override_reason} · validity{issued_at, valid_until} · attestations · level · content_hash · signature`.
Status values: `EVALUATED · REVIEW_REQUIRED · CONDITIONALLY_ASSURED · ASSURED · REJECTED · EXPIRED` (expiry computed from `valid_until`). Schemas: `schemas/*.json`.

## System trace — `caterya.trace/v1`

`trace_id · goal · steps[index, type, name, args, content, ok, scope, side_effect, meta] · outcome · meta`. Step types: `prompt, plan, tool_call, tool_result, retrieval, observation, decision, action, human_override, error, output`.
