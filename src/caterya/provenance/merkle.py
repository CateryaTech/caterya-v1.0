"""RFC 6962/9162-style Merkle tree (domain-separated leaves/nodes) with inclusion proofs."""
from __future__ import annotations

import hashlib


def _h(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def leaf_hash(data: bytes) -> bytes:
    return _h(b"\x00" + data)


def node_hash(l: bytes, r: bytes) -> bytes:
    return _h(b"\x01" + l + r)


def _split(n: int) -> int:
    return 1 << ((n - 1).bit_length() - 1)


def mth(leaves: list[bytes]) -> bytes:
    n = len(leaves)
    if n == 0:
        return _h(b"")
    if n == 1:
        return leaves[0]
    k = _split(n)
    return node_hash(mth(leaves[:k]), mth(leaves[k:]))


def audit_path(m: int, leaves: list[bytes]) -> list[bytes]:
    n = len(leaves)
    if n <= 1:
        return []
    k = _split(n)
    if m < k:
        return audit_path(m, leaves[:k]) + [mth(leaves[k:])]
    return audit_path(m - k, leaves[k:]) + [mth(leaves[:k])]


def verify_inclusion(leaf: bytes, index: int, size: int, proof: list[bytes], root: bytes) -> bool:
    if index >= size:
        return False
    fn, sn, r = index, size - 1, leaf
    for p in proof:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            r = node_hash(p, r)
            if not fn & 1:
                while not fn & 1 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            r = node_hash(r, p)
        fn >>= 1
        sn >>= 1
    return sn == 0 and r == root


class MerkleTree:
    def __init__(self, items: list[bytes] | None = None):
        self.leaves: list[bytes] = [leaf_hash(i) for i in (items or [])]

    def append(self, item: bytes) -> int:
        self.leaves.append(leaf_hash(item))
        return len(self.leaves) - 1

    def root(self, size: int | None = None) -> bytes:
        return mth(self.leaves if size is None else self.leaves[:size])

    def proof(self, index: int) -> list[bytes]:
        return audit_path(index, self.leaves)

    def __len__(self) -> int:
        return len(self.leaves)
