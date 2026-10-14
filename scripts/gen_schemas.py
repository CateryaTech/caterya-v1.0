"""Generate JSON Schemas into schemas/ (Evidence from the dataclass; CAR and SystemTrace hand-specified)."""
from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

from caterya.evidence.model import Evidence

OUT = Path(__file__).resolve().parent.parent / "schemas"
T = {"str": {"type": "string"}, "int": {"type": "integer"}, "dict": {"type": "object"}, "list": {"type": "array"},
     "Optional[float]": {"type": ["number", "null"]}, "Optional[tuple]": {"type": ["array", "null"], "items": {"type": "number"}, "minItems": 2, "maxItems": 2}}


def evidence() -> dict:
    props = {f.name: T.get(str(f.type).replace("typing.", "").replace("from __future__ ", ""), {}) for f in fields(Evidence)}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "caterya.evidence/v1", "title": "CATERYA Evidence",
            "description": "A verifiable measurement: claim + method hash + data hash + seed + result + CI + limits + chain + signature. "
                           "content_hash = <algo>:hex(hash(canonical_json(record without id, content_hash, signature))); "
                           "signature signs the content_hash string.",
            "type": "object", "required": [f.name for f in fields(Evidence) if f.name not in ("id",)] , "properties": props,
            "additionalProperties": False}


def car() -> dict:
    s = {"type": "string"}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "caterya.car/v1", "title": "CATERYA Assurance Record (CAR)",
            "type": "object",
            "required": ["spec_version", "car_id", "version", "system", "model", "deployment", "evaluation", "domains", "risk",
                         "evidence", "coverage", "disposition", "validity", "level", "content_hash", "signature"],
            "properties": {
                "car_id": {"type": "string", "pattern": "^CAR-[0-9]{4}-[0-9]{6}$"}, "version": {"type": "integer", "minimum": 1},
                "prev_hash": s, "system": {"type": "object", "required": ["name", "type", "version"]},
                "model": {"type": "object", "required": ["provider", "model_id", "model_version"]},
                "deployment": {"type": "object"}, "evaluation": {"type": "object", "required": ["profile", "methodology", "evaluator", "timestamp"]},
                "domains": {"type": "object"}, "risk": {"type": "object", "required": ["level", "findings", "unresolved"]},
                "evidence": {"type": "object", "required": ["artifacts", "hashes"]},
                "disposition": {"type": "object", "required": ["status"], "properties": {"status": {"enum": [
                    "EVALUATED", "REVIEW_REQUIRED", "CONDITIONALLY_ASSURED", "ASSURED", "REJECTED", "EXPIRED"]}}},
                "validity": {"type": "object", "required": ["issued_at", "valid_until"]},
                "level": {"type": "integer", "minimum": 0, "maximum": 4}, "content_hash": s, "signature": s}}


def trace() -> dict:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "caterya.trace/v1", "title": "CATERYA System Trace",
            "type": "object", "required": ["trace_id", "goal", "steps"],
            "properties": {"trace_id": {"type": "string"}, "goal": {"type": "string"}, "outcome": {"type": "object"}, "meta": {"type": "object"},
                           "steps": {"type": "array", "items": {"type": "object", "required": ["index", "type"], "properties": {
                               "index": {"type": "integer"}, "type": {"enum": ["prompt", "plan", "tool_call", "tool_result", "retrieval", "observation",
                                                                              "decision", "action", "human_override", "error", "output"]},
                               "name": {"type": "string"}, "args": {"type": "object"}, "content": {"type": "string"}, "ok": {"type": "boolean"},
                               "scope": {"type": ["string", "null"]}, "side_effect": {"type": "number"}, "meta": {"type": "object"}}}}}}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, fn in (("evidence", evidence), ("car", car), ("system_trace", trace)):
        (OUT / f"{name}.schema.json").write_text(json.dumps(fn(), indent=2) + "\n")
    print("schemas written:", [p.name for p in OUT.glob("*.json")])


if __name__ == "__main__":
    main()
