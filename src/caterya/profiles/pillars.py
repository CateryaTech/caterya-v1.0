"""How Framework 3.0 pillar names sit on v1.0 evaluation domains.

The names are a map for readers. They do not add a score, and they do not
replace the metric evidence listed under each domain.
"""
from __future__ import annotations

PILLAR_MAP: dict[str, dict[str, object]] = {
    "fairness": {
        "framework_3": "Energy Landscape / Symmetry Index",
        "v1_domain": "fairness",
        "also_reads": ("symmetry_invariance_v1",),
        "metrics": (
            "fairness_parity_v1",
            "fairness_tabular_v1",
            "quantum_symmetry_index_v1",
            "fairness_energy_map_v1",
        ),
        "note": "Parity and invariance are empirical. 'Energy' is a metaphor for the parity surface, not a Hamiltonian.",
    },
    "interpretability": {
        "framework_3": "Information authenticity / explanation faithfulness",
        "v1_domain": "interpretability",
        "metrics": ("information_faithfulness_v1", "entropy_dispersion_v1"),
        "note": "Faithfulness here is agreement between an explanation and the system's answers on the supplied probes, not a proof of mechanism.",
    },
    "robustness": {
        "framework_3": "Stability / Lyapunov-style",
        "v1_domain": "robustness",
        "also_reads": ("stability",),
        "metrics": ("robustness_perturbation_v1", "behavioral_lyapunov_v1"),
        "note": "behavioral_lyapunov_v1 is an empirical divergence rate. It is not a Lyapunov certificate.",
    },
    "transparency": {
        "framework_3": "Provenance completeness (Entanglement was the Framework 3.0 label)",
        "v1_domain": "provenance",
        "metrics": ("provenance_completeness_v1", "regulatory_mapping_v1"),
        "note": "Entanglement entropy is a separate informational quantum quantity. It is not a transparency score.",
    },
}

PROFILE_DOMAIN_NOTE = (
    "Domains map to Framework 3.0 pillars as labels only: "
    "fairness←energy/symmetry, interpretability←information, "
    "robustness←Lyapunov-style stability, provenance←transparency. "
    "See docs/PILLARS.md. Labels are not extra scores."
)
