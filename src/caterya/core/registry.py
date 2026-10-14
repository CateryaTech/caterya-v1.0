from __future__ import annotations

from typing import Any

from .errors import ConfigError

METRICS: dict[str, type] = {}


def register_metric(cls):
    METRICS[cls.spec.id] = cls
    return cls


def _load() -> None:
    import caterya.metrics  # noqa: F401  (registers all built-ins)


def get_metric(metric_id: str, **params: Any):
    _load()
    try:
        return METRICS[metric_id](**params)
    except KeyError as e:
        raise ConfigError(f"unknown metric: {metric_id}") from e


def list_metrics() -> list:
    _load()
    return [c.spec for c in METRICS.values()]
