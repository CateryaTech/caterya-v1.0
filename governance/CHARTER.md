# CATERYA Governance Charter (draft v0.1)

Status: **draft for the founding board**. Not a legal instrument; entity formation, licensing opinions and tax structure need qualified counsel.

## 1. Purpose
Maintain CATERYA as an open standard and reference implementation for AI evaluation, evidence and assurance that outlives any founder or company.

## 2. Separation of entities (independence)
| Entity | Role | Rules |
|---|---|---|
| **CATERYA Foundation / consortium** (to be formed) | owns the specification, schemas, metric registry, trademark and certification scheme | non-profit; no commercial evaluation work on its own account; open membership |
| **Open-source project** (`cateryatech/caterya-v1.0`) | reference implementation | Apache-2.0; governed by the Technical Steering Committee |
| **CATERYA Tech** (commercial) | implementation services, enterprise control plane, training, integration | may not decide specification changes alone; must disclose conflicts when acting as evaluator |
| **Independent evaluators / accredited bodies** | third-party attestation (level 4) | accredited under `ACCREDITATION.md`; may not attest systems they build or sell |

A framework that evaluates others must itself be evaluable: the entity that sells a model, or commercial advantage from a verdict, does not issue that verdict.

## 3. Bodies
- **Technical Steering Committee (TSC)** — 5–9 members, majority external to CATERYA Tech; owns spec versions, metric status promotion (`research → experimental → stable`), release process.
- **Research Council** — academics/labs; reviews methodology, benchmark design, validation results; can block promotion of a metric to `stable`.
- **Accreditation Board** — accredits evaluators; handles complaints.
- **Community maintainers** — merge rights by merit, with 2-reviewer rule on `core/`, `provenance/`, `assurance/`.

## 4. Decision making
Lazy consensus for routine changes; 2/3 TSC vote for breaking spec changes; public RFCs (`docs/rfcs/`) with ≥ 30-day comment period for anything that changes evidence/CAR schemas, metric definitions or levels. All changes are versioned; old spec versions remain verifiable (schema versions are embedded in records).

## 5. Neutrality rules
No pay-to-pass; no evaluator fee contingent on outcome; evaluator results and methodology public by default; conflicts of interest declared and recorded in the CAR (`evaluator` block); vendors cannot veto findings about their own systems.

## 6. Metric promotion
`research` → `experimental`: written spec + tests. `experimental` → `stable`: independent replication, published validation against baselines (including negative results), anti-gaming review.

## 7. Intellectual property boundary
Spec, schemas, core code and metric definitions: Apache-2.0 (patent grant). Trademarks "CATERYA", the level names and any certification mark: held by the Foundation, licensed for conformant use. Datasets: licence stated per dataset; no proprietary data in the repo. Contributors sign off commits (DCO).

## 8. Funding and social-impact principle
Revenue from services, accreditation fees and enterprise control plane funds maintenance; a **published, fixed share** of commercial revenue is directed to a legally separate social trust (education, health research, elder care). The percentage and instrument are set by the founding board and published; they are not encoded in this repository.

## 9. Transparency
Annual public report: finances, accreditations, conflicts of interest, spec changes, validation results, incidents involving the infrastructure itself.
