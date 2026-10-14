"""Incident loop: INCIDENT -> CAPTURE -> EVIDENCE -> REPRODUCE -> EVALUATE -> MITIGATE -> RE-TEST -> UPDATE ASSURANCE RECORD."""
from __future__ import annotations

import re
from typing import Optional

from ..core.canonical import digest, short
from ..core.clock import Clock, iso, utcnow
from ..core.errors import CateryaError
from ..evidence.store import EvidenceStore

STAGES = ["CAPTURED", "EVIDENCED", "REPRODUCED", "EVALUATED", "MITIGATED", "RETESTED", "CLOSED"]


class IncidentLoop:
    def __init__(self, store: EvidenceStore, clock: Clock = utcnow):
        self.store, self.clock = store, clock

    def _save(self, inc: dict) -> dict:
        self.store.put_doc("incident", inc["id"], inc, inc["system"], inc["opened_at"])
        return inc

    def _need(self, inc: dict, stage: str) -> None:
        if STAGES.index(inc["stage"]) < STAGES.index(stage):
            raise CateryaError(f"incident {inc['id']} is at {inc['stage']}; complete {stage} first")

    def capture(self, system: str, description: str, prompt: str, output: str, failure_pattern: str,
                system_prompt: Optional[str] = None, severity: str = "moderate") -> dict:
        now = iso(self.clock())
        inc = {"id": "INC-" + short(digest([system, prompt, output, now]), 10), "system": system, "description": description,
               "severity": severity, "captured": {"prompt": prompt, "system_prompt": system_prompt, "output": output,
                                                   "output_hash": digest(output)},
               "failure_pattern": failure_pattern, "stage": "CAPTURED", "opened_at": now, "history": [("CAPTURED", now)],
               "evidence_ids": [], "mitigations": [], "car_updates": []}
        return self._save(inc)

    def _adv(self, inc: dict, stage: str) -> dict:
        inc["stage"] = stage
        inc["history"].append((stage, iso(self.clock())))
        return self._save(inc)

    def attach_evidence(self, inc_id: str, evidence_ids: list[str]) -> dict:
        inc = self.store.get_doc("incident", inc_id)
        inc["evidence_ids"] += evidence_ids
        return self._adv(inc, "EVIDENCED")

    def reproduce(self, inc_id: str, adapter, trials: int = 5) -> dict:
        inc = self.store.get_doc("incident", inc_id)
        self._need(inc, "CAPTURED")
        c = inc["captured"]
        hits = sum(1 for i in range(trials) if re.search(inc["failure_pattern"], adapter.generate(
            c["prompt"], system=c["system_prompt"], temperature=0.0 if i == 0 else 0.7, seed=i).text, re.I))
        inc["reproduction"] = {"trials": trials, "failures": hits, "rate": hits / trials, "reproducible": hits > 0}
        return self._adv(inc, "REPRODUCED")

    def mark_evaluated(self, inc_id: str, evaluation_id: str) -> dict:
        inc = self.store.get_doc("incident", inc_id)
        self._need(inc, "REPRODUCED")
        inc["evaluation_id"] = evaluation_id
        return self._adv(inc, "EVALUATED")

    def mitigate(self, inc_id: str, description: str, effectiveness: float = 0.0) -> dict:
        inc = self.store.get_doc("incident", inc_id)
        self._need(inc, "EVALUATED")
        inc["mitigations"].append({"description": description, "claimed_effectiveness": effectiveness, "verified": False})
        return self._adv(inc, "MITIGATED")

    def retest(self, inc_id: str, adapter, trials: int = 5) -> dict:
        inc = self.store.get_doc("incident", inc_id)
        self._need(inc, "MITIGATED")
        c = inc["captured"]
        hits = sum(1 for i in range(trials) if re.search(inc["failure_pattern"], adapter.generate(
            c["prompt"], system=c["system_prompt"], temperature=0.0 if i == 0 else 0.7, seed=100 + i).text, re.I))
        inc["retest"] = {"trials": trials, "failures": hits, "fixed": hits == 0}
        for m in inc["mitigations"]:
            m["verified"] = hits == 0
        return self._adv(inc, "RETESTED")

    def close(self, inc_id: str, car_id: str) -> dict:
        inc = self.store.get_doc("incident", inc_id)
        self._need(inc, "RETESTED")
        inc["car_updates"].append(car_id)
        return self._adv(inc, "CLOSED")
