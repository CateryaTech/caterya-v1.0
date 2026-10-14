from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Optional

from ..core.canonical import digest
from ..core.context import EvalContext
from ..core.types import Domain


@dataclass(frozen=True)
class MetricSpec:
    """Operational definition of a metric. Its hash is stored in every Evidence record."""
    id: str
    domain: Domain
    title: str
    description: str
    formula: str
    kind: str = "score"                    # score = [0,1] higher is more trustworthy; quantity = informational
    unit: str = "score[0,1]"
    access: str = "black_box"
    status: str = "experimental"           # stable | experimental | research
    pillar: str = ""                       # fairness | information | stability | transparency (COS pillars)
    golden: str = ""                       # entropy | symmetry | information (Golden Triangle terms)
    assumptions: tuple = ()
    limitations: tuple = ()

    def spec_hash(self) -> str:
        return digest(self)


@dataclass
class MetricResult:
    metric_id: str
    value: Optional[float]
    ci95: Optional[tuple] = None
    n: int = 0
    details: dict = field(default_factory=dict)
    limitations: list = field(default_factory=list)
    unit: str = "score[0,1]"
    untested_reason: Optional[str] = None
    dataset_hash: str = ""
    dataset_hashes: dict = field(default_factory=dict)
    raw_outputs_hash: str = ""
    seed: int = 0
    params: dict = field(default_factory=dict)
    duration_s: float = 0.0
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0


class Metric:
    spec: ClassVar[MetricSpec]
    DEFAULTS: ClassVar[dict] = {}

    def __init__(self, **params: Any):
        self.p = {**self.DEFAULTS, **params}

    def compute(self, ctx: EvalContext) -> MetricResult:  # pragma: no cover - abstract
        raise NotImplementedError

    def result(self, value: Optional[float], ci: Optional[tuple] = None, n: int = 0, **details: Any) -> MetricResult:
        v = None if value is None else max(0.0, min(1.0, value)) if self.spec.kind == "score" else value
        return MetricResult(self.spec.id, v, tuple(ci) if ci else None, n, details,
                            list(self.spec.limitations), self.spec.unit)

    def untested(self, reason: str) -> MetricResult:
        r = self.result(None)
        r.untested_reason = reason
        return r

    def run(self, ctx: EvalContext) -> MetricResult:
        ctx.begin()
        t0 = time.perf_counter()
        r = self.compute(ctx)
        r.duration_s = time.perf_counter() - t0
        r.dataset_hash, r.dataset_hashes = ctx.dataset_hash(), ctx.dataset_hashes()
        r.raw_outputs_hash, r.seed, r.params = ctx.raw_hash(), ctx.seed, dict(self.p)
        r.calls, r.tokens_in, r.tokens_out = ctx.calls, ctx.tokens_in, ctx.tokens_out
        if ctx.errors:
            r.details["adapter_errors"] = ctx.errors
            r.limitations.append(f"{ctx.errors} adapter call(s) failed and were counted as empty outputs")
        return r
