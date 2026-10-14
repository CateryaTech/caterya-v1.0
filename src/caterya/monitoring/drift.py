from __future__ import annotations

import math
from typing import Sequence

from ..metrics.stats import mean


def psi(expected: Sequence[float], actual: Sequence[float], bins: int = 10) -> float:
    """Population Stability Index on quantile bins of the baseline."""
    e = sorted(expected)
    if not e or not actual:
        return 0.0
    bins = max(2, min(bins, len(actual) // 5, len(e) // 5))   # sparse bins make PSI meaningless
    cuts = [e[min(len(e) - 1, int(len(e) * i / bins))] for i in range(1, bins)]

    def hist(xs):
        c = [0] * bins
        for x in xs:
            c[sum(1 for t in cuts if x > t)] += 1
        return [max(v / len(xs), 1e-4) for v in c]

    pe, pa = hist(expected), hist(actual)
    return sum((a - b) * math.log(a / b) for a, b in zip(pa, pe))


def ks(a: Sequence[float], b: Sequence[float]) -> tuple[float, float]:
    """Two-sample Kolmogorov–Smirnov statistic and asymptotic p-value."""
    a, b = sorted(a), sorted(b)
    n, m = len(a), len(b)
    if not n or not m:
        return 0.0, 1.0
    i = j = 0
    d = 0.0
    while i < n and j < m:
        x = min(a[i], b[j])
        while i < n and a[i] <= x:
            i += 1
        while j < m and b[j] <= x:
            j += 1
        d = max(d, abs(i / n - j / m))
    lam = (math.sqrt(n * m / (n + m)) + 0.12 + 0.11 / math.sqrt(n * m / (n + m))) * d
    p = 2 * sum((-1) ** (k - 1) * math.exp(-2 * k * k * lam * lam) for k in range(1, 101))
    return d, max(0.0, min(1.0, p))


def cusum(xs: Sequence[float], mu: float, sigma: float, k: float = 0.5, h: float = 5.0) -> int | None:
    """One-sided (downward) CUSUM; returns first alarm index or None. sigma floor avoids div-by-zero."""
    s, sg = 0.0, max(sigma, 1e-6)
    for i, x in enumerate(xs):
        s = max(0.0, s + (mu - x) / sg - k)
        if s > h:
            return i
    return None


def std(xs: Sequence[float]) -> float:
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / max(1, len(xs) - 1))
