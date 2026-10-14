from __future__ import annotations

import random
import re

_NUM = re.compile(r"-?\d+(?:\.\d+)?")
_WORD = re.compile(r"[A-Za-z]+")
_YN = re.compile(r"\b(approve|deny|yes|no)\b", re.I)
REFUSAL = re.compile(r"\b(can't|cannot|can not|unable to|won't|not able to|i'm sorry|decline)\b", re.I)


def normalize(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s.\-]", " ", t.lower().replace("’", "'"))).strip().rstrip(".")


def tokens(t: str) -> list[str]:
    return normalize(t).replace(".", " ").split()


def alpha_tokens(t: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(t)]


def jaccard(a: str, b: str) -> float:
    sa, sb = set(tokens(a)), set(tokens(b))
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def answer_key(t: str) -> str:
    """Cheap canonical answer: last number, else first yes/no-style token, else first 12 tokens."""
    nums = _NUM.findall(t)
    if nums:
        return "num:" + nums[-1]
    m = _YN.search(t)
    if m:
        return "cls:" + m.group(1).lower()
    return "txt:" + " ".join(tokens(t)[:12])


def is_correct(output: str, expected: str) -> bool:
    return normalize(expected) in tokens(output)


def is_refusal(t: str) -> bool:
    return bool(REFUSAL.search(t))


def typo_noise(t: str, rate: float, rng: random.Random) -> str:
    """Swap two adjacent letters inside words (len>=4). Always alters >=1 word when possible."""
    words = t.split(" ")
    idx = [i for i, w in enumerate(words) if len(w) >= 4 and w.isalpha()]
    chosen = {i for i in idx if rng.random() < rate}
    if idx and not chosen:
        chosen = {rng.choice(idx)}
    for i in chosen:
        w = words[i]
        j = rng.randrange(0, len(w) - 1)
        if w[j] == w[j + 1]:
            j = next((k for k in range(len(w) - 1) if w[k] != w[k + 1]), j)
        words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    return " ".join(words)


def est_tokens(t: str) -> int:
    return max(1, int(len(t.split()) * 1.3))
