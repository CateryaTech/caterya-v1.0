# Pillar labels

Framework 3.0 named four pillars. In v1.0 they are **labels on evaluation domains**, not a second scoring system. The evidence is still the per-metric record.

| Label | v1.0 domain | What it actually measures |
|---|---|---|
| Energy Landscape / Symmetry Index | fairness | Counterfactual parity, tabular gaps, and (optionally) the quantum-encoded rate symmetry. The "energy" surface is `z = 1 − \|rate_a − rate_b\|`. |
| Information authenticity | interpretability | Explanation faithfulness and dispersion on the supplied probes. |
| Lyapunov-style stability | robustness (and the stability domain) | Perturbation ratio and an empirical divergence rate. Not a Lyapunov proof. |
| Provenance / transparency | provenance | Declared-field completeness. Entanglement entropy is a separate informational quantity, not this pillar's score. |

The same paragraph is on every `Profile.domain_note`. Golden Triangle (`G = (E · S · I)^(1/3)`) is an optional view inside `car["cos"]["golden_triangle_view"]`. A missing axis leaves `G` null; it is not imputed inside `G`. COS may still treat a missing `G` as 1 so the pillar mean remains visible — that choice is written in the view. Safety, security, and privacy are outside the triangle.

`fairness_energy_map_v1` hashes the canonical grid (`artifact_hash`). Plotly HTML (`caterya[viz]`) is a rendering of that grid and is not the hashed object. Name both groups; the metric will not pick a pair for you.
