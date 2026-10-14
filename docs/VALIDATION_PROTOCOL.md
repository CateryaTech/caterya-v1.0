# Validation protocol

The largest risk to CATERYA is **empirical validity**: do the metrics measure what they claim, can they be gamed, and do they detect anything simpler methods miss? This protocol defines how that is tested and published — including negative results.

## Hypotheses

- **H1 Criterion validity.** Metric scores correlate with independently labelled failures (jailbreak success, leakage incidents, harmful tool actions) on real systems.
- **H2 Reproducibility.** Same system, seed and data → same result; across seeds/runs the CI covers the true value at the nominal rate.
- **H3 Incremental validity.** Each metric improves detection over the strongest simple baseline (accuracy, refusal rate, output-length statistics, off-the-shelf classifiers, Inspect/HELM/lm-eval tasks).
- **H4 Robustness to gaming.** Optimising a system against the published probes does not raise the score without reducing held-out failures.

## Procedure

1. Pre-register metric specs (`docs/METRICS.md`, spec hashes). 2. Evaluate open-weight models (Llama, Qwen, Mistral families) and API models in black-box mode across versions. 3. Obtain labels from independent red-teams / incident reports. 4. Report AUROC, calibration, rank correlation, CIs, and baseline deltas. 5. Hold out probe sets and rotate them; publish a public-replication kit. 6. Publish **negative results**. 7. Third-party replication before any claim moves from `experimental` to `stable`.

## Stage-0 results (controlled mock flaw-injection)

`python benchmarks/validate.py --seeds 8` — healthy mock vs mock with 30 % injected flaw; baseline = simple comparator. This checks sensitivity and the harness, **not** real-model validity.

| Flaw | Metric | AUROC | Baseline AUROC | Dose–response ρ | Reading |
|---|---|---|---|---|---|
| brittle | symmetry_invariance_v1 | 1.00 | 0.50 | −1.00 | adds information (baseline blind) |
| brittle | robustness_perturbation_v1 | 1.00 | 0.50 | −1.00 | adds information |
| noisy | reliability_v1 | 1.00 | 1.00 | −1.00 | no gain over accuracy |
| noisy | entropy_dispersion_v1 | 1.00 | 1.00 | −0.90 | no gain over accuracy |
| leaky | injection_resistance_v1 | 1.00 | 1.00 | −0.97 | no gain over refusal-keyword rate |
| leaky | pii_leakage_v1 | 1.00 | 1.00 | −0.97 | no gain |
| leaky | policy_adherence_v1 | 1.00 | 1.00 | −0.89 | no gain |
| biased | fairness_parity_v1 | 1.00 | 0.25 | −1.00 | adds information (baseline mis-directed) |
| chaotic | behavioral_lyapunov_v1 | 1.00 | 1.00 | −1.00 | no gain over output-length stability (toy) |
| forgetful | context_coupling_v1 | 1.00 | 0.50 | n/a | adds information (severity does not scale memory) |

Honest reading: on toy mocks several physics-inspired and leakage metrics match simple baselines; the case for them must be made on real systems (H1/H3). Mocks are deterministic, so AUROC of 1.00 mostly shows the metrics see the injected flaw.

## Quantum and guardrail metrics (not yet in stage-0)

These are research metrics. Stage-0 mock AUROC has **not** been run for them. Until it has, they stay `research` and must not be described as validated.

- **H2 for `quantum_symmetry_index_v1`.** Same rates, seed, and backend → same value and same `circuit_hash`. Checked for the classical, PennyLane, and Qiskit statevectors in `tests/test_quantum.py`. Not checked on hardware.
- **H3.** No claim that the swap test detects unfairness that demographic parity on the same rates does not. The encoding is a function of those rates.
- **H1 for guardrails.** No claim that the lexical screen or the swarm predicts incidents. Hard flags are keyword lists.
- **H2 for the swarm.** Same score map → same consensus. Checked. Abstention is the result when the map does not cover an agent.

## Anti-gaming checklist (to implement before `stable`)

adversarial/paraphrase probe generation · rotating private held-out sets · public replication · opacity penalty in COS (implemented as coverage penalty) · evaluator-side randomisation of probe order and seeds · detection of evaluation-aware behaviour (distribution difference between probe and production traffic).
