# Succession and continuity

Goal: CATERYA continues if the founder is unavailable. "An open infrastructure that Ary initiated and the ecosystem can continue."

1. **No single point of control.** Repository admin, package-registry publishing, domain, signing keys and trademark are held by the Foundation (or a named custodian until it exists), with ≥ 3 admins from ≥ 2 organisations.
2. **Key custody.** Release-signing and log-signing keys use multi-party custody (threshold scheme / HSM with M-of-N officers). Key rotation procedure and revocation list are published. Evaluator keys for evidence are the *evaluator's* and never held by the project.
3. **Succession triggers.** Founder inactivity > 90 days without handover, resignation, incapacity, or TSC vote of no confidence. The TSC chair assumes interim stewardship; a successor steward is elected within 120 days.
4. **Documentation.** Specification, runbooks, release process and governance records live in the repo (`docs/`, `governance/`); no tribal knowledge.
5. **Escrow.** Registry credentials, domain registrar access and trademark documents are placed with a legal custodian under written instructions.
6. **Fork-friendliness.** Apache-2.0, open specs and portable evidence bundles mean any party can continue verification even if the project stops: published evidence stays verifiable offline.
7. **Review.** Succession plan reviewed annually and after any change in custodians.
