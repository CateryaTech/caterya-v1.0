"""Seal a regulatory mapping as Evidence after the other records exist."""
from __future__ import annotations

from typing import Optional

from ..core.clock import iso, utcnow
from ..evidence.model import Evidence
from ..guardrails.evidence import seal_decision
from ..provenance.signing import Signer
from .mapping import coverage_fraction, map_evidence


def seal_mapping(
    evidences: list,
    signer: Signer,
    *,
    framework: Optional[str] = None,
    prev_hash: str = "",
    system_hash: str = "",
    profile: str = "",
    mode: str = "pre_release",
    seed: int = 0,
    timestamp: Optional[str] = None,
) -> Evidence:
    """Map ``evidences`` and seal the coverage fraction.

    The claim states that the number is mapping coverage. The full clause table
    is in the Evidence context. This function does not certify anything.
    """
    mapped = map_evidence(evidences, framework)
    cover = coverage_fraction(mapped)
    return seal_decision(
        signer,
        metric_id="regulatory_mapping_v1",
        value=cover["fraction_evidenced"],
        claim="technical regulatory mapping coverage; not legal advice or certification",
        details={"mapping": mapped["mapping"], "frameworks": mapped["frameworks"], "coverage": cover, "framework_filter": framework},
        limitations=list(cover["limitations"]) + [mapped["disclaimer"]],
        prev_hash=prev_hash,
        system_hash=system_hash,
        profile=profile,
        mode=mode,
        seed=seed,
        n=cover["normative"],
        untested=None if cover["fraction_evidenced"] is not None else "no normative clauses",
        timestamp=timestamp or iso(utcnow()),
    )
