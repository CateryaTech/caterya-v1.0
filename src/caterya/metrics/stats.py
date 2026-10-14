from __future__ import annotations

import math
import random
from collections import Counter
from typing import Callable, Sequence


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def bootstrap_ci(rows: Sequence, stat: Callable[[Sequence], float] = mean, n_boot: int = 300,
                 level: float = 0.95, seed: int = 0) -> tuple[float, float]:
    """Percentile bootstrap over rows. n<2 carries no information -> (0,1)."""
    n = len(rows)
    if n < 2:
        return (0.0, 1.0)
    rng = random.Random(seed)
    vals = sorted(stat([rows[rng.randrange(n)] for _ in range(n)]) for _ in range(n_boot))
    a = (1 - level) / 2
    return (vals[int(a * (n_boot - 1))], vals[int((1 - a) * (n_boot - 1))])


def shannon_entropy(counts: Sequence[float]) -> float:
    tot = float(sum(counts))
    return -sum((c / tot) * math.log2(c / tot) for c in counts if c > 0) if tot else 0.0


def mutual_information(pairs: Sequence[tuple]) -> float:
    """Plug-in MI (bits) with Miller-Madow bias correction."""
    n = len(pairs)
    if n == 0:
        return 0.0
    pxy, px, py = Counter(pairs), Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    mi = sum(c / n * math.log2((c / n) / ((px[a] / n) * (py[b] / n))) for (a, b), c in pxy.items())
    corr = (len(px) - 1) * (len(py) - 1) / (2 * n * math.log(2))
    return max(0.0, mi - corr)


def ece(confs: Sequence[float], correct: Sequence[bool], bins: int = 10) -> float:
    n = len(confs)
    if n == 0:
        return 0.0
    tot = 0.0
    for b in range(bins):
        idx = [i for i, c in enumerate(confs) if (c > b / bins or b == 0) and c <= (b + 1) / bins]
        if idx:
            tot += len(idx) / n * abs(mean([confs[i] for i in idx]) - mean([1.0 if correct[i] else 0.0 for i in idx]))
    return tot


def auroc(pos: Sequence[float], neg: Sequence[float]) -> float:
    if not pos or not neg:
        return float("nan")
    wins = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return wins / (len(pos) * len(neg))


def _rank(xs: Sequence[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    rx, ry = _rank(x), _rank(y)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")
