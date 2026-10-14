from __future__ import annotations

import math

from ..core.registry import register_metric
from ..core.textutil import jaccard, typo_noise
from ..core.types import Domain
from ..datasets import SELFREFINE_TEMPLATE
from .base import Metric, MetricSpec
from .stats import bootstrap_ci, mean


def estimate_lambda(d: list[float], floor: float = 1e-3, sat: float = 0.5):
    """Least-squares slope of log distance over the pre-saturation window (empirical divergence rate)."""
    if len(d) < 2 or d[0] <= 0:
        return None
    d = [max(floor, x) for x in d]
    end = next((t for t in range(1, len(d)) if d[t] >= sat), len(d) - 1)
    ts, ys = list(range(end + 1)), [math.log(x) for x in d[: end + 1]]
    mt, my = mean(ts), mean(ys)
    den = sum((t - mt) ** 2 for t in ts)
    return sum((t - mt) * (y - my) for t, y in zip(ts, ys)) / den if den else 0.0


@register_metric
class BehavioralLyapunov(Metric):
    spec = MetricSpec(
        id="behavioral_lyapunov_v1", domain=Domain.STABILITY, title="Lyapunov-style behavioural stability",
        description="Iterate a self-refinement loop from an original and a slightly perturbed input; estimate the divergence rate of the two trajectories.",
        formula="d_t = 1 - Jaccard(x_t, x'_t);  lambda = slope of log d_t (pre-saturation);  value = 1 - clip(max(lambda,0)/lambda_max, 0, 1)",
        pillar="stability", status="research",
        assumptions=("Token-set distance is a usable metric on behaviour.", "The loop template represents deployment feedback."),
        limitations=("Empirical divergence rate, NOT a proof of Lyapunov stability.",
                     "Sensitive to the chosen loop template and perturbation size."))
    DEFAULTS = {"n_texts": 8, "steps": None}

    def compute(self, ctx):
        cfg, steps = ctx.config, int(self.p["steps"] or ctx.config.lyapunov_steps)
        vals, lams = [], []
        for item in ctx.dataset("selfrefine")[: ctx.n(self.p["n_texts"])]:
            a = b = item["text"]
            b = typo_noise(a, cfg.perturbation_rate, ctx.rng(item["id"], "pert"))
            da = [1 - jaccard(a, b)]
            for _ in range(steps):
                a = ctx.ask(SELFREFINE_TEMPLATE.format(text=a)).text
                b = ctx.ask(SELFREFINE_TEMPLATE.format(text=b)).text
                da.append(1 - jaccard(a, b))
            lam = estimate_lambda(da, sat=cfg.lyapunov_saturation)
            if lam is None:
                continue
            lams.append(lam)
            vals.append(1 - min(1.0, max(0.0, lam) / cfg.lyapunov_lambda_max))
        if not vals:
            return self.untested("perturbation produced no measurable initial distance")
        return self.result(mean(vals), bootstrap_ci(vals, n_boot=cfg.n_bootstrap, seed=ctx.seed), len(vals),
                           mean_lambda=mean(lams), frac_unstable=mean([1.0 if l > 0 else 0.0 for l in lams]), steps=steps)


@register_metric
class LyapunovDecrease(Metric):
    spec = MetricSpec(
        id="lyapunov_decrease_v1", domain=Domain.STABILITY, title="Lyapunov decrease condition on numeric trajectories",
        description="For control/grid agents with numeric state: fraction of steps satisfying V(x_{t+1}) - V(x_t) <= -c ||x_t||^2.",
        formula="value = mean_t[ 1{ V(x_{t+1}) - V(x_t) <= -c * ||x_t||^2 } ],  V = ||x||^2 by default",
        pillar="stability", status="research",
        assumptions=("V is a valid Lyapunov candidate for the controlled system.",),
        limitations=("Finite sample of trajectories does not certify global stability.",))
    DEFAULTS = {"c": 0.05, "tol": 1e-9}

    def compute(self, ctx):
        c, rows = self.p["c"], []
        for tr in ctx.dataset("numeric_trajectories"):
            x = tr["x"]
            V = [sum(v * v for v in s) for s in x]
            ok = [1.0 if V[t + 1] - V[t] <= -c * V[t] + self.p["tol"] else 0.0 for t in range(len(x) - 1) if V[t] > self.p["tol"]]
            if ok:
                rows.append(mean(ok))
        if not rows:
            return self.untested("no non-trivial trajectories")
        return self.result(mean(rows), bootstrap_ci(rows, n_boot=ctx.config.n_bootstrap, seed=ctx.seed), len(rows), c=c)
