"""Technical regulatory mapping: clause -> tests (not clause -> PDF).

INDICATIVE ONLY. Technical evidence availability is not legal compliance or conformity. Clause references
are summarised from memory of the public texts and MUST be verified against current official sources.
"""
from __future__ import annotations

FRAMEWORKS = {
    "EU_AI_ACT": "EU Artificial Intelligence Act (high-risk system requirements)",
    "NIST_AI_RMF": "NIST AI Risk Management Framework 1.0",
    "ISO_42001": "ISO/IEC 42001 AI management system",
    "OECD": "OECD AI Principles",
    "INDONESIA": "Indonesia: SE Menkominfo 9/2023 AI ethics values; UU PDP 27/2022 (personal data)",
    "ID_AI_ETHICS_2026": (
        "Indonesia AI ethics themes, labelled 2026 for this pack. Identifiers are thematic, "
        "not verified article numbers of a consolidated 2026 statute. Check current Komdigi texts."
    ),
}

M = lambda *ids: list(ids)  # noqa: E731
# (framework, clause, title, metrics, note, optional)
CLAUSES = [
    ("EU_AI_ACT", "Art. 9", "Risk management system", M("injection_resistance_v1", "policy_adherence_v1", "pii_leakage_v1"), "Continuous risk identification and testing", False),
    ("EU_AI_ACT", "Art. 10", "Data and data governance (bias examination)", M("fairness_parity_v1", "fairness_tabular_v1"), "Bias examination of outputs", False),
    ("EU_AI_ACT", "Art. 11-12", "Technical documentation and record-keeping", M("provenance_completeness_v1"), "Evidence records and logs", False),
    ("EU_AI_ACT", "Art. 13", "Transparency to deployers", M("information_faithfulness_v1", "provenance_completeness_v1"), "Explanation faithfulness", False),
    ("EU_AI_ACT", "Art. 14", "Human oversight", M("agent_tool_safety_v1", "agent_escalation_v1"), "Human approval gates for sensitive tools", False),
    ("EU_AI_ACT", "Art. 15", "Accuracy, robustness, cybersecurity", M("reliability_v1", "robustness_perturbation_v1", "injection_resistance_v1", "calibration_ece_v1"), "Accuracy, perturbation robustness, attack resistance", False),
    ("EU_AI_ACT", "Art. 72", "Post-market monitoring", M("behavioral_lyapunov_v1"), "Continuous evaluation and drift monitoring (see monitoring module)", False),
    ("EU_AI_ACT", "Art. 9 note", "Research extension: guardrail score during canary", M("guardrail_decision_v1"), "Operational signal only. Not a substitute for Art. 14 human oversight.", True),
    ("EU_AI_ACT", "Art. 10 note", "Research extension: quantum-encoded parity", M("quantum_symmetry_index_v1"), "Not text of the Act. Absence is informational, not a legal gap.", True),
    ("NIST_AI_RMF", "MEASURE 2.5", "Valid and reliable", M("reliability_v1", "robustness_perturbation_v1", "calibration_ece_v1"), "", False),
    ("NIST_AI_RMF", "MEASURE 2.6", "Safe", M("policy_adherence_v1", "agent_persistence_v1"), "", False),
    ("NIST_AI_RMF", "MEASURE 2.7", "Secure and resilient", M("injection_resistance_v1", "agent_unauthorized_action_v1"), "", False),
    ("NIST_AI_RMF", "MEASURE 2.8", "Transparent and accountable", M("provenance_completeness_v1"), "", False),
    ("NIST_AI_RMF", "MEASURE 2.9", "Explainable and interpretable", M("information_faithfulness_v1"), "", False),
    ("NIST_AI_RMF", "MEASURE 2.10", "Privacy risk", M("pii_leakage_v1"), "", False),
    ("NIST_AI_RMF", "MEASURE 2.11", "Fairness and bias", M("fairness_parity_v1", "fairness_tabular_v1"), "", False),
    ("NIST_AI_RMF", "MEASURE 2.12", "Environmental impact", M("sustainability_estimate_v1"), "", False),
    ("NIST_AI_RMF", "MANAGE 4.1", "Post-deployment monitoring", M("behavioral_lyapunov_v1"), "Monitoring module", False),
    ("ISO_42001", "9.1", "Monitoring, measurement, analysis, evaluation", M("reliability_v1", "robustness_perturbation_v1", "behavioral_lyapunov_v1"), "", False),
    ("ISO_42001", "8.x", "Operational planning and control", M("policy_adherence_v1", "agent_tool_safety_v1"), "", False),
    ("ISO_42001", "10.2", "Nonconformity and corrective action", M(), "Incident loop produces re-test evidence", False),
    ("OECD", "1.2", "Human rights, fairness, privacy", M("fairness_parity_v1", "pii_leakage_v1"), "", False),
    ("OECD", "1.3", "Transparency and explainability", M("information_faithfulness_v1"), "", False),
    ("OECD", "1.4", "Robustness, security, safety", M("robustness_perturbation_v1", "injection_resistance_v1", "policy_adherence_v1"), "", False),
    ("OECD", "1.5", "Accountability", M("provenance_completeness_v1"), "Signed, hash-chained evidence", False),
    ("INDONESIA", "Keamanan", "Security value", M("injection_resistance_v1", "policy_adherence_v1"), "AI ethics circular", False),
    ("INDONESIA", "Transparansi", "Transparency value", M("information_faithfulness_v1", "provenance_completeness_v1"), "", False),
    ("INDONESIA", "Inklusivitas", "Inclusivity / non-discrimination", M("fairness_parity_v1"), "", False),
    ("INDONESIA", "Pelindungan Data Pribadi", "Personal data protection", M("pii_leakage_v1"), "Also UU PDP", False),
    ("INDONESIA", "Pembangunan & Lingkungan Berkelanjutan", "Sustainability", M("sustainability_estimate_v1"), "", False),
    ("ID_AI_ETHICS_2026", "Keamanan", "Security theme", M("injection_resistance_v1", "policy_adherence_v1"), "Thematic label, verify against the current official text", False),
    ("ID_AI_ETHICS_2026", "Transparansi", "Transparency theme", M("information_faithfulness_v1", "provenance_completeness_v1"), "Thematic label", False),
    ("ID_AI_ETHICS_2026", "Inklusivitas", "Inclusivity theme", M("fairness_parity_v1", "fairness_tabular_v1"), "Thematic label", False),
    ("ID_AI_ETHICS_2026", "Pelindungan Data", "Personal-data theme", M("pii_leakage_v1"), "Thematic label; also consider UU PDP", False),
    ("ID_AI_ETHICS_2026", "Akuntabilitas", "Accountability theme", M("provenance_completeness_v1"), "Signed evidence is a technical trace, not legal accountability", False),
    ("ID_AI_ETHICS_2026", "Keandalan", "Reliability theme", M("reliability_v1", "robustness_perturbation_v1"), "Thematic label", False),
    ("ID_AI_ETHICS_2026", "Pengawasan Manusia", "Human oversight theme", M("agent_escalation_v1"), "A guardrail score is not human oversight", False),
]
DISCLAIMER = ("Indicative mapping of technical evidence to framework themes. Not legal advice, not a conformity "
              "assessment, not a certification; verify clause text against current official sources.")


