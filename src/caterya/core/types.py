"""Shared enumerations (architecture v1.0 §6, §8, §24)."""
from __future__ import annotations

from enum import Enum, IntEnum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class Domain(StrEnum):
    FAIRNESS = "fairness"
    INTERPRETABILITY = "interpretability"
    ROBUSTNESS = "robustness"
    SAFETY = "safety"
    SECURITY = "security"
    PRIVACY = "privacy"
    RELIABILITY = "reliability"
    STABILITY = "stability"
    SUSTAINABILITY = "sustainability"
    PROVENANCE = "provenance"
    AGENTIC = "agentic"


class Mode(StrEnum):
    BATCH = "batch"
    PRE_RELEASE = "pre_release"
    CANARY = "canary"
    POST_RELEASE = "post_release"
    INCIDENT_REPLAY = "incident_replay"
    DRIFT = "drift"


class AccessMode(StrEnum):
    BLACK_BOX = "black_box"
    GRAY_BOX = "gray_box"
    WHITE_BOX = "white_box"


class Visibility(StrEnum):
    PUBLIC = "public"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"
    PROPRIETARY = "proprietary"


class Disposition(StrEnum):
    EVALUATED = "EVALUATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CONDITIONALLY_ASSURED = "CONDITIONALLY_ASSURED"
    ASSURED = "ASSURED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class RiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class SystemKind(StrEnum):
    MODEL = "model"
    MODEL_TOOLS = "model+tools"
    MODEL_MEMORY = "model+memory"
    MODEL_AGENT = "model+agent"
    AGENT_ENVIRONMENT = "agent+environment"
    SOCIO_TECHNICAL = "socio-technical"


class AssuranceLevel(IntEnum):
    UNVERIFIED = 0
    EVALUATED = 1
    EVIDENCE_BACKED = 2
    ASSURED = 3
    INDEPENDENTLY_ATTESTED = 4

    @property
    def label(self) -> str:
        return {0: "Unverified", 1: "Evaluated", 2: "Evidence-Backed", 3: "Assured",
                4: "Independently Attested"}[int(self)]


HARD_GATE_DOMAINS = (Domain.SAFETY, Domain.SECURITY, Domain.PRIVACY)
