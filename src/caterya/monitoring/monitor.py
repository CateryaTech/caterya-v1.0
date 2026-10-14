"""Observability: production behaviour signals -> drift/risk detection -> re-evaluation trigger (tiered depth)."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from ..core.clock import Clock, iso, parse_iso, utcnow
from ..core.config import CateryaConfig
from ..metrics.stats import mean
from .drift import cusum, ks, psi, std


@dataclass
class Alert:
    signal: str
    kind: str
    severity: str          # warn | alert
    value: float
    detail: str = ""


@dataclass
class ReEvalTrigger:
    depth: str             # light | deep
    reason: str
    mode: str = "post_release"
    alerts: list = field(default_factory=list)


class ContinuousMonitor:
    """Signals are higher-is-better behaviour scores (e.g. refusal rate on canary prompts, tool-error rate, eval pass rate)."""

    def __init__(self, cfg: CateryaConfig | None = None, clock: Clock = utcnow, baseline_n: int = 50, window: int = 50):
        self.cfg, self.clock, self.baseline_n, self.window = cfg or CateryaConfig(), clock, baseline_n, window
        self.series: dict[str, list[float]] = {}
        self.last_deep: Optional[str] = None
        self.last_fingerprint: Optional[str] = None

    def ingest(self, signal: str, value: float) -> None:
        self.series.setdefault(signal, []).append(float(value))

    def set_baseline(self, signal: str, values: list[float]) -> None:
        self.series[signal] = list(values)[: self.baseline_n]
        self.baseline_n = len(self.series[signal])

    def check(self) -> list[Alert]:
        c, alerts = self.cfg, []
        for name, xs in self.series.items():
            if len(xs) < self.baseline_n + 10:
                continue
            base, recent = xs[: self.baseline_n], xs[self.baseline_n:][-self.window:]
            i = cusum(xs[self.baseline_n:], mean(base), std(base), c.cusum_k, c.cusum_h)
            if i is not None:
                alerts.append(Alert(name, "cusum", "alert", float(i), f"downward shift detected at +{i} samples"))
            if len(recent) < 20:        # distribution tests need a minimum recent sample
                continue
            p = psi(base, recent)
            if p >= c.drift_psi_alert:
                alerts.append(Alert(name, "psi", "alert", p, f"PSI {p:.3f} >= {c.drift_psi_alert}"))
            elif p >= c.drift_psi_warn:
                alerts.append(Alert(name, "psi", "warn", p, f"PSI {p:.3f} >= {c.drift_psi_warn}"))
            d, pv = ks(base, recent)
            if pv < c.ks_alpha and d > 0.3:
                alerts.append(Alert(name, "ks", "alert" if d > 0.5 else "warn", d, f"KS D={d:.2f}, p={pv:.3g}"))
        alerts.extend(self.windowed_drift("guardrail_score"))
        return alerts

    def guardrail_window_values(self) -> list[float]:
        """Latest guardrail samples, or ``[]`` when the series is absent."""
        xs = self.series.get("guardrail_score", [])
        window = int(getattr(self.cfg, "guardrail_window", 20))
        return list(xs[-window:])

    def guardrail_window_mean(self) -> Optional[float]:
        """Mean of the latest window once ``guardrail_min_samples`` exist, else None."""
        xs = self.guardrail_window_values()
        need = int(getattr(self.cfg, "guardrail_min_samples", 5))
        if len(xs) < need:
            return None
        return mean(xs)

    def guardrail_breach(self) -> Optional[Alert]:
        """Alert when the window mean is below ``guardrail_min_score``. Does not invent samples."""
        score = self.guardrail_window_mean()
        if score is None:
            return None
        threshold = float(getattr(self.cfg, "guardrail_min_score", 0.70))
        if score >= threshold:
            return None
        return Alert("guardrail_score", "window_mean", "alert", score, f"window mean {score:.3f} < {threshold:.3f}")

    def on_guardrail(self, score: float, *, threshold: Optional[float] = None) -> Optional[ReEvalTrigger]:
        """Ingest one guardrail score and, if the window is already below threshold, request incident replay.

        The caller still has to run the deep evaluation. This method does not block traffic.
        """
        self.ingest("guardrail_score", score)
        if threshold is not None:
            previous = self.cfg.guardrail_min_score
            self.cfg.guardrail_min_score = float(threshold)
            try:
                breach = self.guardrail_breach()
            finally:
                self.cfg.guardrail_min_score = previous
        else:
            breach = self.guardrail_breach()
        if breach is None:
            return None
        self.last_deep = iso(self.clock())
        return ReEvalTrigger("deep", "canary guardrail score below threshold", "incident_replay", [breach])

    def window_pair(self, signal: str, window: Optional[int] = None) -> Optional[tuple[list[float], list[float]]]:
        """Previous window and latest window of equal length, or None if the series is shorter."""
        xs = self.series.get(signal, [])
        w = int(window or getattr(self.cfg, "guardrail_window", self.window))
        if w < 2 or len(xs) < 2 * w:
            return None
        return list(xs[-2 * w: -w]), list(xs[-w:])

    def windowed_drift(self, signal: str, window: Optional[int] = None) -> list[Alert]:
        """PSI/KS between the previous window and the latest window.

        Used for the guardrail series. Other signals keep the baseline comparison in :meth:`check`.
        """
        pair = self.window_pair(signal, window)
        if pair is None:
            return []
        previous, recent = pair
        alerts: list[Alert] = []
        p = psi(previous, recent)
        if p >= self.cfg.drift_psi_alert:
            alerts.append(Alert(signal, "window_psi", "alert", p, f"window PSI {p:.3f}"))
        elif p >= self.cfg.drift_psi_warn:
            alerts.append(Alert(signal, "window_psi", "warn", p, f"window PSI {p:.3f}"))
        d, pv = ks(previous, recent)
        if pv < self.cfg.ks_alpha and d > 0.3:
            alerts.append(Alert(signal, "window_ks", "alert" if d > 0.5 else "warn", d, f"window KS D={d:.2f}, p={pv:.3g}"))
        return alerts

    def plan(self, fingerprint: str | None = None) -> Optional[ReEvalTrigger]:
        """Light eval on every change; deep eval on alerts or when the deep cadence elapsed."""
        now, alerts = self.clock(), self.check()
        changed = bool(fingerprint) and self.last_fingerprint is not None and fingerprint != self.last_fingerprint
        if fingerprint:
            self.last_fingerprint = fingerprint        # first sighting is the baseline, not a change
        breach = self.guardrail_breach()
        if breach is not None:
            self.last_deep = iso(now)
            return ReEvalTrigger("deep", "canary guardrail score below threshold", "incident_replay", alerts + [breach])
        if any(a.severity == "alert" for a in alerts):
            self.last_deep = iso(now)
            return ReEvalTrigger("deep", "drift/risk alert", "drift", alerts)
        if self.last_deep is None or (now - parse_iso(self.last_deep)).days >= self.cfg.deep_every_days:
            self.last_deep = iso(now)
            return ReEvalTrigger("deep", "scheduled deep re-evaluation", "post_release", alerts)
        if changed:
            return ReEvalTrigger("light", "system fingerprint changed (model/tools/config)", "pre_release", alerts)
        return None

    def canary_sample(self, rng: random.Random) -> bool:
        return rng.random() < self.cfg.canary_fraction
