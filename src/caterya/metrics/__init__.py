"""Importing this package registers every built-in metric."""
from ..guardrails import metrics as _guardrail_metrics  # noqa: E402,F401
from ..quantum import metrics as _quantum_metrics  # noqa: E402,F401
from . import (  # noqa: F401
    agentic,
    dispersion,
    energy_map,
    fairness,
    operational,
    privacy,
    regulatory_metric,
    reliability,
    robustness,
    safety,
    stability,
)
from .base import Metric, MetricResult, MetricSpec  # noqa: F401
