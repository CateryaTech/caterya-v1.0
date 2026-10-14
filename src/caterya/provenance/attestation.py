"""in-toto Statement wrapped in a DSSE envelope (Sigstore/in-toto pattern) for third-party attestation."""
from __future__ import annotations

import base64
import json

from ..core.canonical import canonical_bytes
from .signing import Signer, Verifier

PAYLOAD_TYPE = "application/vnd.in-toto+json"
PREDICATE_TYPE = "https://github.com/cateryatech/caterya-v1.0/predicates/assurance/v1"


def pae(payload_type: str, payload: bytes) -> bytes:
    t = payload_type.encode()
    return b"DSSEv1 %d %s %d %s" % (len(t), t, len(payload), payload)


def statement_for_car(car: dict) -> dict:
    h = car["content_hash"].split(":", 1)[-1]
    return {"_type": "https://in-toto.io/Statement/v1",
            "subject": [{"name": car["car_id"], "digest": {"sha256": h}}],
            "predicateType": PREDICATE_TYPE,
            "predicate": {"system": car["system"], "level": car["level"], "disposition": car["disposition"]["status"],
                          "risk": car["risk"]["level"], "evidence_root": car["evidence"].get("merkle_root", "")}}


def make_dsse(statement: dict, signer: Signer) -> dict:
    payload = canonical_bytes(statement)
    sig = signer.sign(pae(PAYLOAD_TYPE, payload))
    return {"payloadType": PAYLOAD_TYPE, "payload": base64.b64encode(payload).decode(),
            "signatures": [{"keyid": signer.key_id, "sig": sig}]}


def verify_dsse(envelope: dict, verifier: Verifier) -> tuple[bool, dict | None]:
    payload = base64.b64decode(envelope["payload"])
    ok = any(s["keyid"] == verifier.key_id and verifier.verify(pae(envelope["payloadType"], payload), s["sig"])
             for s in envelope["signatures"])
    return ok, (json.loads(payload) if ok else None)
