from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

Clock = Callable[[], datetime]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


class FixedClock:
    """Deterministic clock for tests and reproducible runs."""

    def __init__(self, start: str = "2026-10-11T00:00:00.000000Z", step_s: float = 1.0):
        self._t = parse_iso(start)
        self._step = timedelta(seconds=step_s)

    def __call__(self) -> datetime:
        t = self._t
        self._t = t + self._step
        return t
