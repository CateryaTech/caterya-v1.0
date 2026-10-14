from __future__ import annotations

import platform
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

from .canonical import digest, short


def capture_environment() -> dict:
    from .. import __version__
    return {"python": sys.version.split()[0], "platform": platform.platform(), "caterya": __version__}


@dataclass
class SystemDescriptor:
    """The unit of evaluation: model + tools + memory + policies + deployment (model != system)."""
    name: str
    version: str = "0.0.0"
    kind: str = "model"
    provider: str = "unknown"
    model_id: str = ""
    model_version: str = ""
    tools: list = field(default_factory=list)
    memory: dict = field(default_factory=dict)
    policies: list = field(default_factory=list)
    config: dict = field(default_factory=dict)
    code_hash: str = ""
    environment: dict = field(default_factory=dict)      # declared runtime of the system under test
    dataset_hashes: dict = field(default_factory=dict)   # training/eval data fingerprints, if disclosed
    organization: str = ""
    access_mode: str = "black_box"
    deployment: dict = field(default_factory=lambda: {
        "environment": "dev", "use_case": "", "jurisdiction": "", "sector": "general",
        "criticality": "moderate", "exposure": 0.5})

    def fingerprint(self) -> dict:
        d = asdict(self)
        for k in ("deployment", "organization", "access_mode"):
            d.pop(k)
        return d

    def fingerprint_hash(self, algo: str = "sha256") -> str:
        return digest(self.fingerprint(), algo)

    @property
    def id(self) -> str:
        return "SYS-" + short(self.fingerprint_hash(), 12)

    def completeness(self) -> tuple[float, list[str]]:
        checks = {
            "name": bool(self.name), "version": self.version not in ("", "0.0.0"),
            "provider": self.provider not in ("", "unknown"), "model_id": bool(self.model_id),
            "model_version": bool(self.model_version), "code_hash": bool(self.code_hash),
            "environment": bool(self.environment), "dataset_hashes": bool(self.dataset_hashes),
        }
        missing = [k for k, ok in checks.items() if not ok]
        return 1 - len(missing) / len(checks), missing

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SystemDescriptor":
        names = set(cls.__dataclass_fields__)
        obj = cls(**{k: v for k, v in d.items() if k in names})
        return obj

    def to_dict(self) -> dict:
        return asdict(self)


SystemConfig = SystemDescriptor
