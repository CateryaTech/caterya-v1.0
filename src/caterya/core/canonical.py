"""Canonical serialisation and content addressing.

Canonical form = JSON with sorted keys, no insignificant whitespace, UTF-8.
This is close to, but NOT a full implementation of, RFC 8785 (JCS): floats use
Python's shortest round-trip repr. Hashes are therefore stable for a given
spec version across CPython platforms; cross-language implementers should
follow docs/SPEC_EVIDENCE.md.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

ALGOS = {"sha256": hashlib.sha256, "sha3-256": hashlib.sha3_256}


def jsonable(o: Any) -> Any:
    if is_dataclass(o) and not isinstance(o, type):
        return jsonable(asdict(o))
    if isinstance(o, Enum):
        return o.value
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set, frozenset)):
        seq = sorted(o, key=repr) if isinstance(o, (set, frozenset)) else o
        return [jsonable(x) for x in seq]
    if isinstance(o, float):
        if math.isnan(o) or math.isinf(o):
            raise ValueError("NaN/Inf are not allowed in canonical JSON")
        return o
    if isinstance(o, bytes):
        return o.hex()
    return o


def canonical_bytes(o: Any) -> bytes:
    return json.dumps(jsonable(o), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def hex_digest(data: bytes, algo: str = "sha256") -> str:
    try:
        return ALGOS[algo](data).hexdigest()
    except KeyError as e:
        raise ValueError(f"unsupported hash algorithm: {algo}") from e


def digest(o: Any, algo: str = "sha256") -> str:
    """Content address of any JSON-able object: '<algo>:<hex>'."""
    data = o if isinstance(o, bytes) else canonical_bytes(o)
    return f"{algo}:{hex_digest(data, algo)}"


def short(d: str, n: int = 12) -> str:
    return d.split(":", 1)[-1][:n]


def derive_seed(*parts: Any) -> int:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(h[:8], "big")


def hashfrac(*parts: Any) -> float:
    """Deterministic uniform [0,1) from arbitrary parts."""
    return derive_seed(*parts) / 2**64
