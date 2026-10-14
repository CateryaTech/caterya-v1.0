"""Optional external anchoring of tree heads. 'Cryptographic provenance first; blockchain when justified.'"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from ..core.errors import CapabilityUnavailable


class Anchor(ABC):
    name = "anchor"

    @abstractmethod
    def publish(self, sth: dict) -> dict: ...


class NullAnchor(Anchor):
    name = "null"

    def publish(self, sth: dict) -> dict:
        return {"anchor": "none"}


class FileAnchor(Anchor):
    """Appends tree heads to a file (e.g. a public git repo or object store) — simple, auditable."""
    name = "file"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def publish(self, sth: dict) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps({"size": sth["size"], "root": sth["root"], "timestamp": sth["timestamp"]}) + "\n")
        return {"anchor": "file", "path": str(self.path)}


class LedgerAnchor(Anchor):
    """Interface for public ledgers / RFC 3161 TSAs. Implement `publish`; gated by enable_chain_anchor."""
    name = "ledger"

    def publish(self, sth: dict) -> dict:
        raise CapabilityUnavailable("implement LedgerAnchor.publish for your ledger or timestamp authority")
