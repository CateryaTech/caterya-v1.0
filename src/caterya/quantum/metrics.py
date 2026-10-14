"""Quantum-extension metrics. Each one is research-grade and becomes Evidence when the runner seals it.

Missing inputs stay ``NOT TESTED``. They are never filled with a perfect score.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.registry import register_metric
from ..core.types import Domain
from ..metrics.base import Metric, MetricResult, MetricSpec
from ..metrics.stats import bootstrap_ci, mean
from .backend import fidelity, get_backend, von_neumann_entropy_of_reduced
from .entropy import entanglement_from_rates
from .symmetry import attributes_of, evaluate_rows, group_rates
from .types import CircuitSpec

_QSI_LIMITS = (
    "Research-grade. On an ideal simulator the value is a function of the encoded positive rates only.",
    "Circuit form is variational (RY, CNOT ladder, RZ) but angles are a deterministic function of the rates, not a trained optimum.",
    "Not a certificate of fairness, safety, or legal compliance. Demographic parity is one incompatible criterion among several.",
    "Shot noise, when requested, is reported beside the statevector value and does not replace it.",
    "Equal rates, including the all-zero rate vector, score near 1 by construction of the reference state.",
)


def _rows_for_symmetry(ctx) -> Optional[list]:
    if ctx.has_dataset("quantum_fairness"):
        return list(ctx.dataset("quantum_fairness"))
    if ctx.has_dataset("tabular_predictions"):
        return list(ctx.dataset("tabular_predictions"))
    return None


def _attach(result: MetricResult, extra_limits: list[str], details: dict[str, Any]) -> MetricResult:
    for note in extra_limits:
        if note not in result.limitations:
            result.limitations.append(note)
    result.details.update(details)
    return result


@register_metric
class QuantumSymmetryIndex(Metric):
    """Swap-test symmetry of group positive rates. See ``caterya.quantum.symmetry``."""

    spec = MetricSpec(
        id="quantum_symmetry_index_v1",
        domain=Domain.FAIRNESS,
        title="Quantum-encoded symmetry index (swap test)",
        description=(
            "Fidelity between a data-encoded group-rate state and the equal-rate reference, "
            "estimated by a swap test on a named backend."
        ),
        formula="value = mean_a (2 P_a(ancilla=0) - 1), statevector when available",
        pillar="fairness",
        golden="symmetry",
        status="research",
        access="black_box",
        assumptions=(
            "y_pred is a binary favourable-outcome indicator in {0,1}.",
            "Group labels are accurate.",
            "The published circuit, not a hidden ansatz, is what was executed.",
        ),
        limitations=_QSI_LIMITS,
    )
    DEFAULTS = {"backend": "classical", "shots": 0, "min_support": None, "remote": None}

    def compute(self, ctx) -> MetricResult:
        rows = _rows_for_symmetry(ctx)
        if rows is None:
            return self.untested("dataset 'quantum_fairness' or 'tabular_predictions' not provided")
        min_support = self.p["min_support"] if self.p["min_support"] is not None else ctx.config.fairness_min_support
        noise = self.p.get("noise")
        try:
            payload = evaluate_rows(
                rows,
                backend=str(self.p["backend"]),
                shots=int(self.p["shots"]),
                seed=ctx.seed,
                noise=noise,
                remote=self.p.get("remote"),
                min_support=int(min_support),
            )
        except Exception as exc:
            return self.untested(f"{type(exc).__name__}: {exc}")
        if payload.get("value") is None:
            return self.untested(payload.get("untested") or "symmetry index not measured")

        def stat(sample: list) -> float:
            again = evaluate_rows(
                sample,
                backend=str(self.p["backend"]),
                shots=0,
                seed=ctx.seed,
                noise=None,
                remote=None,
                min_support=int(min_support),
            )
            return 0.0 if again.get("value") is None else float(again["value"])

        n_boot = min(int(ctx.config.n_bootstrap), 80)
        ci = bootstrap_ci(rows, stat, n_boot=n_boot, seed=ctx.seed) if len(rows) >= 2 else None
        summary = {}
        for name, item in payload["per_attribute"].items():
            summary[name] = {
                "value": item.get("value"),
                "shot_estimate": item.get("shot_estimate"),
                "circuit_hash": item.get("circuit_hash"),
                "groups": item.get("groups"),
                "rates": item.get("rates"),
                "suppressed_small_groups": item.get("suppressed_small_groups"),
                "value_source": item.get("value_source"),
                "backend": (item.get("backend") or {}).get("backend"),
                "backend_version": (item.get("backend") or {}).get("backend_version"),
                "shots": (item.get("backend") or {}).get("shots"),
                "noise_model": (item.get("backend") or {}).get("noise_model"),
                "method": (item.get("backend") or {}).get("method"),
            }
        first = next(iter(payload["per_attribute"].values()))
        meta = first.get("backend") or {}
        result = self.result(float(payload["value"]), ci, len(rows), per_attribute=summary, n_boot=n_boot)
        extra = list(payload.get("limitations") or [])
        if n_boot < ctx.config.n_bootstrap:
            extra.append(f"Bootstrap capped at {n_boot} resamples (each resample re-runs the statevector).")
        extra.append("Confidence interval resamples rows and re-runs the exact statevector; it does not include shot noise.")
        return _attach(result, extra, {
            "circuit_hash": first.get("circuit_hash"),
            "backend": meta.get("backend", self.p["backend"]),
            "backend_version": meta.get("backend_version"),
            "shots": meta.get("shots", self.p["shots"]),
            "noise_model": meta.get("noise_model"),
            "noise_applied_to": meta.get("noise_applied_to"),
            "method": meta.get("method"),
            "value_source": first.get("value_source"),
        })


@register_metric
class QuantumFidelity(Metric):
    spec = MetricSpec(
        id="quantum_fidelity_v1",
        domain=Domain.STABILITY,
        title="Distribution fidelity between two backends or supplied distributions",
        description=(
            "Bhattacharyya fidelity between outcome distributions. Supplied pairs are accepted. "
            "A dataset of circuits is executed on two named backends; a missing backend is not replaced."
        ),
        formula="value = mean_i |sum_k sqrt(p_k q_k)|^2",
        status="research",
        access="white_box",
        pillar="stability",
        assumptions=("Outcome distributions are over the same computational-basis ordering (LSB-0).",),
        limitations=(
            "Z-basis distributions discard relative phase, so this is not full process fidelity.",
            "Needs paired distributions ('quantum_states') or executable circuits ('quantum_circuits').",
            "A backend that is not installed yields NOT TESTED for that record, not a classical substitute.",
            "Research-grade. Agreement of two simulators is not evidence about a physical device.",
        ),
    )
    DEFAULTS = {"shots": 0}

    def compute(self, ctx) -> MetricResult:
        vals: list[float] = []
        notes: list[str] = []
        metas: list[dict] = []
        if ctx.has_dataset("quantum_states"):
            for record in ctx.dataset("quantum_states"):
                vals.append(fidelity(record["p_classical"], record["p_quantum"]))
                metas.append({k: record.get(k) for k in ("circuit_hash", "backend", "backend_version", "shots", "noise_model")})
            notes.append("Distributions were supplied by the caller. This metric did not execute a circuit for those rows.")
        if ctx.has_dataset("quantum_circuits"):
            for record in ctx.dataset("quantum_circuits"):
                spec = CircuitSpec.from_dict(record["circuit"] if "circuit" in record else record)
                try:
                    left = get_backend(record.get("backend_a", "classical")).run(spec, shots=int(record.get("shots", self.p["shots"])), seed=ctx.seed, noise=record.get("noise"))
                    right = get_backend(record["backend_b"]).run(spec, shots=int(record.get("shots", self.p["shots"])), seed=ctx.seed, noise=record.get("noise"))
                except Exception as exc:
                    notes.append(f"{type(exc).__name__}: {exc}")
                    continue
                vals.append(fidelity(left.probabilities, right.probabilities))
                metas.append({
                    "circuit_hash": left.circuit_hash,
                    "backend": f"{left.backend}|{right.backend}",
                    "backend_version": f"{left.backend_version}|{right.backend_version}",
                    "shots": left.shots,
                    "noise_model": left.noise_model,
                    "method": f"{left.method}|{right.method}",
                })
        if not vals:
            reason = "dataset 'quantum_states' or 'quantum_circuits' not provided"
            if notes:
                reason = "; ".join(notes)
            return self.untested(reason)
        result = self.result(mean(vals), bootstrap_ci(vals, n_boot=min(ctx.config.n_bootstrap, 200), seed=ctx.seed), len(vals))
        first = metas[0] if metas else {}
        return _attach(result, notes, {
            "circuit_hash": first.get("circuit_hash"),
            "backend": first.get("backend"),
            "backend_version": first.get("backend_version"),
            "shots": first.get("shots", 0),
            "noise_model": first.get("noise_model"),
            "method": first.get("method", "supplied_distributions" if not ctx.has_dataset("quantum_circuits") else "executed"),
            "records": metas,
        })


@register_metric
class EntanglementEntropy(Metric):
    spec = MetricSpec(
        id="entanglement_entropy_v1",
        domain=Domain.STABILITY,
        title="Bipartite entanglement entropy",
        description=(
            "Von Neumann entropy of a reduced pure state. Supplied states use the caller's bipartition. "
            "Otherwise the observed symmetry register is prepared and cut in half."
        ),
        formula="E = -sum lambda_i log2 lambda_i over eigenvalues of the reduced density matrix",
        kind="quantity",
        unit="bits",
        status="research",
        access="white_box",
        pillar="stability",
        assumptions=("The input is a pure state, or the published observed-register circuit was executed.",),
        limitations=(
            "Informational; not a trustworthiness score. Higher is not better.",
            "Requires numpy. Remote shot backends do not yield this quantity.",
            "The half-register cut is a convention. It is not a device entanglement witness by itself.",
            "Supplied 'quantum_states' take precedence over the symmetry-register preparation.",
        ),
    )
    DEFAULTS = {"backend": "classical", "min_support": None}

    def compute(self, ctx) -> MetricResult:
        if ctx.has_dataset("quantum_states"):
            vals = [
                von_neumann_entropy_of_reduced([complex(a, b) for a, b in record["state"]], record["dim_a"], record["dim_b"])
                for record in ctx.dataset("quantum_states")
                if "state" in record
            ]
            if not vals:
                return self.untested("dataset 'quantum_states' has no 'state' entries")
            result = self.result(mean(vals), None, len(vals))
            return _attach(result, ["States were supplied by the caller; CATERYA did not prepare them."], {
                "circuit_hash": None,
                "backend": "supplied_state",
                "backend_version": None,
                "shots": 0,
                "noise_model": None,
                "method": "supplied_statevector",
            })
        rows = _rows_for_symmetry(ctx)
        if rows is None:
            return self.untested("dataset 'quantum_states' or 'quantum_fairness'/'tabular_predictions' not provided")
        min_support = self.p["min_support"] if self.p["min_support"] is not None else ctx.config.fairness_min_support
        attrs = attributes_of(rows)
        targets = attrs or [None]
        bits: list[float] = []
        details: dict[str, Any] = {}
        notes: list[str] = []
        try:
            for name in targets:
                rates, suppressed = group_rates(rows, attribute=name, min_support=int(min_support))
                payload = entanglement_from_rates(rates, backend=str(self.p["backend"]))
                key = name or "group"
                details[key] = {
                    "value": payload.get("value"),
                    "circuit_hash": payload.get("circuit_hash"),
                    "suppressed_small_groups": suppressed,
                    "untested": payload.get("untested"),
                }
                if payload.get("value") is not None:
                    bits.append(float(payload["value"]))
                notes.extend(payload.get("limitations") or [])
                if payload.get("untested"):
                    notes.append(str(payload["untested"]))
                if payload.get("backend"):
                    details["backend_meta"] = payload["backend"]
        except Exception as exc:
            return self.untested(f"{type(exc).__name__}: {exc}")
        if not bits:
            return self.untested(notes[-1] if notes else "entanglement entropy not measured")
        meta = details.get("backend_meta") or {}
        result = self.result(mean(bits), None, len(rows), per_attribute={k: v for k, v in details.items() if k != "backend_meta"})
        return _attach(result, notes, {
            "circuit_hash": next((v.get("circuit_hash") for v in details.values() if isinstance(v, dict) and v.get("circuit_hash")), None),
            "backend": meta.get("backend", self.p["backend"]),
            "backend_version": meta.get("backend_version"),
            "shots": meta.get("shots", 0),
            "noise_model": meta.get("noise_model"),
            "method": meta.get("method"),
        })
