"""Seal a guardrail or swarm decision as Evidence.

The record is a recommendation. It does not change an assurance disposition
and it does not block an agent framework by itself.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.clock import iso, utcnow
from ..core.registry import get_metric
from ..evidence.model import Evidence, seal_evidence, unsealed_from_result
from ..metrics.base import MetricResult
from ..provenance.signing import Signer


def seal_decision(
    signer: Signer,
    *,
    metric_id: str,
    value: Optional[float],
    claim: str,
    details: dict[str, Any],
    limitations: list[str],
    prev_hash: str = "",
    system_hash: str = "",
    profile: str = "",
    mode: str = "canary",
    seed: int = 0,
    n: int = 1,
    ci: Optional[tuple] = None,
    untested: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> Evidence:
    """Hash-chain and sign one decision.

    ``metric_id`` must be a registered spec so the spec hash matches ``docs/METRICS.md``.
    """
    spec = get_metric(metric_id).spec
    result = MetricResult(
        metric_id=spec.id,
        value=value,
        ci95=ci,
        n=n,
        details=details,
        limitations=list(spec.limitations) + [note for note in limitations if note not in spec.limitations],
        unit=spec.unit,
        untested_reason=untested,
        seed=seed,
    )
    ev = unsealed_from_result(
        result,
        spec,
        claim=claim,
        system_hash=system_hash,
        profile=profile,
        mode=mode,
        ts=timestamp or iso(utcnow()),
        evaluator=signer.identity(),
        visibility="public",
        extra_context={"guardrail": True},
    )
    return seal_evidence(ev, prev_hash, signer)
