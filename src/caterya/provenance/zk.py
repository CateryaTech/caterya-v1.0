"""Privacy primitives. HONEST SCOPE: salted commitments + Merkle selective disclosure are provided.
They are NOT zero-knowledge proofs. `ZKBackend` is an interface for future proof systems."""
from __future__ import annotations

import hashlib
import secrets
from typing import Any

from ..core.canonical import canonical_bytes
from ..core.errors import CapabilityUnavailable
from .merkle import MerkleTree, leaf_hash, verify_inclusion


def commit(value: Any, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    return hashlib.sha256(salt + canonical_bytes(value)).hexdigest(), salt.hex()


def open_commitment(commitment: str, value: Any, salt_hex: str) -> bool:
    return hashlib.sha256(bytes.fromhex(salt_hex) + canonical_bytes(value)).hexdigest() == commitment


class SelectiveDisclosure:
    """Commit to every field of a record; reveal only chosen fields with Merkle proofs."""

    def __init__(self, record: dict):
        self.keys = sorted(record)
        self.salts = {k: secrets.token_bytes(16) for k in self.keys}
        self._leaves = [self._leaf(k, record[k]) for k in self.keys]
        self.tree = MerkleTree(self._leaves)
        self.record = record

    def _leaf(self, k: str, v: Any) -> bytes:
        return self.salts[k] + canonical_bytes([k, v])

    @property
    def root(self) -> str:
        return self.tree.root().hex()

    def reveal(self, fields: list[str]) -> list[dict]:
        out = []
        for k in fields:
            i = self.keys.index(k)
            out.append({"field": k, "value": self.record[k], "salt": self.salts[k].hex(), "index": i,
                        "size": len(self.keys), "path": [p.hex() for p in self.tree.proof(i)]})
        return out


def verify_disclosure(root: str, rev: dict) -> bool:
    leaf = bytes.fromhex(rev["salt"]) + canonical_bytes([rev["field"], rev["value"]])
    return verify_inclusion(leaf_hash(leaf), rev["index"], rev["size"], [bytes.fromhex(p) for p in rev["path"]],
                            bytes.fromhex(root))


class ZKBackend:
    name = "none"

    def prove(self, statement: dict, witness: dict) -> bytes:
        raise CapabilityUnavailable("no zero-knowledge backend configured (interface only in v1)")

    def verify(self, statement: dict, proof: bytes) -> bool:
        raise CapabilityUnavailable("no zero-knowledge backend configured (interface only in v1)")
