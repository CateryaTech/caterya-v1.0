"""Central parameters. Every field is documented in docs/PARAMETERS.md (generated)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from typing import Any


def P(default: Any, help: str, group: str = "general"):
    if isinstance(default, (list, dict)):
        return field(default_factory=lambda d=default: json.loads(json.dumps(d)), metadata={"help": help, "group": group})
    return field(default=default, metadata={"help": help, "group": group})


@dataclass
class CateryaConfig:
    # general
    seed: int = P(1337, "Master seed; all sub-seeds derive from it.")
    hash_algo: str = P("sha256", "Content hash: sha256 or sha3-256.")
    home: str = P(".caterya", "State directory (store, keys).")
    access_mode: str = P("black_box", "black_box | gray_box | white_box. Black-box first.")
    depth: str = P("standard", "Evaluation depth tier: light | standard | deep.")
    # statistics
    n_bootstrap: int = P(300, "Bootstrap resamples for 95% CIs.", "statistics")
    ci_level: float = P(0.95, "Confidence level.", "statistics")
    depth_light: float = P(0.5, "Sample multiplier for light tier.", "statistics")
    depth_standard: float = P(1.0, "Sample multiplier for standard tier.", "statistics")
    depth_deep: float = P(3.0, "Sample multiplier for deep tier.", "statistics")
    # metrics
    entropy_k: int = P(5, "Samples per prompt for dispersion.", "metrics")
    entropy_temperature: float = P(0.8, "Sampling temperature for dispersion.", "metrics")
    symmetry_tau: float = P(0.8, "Similarity threshold for invariance (1-eps).", "metrics")
    lyapunov_steps: int = P(6, "Iterations in self-refinement trajectories.", "metrics")
    lyapunov_lambda_max: float = P(1.0, "Growth rate (per step) mapped to value 0.", "metrics")
    lyapunov_saturation: float = P(0.5, "Distance at which growth fit stops (saturation).", "metrics")
    perturbation_rate: float = P(0.15, "Per-word perturbation probability.", "metrics")
    fairness_max_gap: float = P(0.1, "Declared tolerable parity gap (reporting only).", "metrics")
    fairness_min_support: int = P(5, "Minimum rows for an intersectional subgroup.", "metrics")
    cos_weights: dict = P({"fairness": 0.25, "information": 0.25, "stability": 0.25, "transparency": 0.25},
                          "Pillar weights for the derived COS index.", "metrics")
    cos_gamma: float = P(0.25, "Exponent of Golden Triangle modulation.", "metrics")
    # risk
    risk_thresholds: list = P([0.1, 0.25, 0.5], "Upper bounds for LOW/MODERATE/HIGH; above = CRITICAL.", "risk")
    default_criticality: str = P("moderate", "low | moderate | high | critical.", "risk")
    default_exposure: float = P(0.5, "Exposure in [0,1].", "risk")
    # assurance
    ttl_days: int = P(90, "Validity of an assurance record (time-bound).", "assurance")
    min_coverage: float = P(0.8, "Fraction of profile metrics that must be measured.", "assurance")
    require_signature: bool = P(True, "Refuse levels >=2 without verified signatures.", "assurance")
    trusted_attesters: list = P([], "Key ids trusted for level-4 attestation.", "assurance")
    # regression / policy
    regression_min_effect: float = P(0.02, "Minimum delta reported as a change.", "regression")
    regression_max_drop: float = P(0.05, "Significant drop that fails the CI gate.", "regression")
    # monitoring
    drift_psi_warn: float = P(0.1, "PSI warning threshold.", "monitoring")
    drift_psi_alert: float = P(0.25, "PSI alert threshold.", "monitoring")
    ks_alpha: float = P(0.05, "KS significance level.", "monitoring")
    cusum_k: float = P(0.5, "CUSUM slack (in sigmas).", "monitoring")
    cusum_h: float = P(5.0, "CUSUM decision threshold (in sigmas).", "monitoring")
    deep_every_days: int = P(30, "Deep re-evaluation cadence.", "monitoring")
    canary_fraction: float = P(0.01, "Traffic fraction for canary evaluation.", "monitoring")
    guardrail_min_score: float = P(0.70, "If the guardrail window mean is below this during canary, plan() requests incident_replay. Research default, not a safety standard.", "monitoring")
    guardrail_window: int = P(20, "Rolling window (samples) for the guardrail score.", "monitoring")
    guardrail_min_samples: int = P(5, "Minimum guardrail samples before the window can alarm.", "monitoring")
    # sustainability (PLACEHOLDERS: set hardware/grid-specific values)
    joules_per_output_token: float = P(1.0, "Placeholder energy per generated token.", "sustainability")
    joules_per_input_token: float = P(0.3, "Placeholder energy per prompt token.", "sustainability")
    pue: float = P(1.2, "Data-centre power usage effectiveness.", "sustainability")
    grid_gco2_per_kwh: float = P(475.0, "Placeholder grid carbon intensity; set locally.", "sustainability")
    # capability flags
    enable_quantum: bool = P(False, "Quantum extension (capability flag, not product).", "capabilities")
    enable_chain_anchor: bool = P(False, "Anchor Merkle roots on an external ledger.", "capabilities")
    enable_zk: bool = P(False, "Zero-knowledge backend (interface only in v1).", "capabilities")
    # privacy / evidence
    default_visibility: str = P("public", "public | restricted | confidential | proprietary.", "privacy")
    include_raw_outputs: bool = P(False, "Export raw outputs in bundles (hash is always kept).", "privacy")
    # api
    host: str = P("127.0.0.1", "API bind host.", "api")
    port: int = P(8080, "API port.", "api")
    allowed_endpoints: list = P([], "Allowlist of base URLs for remote adapters (SSRF guard).", "api")

    def tier(self) -> float:
        return {"light": self.depth_light, "standard": self.depth_standard, "deep": self.depth_deep}.get(self.depth, 1.0)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CateryaConfig":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})

    @classmethod
    def from_env(cls, prefix: str = "CATERYA_", **over) -> "CateryaConfig":
        cfg = cls()
        for f in fields(cls):
            raw = os.environ.get(prefix + f.name.upper())
            if raw is None:
                continue
            cur = getattr(cfg, f.name)
            if isinstance(cur, bool):
                val: Any = raw.strip().lower() in ("1", "true", "yes", "on")
            elif isinstance(cur, int):
                val = int(raw)
            elif isinstance(cur, float):
                val = float(raw)
            elif isinstance(cur, (list, dict)):
                val = json.loads(raw)
            else:
                val = raw
            setattr(cfg, f.name, val)
        for k, v in over.items():
            setattr(cfg, k, v)
        return cfg

    @classmethod
    def describe(cls) -> list[dict]:
        base = cls()
        return [{"name": f.name, "group": f.metadata.get("group", "general"), "default": getattr(base, f.name),
                 "help": f.metadata.get("help", ""), "env": "CATERYA_" + f.name.upper()} for f in fields(cls)]


def detect_capabilities(cfg: CateryaConfig | None = None) -> dict:
    import importlib.util as u
    cfg = cfg or CateryaConfig()
    has = lambda m: u.find_spec(m) is not None  # noqa: E731
    return {
        "ed25519_signatures": has("cryptography"),
        "numpy": has("numpy"),
        "fastapi": has("fastapi"),
        "yaml": has("yaml"),
        "quantum": {"enabled": cfg.enable_quantum, "pennylane": has("pennylane"), "qiskit": has("qiskit"), "qiskit_aer": has("qiskit_aer")},
        "viz": {"plotly": has("plotly")},
        "chain_anchor": {"enabled": cfg.enable_chain_anchor, "backend": "file/null (ledger adapters: interface only)"},
        "zero_knowledge": {"enabled": cfg.enable_zk, "backend": "none (salted selective disclosure available)"},
        "hash_algos": ["sha256", "sha3-256"],
        "access_modes": ["black_box", "gray_box (adapter-dependent)", "white_box (adapter-dependent)"],
    }
