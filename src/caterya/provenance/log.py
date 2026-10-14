"""Append-only transparency log (Certificate-Transparency style) with signed tree heads."""
from __future__ import annotations

from ..core.canonical import canonical_bytes
from ..core.clock import Clock, iso, utcnow
from .merkle import MerkleTree, leaf_hash, verify_inclusion
from .signing import Signer, Verifier


class TransparencyLog:
    def __init__(self, signer: Signer, leaves: list[str] | None = None, clock: Clock = utcnow):
        self.signer, self.clock = signer, clock
        self.items: list[str] = list(leaves or [])        # hex content hashes
        self.tree = MerkleTree([i.encode() for i in self.items])

    def append(self, content_hash: str) -> int:
        self.items.append(content_hash)
        return self.tree.append(content_hash.encode())

    def signed_tree_head(self) -> dict:
        body = {"size": len(self.tree), "root": self.tree.root().hex(), "timestamp": iso(self.clock()),
                "key_id": self.signer.key_id}
        return {**body, "signature": self.signer.sign(canonical_bytes(body))}

    def inclusion_proof(self, index: int) -> dict:
        return {"index": index, "size": len(self.tree), "leaf": self.items[index],
                "path": [p.hex() for p in self.tree.proof(index)], "root": self.tree.root().hex()}

    def check_consistency(self, old_sth: dict) -> bool:
        n = old_sth["size"]
        return n <= len(self.tree) and self.tree.root(n).hex() == old_sth["root"]


def verify_sth(sth: dict, verifier: Verifier) -> bool:
    body = {k: sth[k] for k in ("size", "root", "timestamp", "key_id")}
    return verifier.verify(canonical_bytes(body), sth["signature"])


def verify_inclusion_proof(p: dict) -> bool:
    return verify_inclusion(leaf_hash(p["leaf"].encode()), p["index"], p["size"],
                            [bytes.fromhex(x) for x in p["path"]], bytes.fromhex(p["root"]))
