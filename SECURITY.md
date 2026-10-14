# Security policy and threat model

Report vulnerabilities privately to the maintainers (security contact to be published with the Foundation; until then use GitHub private vulnerability reporting). Do not open public issues for exploitable bugs.

## Threat model (summary)
| Threat | Mitigation | Residual |
|---|---|---|
| Altered results | content hash + signature + hash chain + Merkle log + signed tree heads | evaluator can lie about *what it ran*; mitigate with reproducibility and level-4 attestation |
| Forged evaluator identity | Ed25519 keys; trust lists; HMAC dev keys flagged `third_party_verifiable=false` and cap level at 1 | key theft → custody and rotation required |
| Gaming the probes | seeded sampling, hash-bound datasets, rotating held-out sets (planned) | public probes are gameable |
| SSRF via adapters | remote endpoints must match `CATERYA_ALLOWED_ENDPOINTS` (API refuses otherwise) | operator must configure allowlist |
| API abuse | optional bearer token `CATERYA_API_KEY` on mutating routes; run behind TLS/reverse proxy | no rate limiting built in |
| Data leakage in evidence | hashes not data; visibility classes; selective disclosure | raw outputs may contain sensitive text; keep `include_raw_outputs=false` |
| Supply chain | zero runtime dependencies in core; dependency scanning, SBOM and signed builds recommended in CI | to be automated |

Private keys: `signing_key.json` is created with mode 0600 in the state directory. Never commit it (`.gitignore` excludes `.caterya/`).