def map_evidence(evidences: list, framework: str | None = None) -> dict:
    best: dict[str, dict] = {}
    for e in evidences:
        best[e.metric] = {"result": e.result, "id": e.id}
    out: dict[str, list] = {}
    for fw, cid, title, metrics, note, optional in CLAUSES:
        if framework and fw != framework:
            continue
        have = [m for m in metrics if m in best and best[m]["result"] is not None]
        if not metrics:
            status = "no_mapped_tests"
        elif optional and not have:
            status = "informational"
        elif len(have) == len(metrics):
            status = "evidenced"
        elif have:
            status = "partial"
        else:
            status = "gap"
        out.setdefault(fw, []).append({
            "clause": cid,
            "title": title,
            "status": status,
            "optional": optional,
            "metrics": metrics,
            "evidence": [best[m]["id"] for m in have],
            "missing": [m for m in metrics if m not in have],
            "note": note,
        })
    return {"frameworks": {k: FRAMEWORKS[k] for k in out}, "mapping": out, "disclaimer": DISCLAIMER}


def coverage_fraction(mapped: dict) -> dict:
    """Fraction of non-optional clauses with status ``evidenced``.

    Optional research rows are excluded from the denominator. The fraction is
    mapping coverage, not conformity.
    """
    counts = {"evidenced": 0, "partial": 0, "gap": 0, "no_mapped_tests": 0, "informational": 0, "normative": 0}
    for clauses in mapped["mapping"].values():
        for clause in clauses:
            counts[clause["status"]] = counts.get(clause["status"], 0) + 1
            if not clause["optional"] and clause["status"] != "no_mapped_tests":
                counts["normative"] += 1
                if clause["status"] == "evidenced":
                    counts["evidenced_normative"] = counts.get("evidenced_normative", 0) + 1
    normative = counts["normative"]
    evidenced = counts.get("evidenced_normative", 0)
    return {
        "fraction_evidenced": (evidenced / normative) if normative else None,
        "evidenced_normative": evidenced,
        "normative": normative,
        "counts": {k: v for k, v in counts.items() if k != "evidenced_normative"},
        "disclaimer": DISCLAIMER,
        "formula": "evidenced non-optional clauses / non-optional clauses",
        "status": "research",
        "limitations": [
            "Coverage of this mapping table, not legal conformity.",
            "Partial clauses count as not evidenced in the fraction.",
            "Clauses with no mapped tests, and optional research rows, are excluded from the denominator.",
        ],
    }


def summary(evidences: list, framework: str | None = None) -> dict:
    m = map_evidence(evidences, framework)["mapping"]
    return {fw: {s: sum(1 for c in cs if c["status"] == s) for s in ("evidenced", "partial", "gap", "no_mapped_tests")} for fw, cs in m.items()}
