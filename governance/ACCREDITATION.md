# Evaluator accreditation (required for assurance level 4)

An evidence record reaches **level 4 — Independently Attested** only when a DSSE/in-toto attestation over the CAR is signed by a key that is (a) different from the evaluator's key and (b) listed in the deployment's trust list (`trusted_attesters`).

Accreditation criteria (draft):
- **Independence:** no ownership of, or commercial interest in, the evaluated system or its vendor; disclosed relationships; no outcome-contingent fees.
- **Competence:** named evaluators with relevant ML-safety / security / domain expertise; documented methodology covering the profile.
- **Reproducibility:** publishes evidence bundles; re-runs and confirms the evaluated evidence (`caterya evidence reproduce`) with its own seeds and held-out probes.
- **Security:** key custody, audit logs, incident handling, SBOM and signed releases for its tooling.
- **Process:** complaint and appeal procedure; public register of accredited bodies and attested systems; annual surveillance.

Accredited bodies attest *a defined assurance process was completed on stated evidence*; they do not certify that a system is safe.
