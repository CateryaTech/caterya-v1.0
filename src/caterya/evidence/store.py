"""SQLite evidence registry (PostgreSQL via the same interface is a drop-in for production)."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from ..core.canonical import jsonable
from .model import Evidence

_DDL = """
CREATE TABLE IF NOT EXISTS evidence(seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, system_id TEXT, evaluation_id TEXT,
  metric TEXT, domain TEXT, ts TEXT, content_hash TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS docs(kind TEXT, id TEXT, system_name TEXT, ts TEXT, json TEXT, PRIMARY KEY(kind,id));
CREATE TABLE IF NOT EXISTS leaves(idx INTEGER PRIMARY KEY, leaf TEXT);
CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY, value INTEGER);
CREATE INDEX IF NOT EXISTS ev_sys ON evidence(system_id); CREATE INDEX IF NOT EXISTS docs_sys ON docs(kind, system_name);
"""


class EvidenceStore:
    def __init__(self, path: str | Path = ":memory:"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._db.executescript(_DDL)

    # evidence ---------------------------------------------------------
    def put_evidence(self, ev: Evidence, system_id: str = "", evaluation_id: str = "") -> int:
        with self._lock:
            c = self._db.execute("INSERT INTO evidence(id,system_id,evaluation_id,metric,domain,ts,content_hash,json) VALUES(?,?,?,?,?,?,?,?)",
                                 (ev.id, system_id, evaluation_id, ev.metric, ev.domain, ev.timestamp, ev.content_hash,
                                  json.dumps(ev.to_dict())))
            self._db.commit()
            return c.lastrowid or 0

    def get_evidence(self, id_: str) -> Optional[Evidence]:
        with self._lock:
            r = self._db.execute("SELECT json FROM evidence WHERE id=?", (id_,)).fetchone()
        return Evidence.from_dict(json.loads(r["json"])) if r else None

    def evidence_row(self, id_: str) -> Optional[dict]:
        with self._lock:
            r = self._db.execute("SELECT seq,system_id,evaluation_id FROM evidence WHERE id=?", (id_,)).fetchone()
        return dict(r) if r else None

    def list_evidence(self, system_id: str = "", evaluation_id: str = "", metric: str = "", limit: int = 500) -> list[Evidence]:
        q, a = "SELECT json FROM evidence WHERE 1=1", []
        for col, v in (("system_id", system_id), ("evaluation_id", evaluation_id), ("metric", metric)):
            if v:
                q += f" AND {col}=?"
                a.append(v)
        with self._lock:
            rows = self._db.execute(q + " ORDER BY seq LIMIT ?", (*a, limit)).fetchall()
        return [Evidence.from_dict(json.loads(r["json"])) for r in rows]

    def head_hash(self) -> str:
        with self._lock:
            r = self._db.execute("SELECT content_hash FROM evidence ORDER BY seq DESC LIMIT 1").fetchone()
        return r["content_hash"] if r else ""

    # generic documents (systems, evaluations, CARs, incidents, signals) -
    def put_doc(self, kind: str, id_: str, doc: dict, system_name: str = "", ts: str = "") -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO docs(kind,id,system_name,ts,json) VALUES(?,?,?,?,?)",
                             (kind, id_, system_name, ts, json.dumps(jsonable(doc))))
            self._db.commit()

    def get_doc(self, kind: str, id_: str) -> Optional[dict]:
        with self._lock:
            r = self._db.execute("SELECT json FROM docs WHERE kind=? AND id=?", (kind, id_)).fetchone()
        return json.loads(r["json"]) if r else None

    def list_docs(self, kind: str, system_name: str = "", limit: int = 200) -> list[dict]:
        q, a = "SELECT json FROM docs WHERE kind=?", [kind]
        if system_name:
            q += " AND system_name=?"
            a.append(system_name)
        with self._lock:
            rows = self._db.execute(q + " ORDER BY ts, rowid LIMIT ?", (*a, limit)).fetchall()
        return [json.loads(r["json"]) for r in rows]

    # log leaves / counters -----------------------------------------------
    def put_leaf(self, idx: int, leaf: str) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO leaves(idx,leaf) VALUES(?,?)", (idx, leaf))
            self._db.commit()

    def leaves(self) -> list[str]:
        with self._lock:
            return [r["leaf"] for r in self._db.execute("SELECT leaf FROM leaves ORDER BY idx")]

    def next_counter(self, name: str) -> int:
        with self._lock:
            self._db.execute("INSERT INTO counters(name,value) VALUES(?,1) ON CONFLICT(name) DO UPDATE SET value=value+1", (name,))
            self._db.commit()
            return self._db.execute("SELECT value FROM counters WHERE name=?", (name,)).fetchone()["value"]


def build_graph(evs: list[Evidence], system: dict | None = None, assurance_id: str = "") -> dict:
    """Evidence Graph: MODEL evaluated_by EVALUATION uses DATASET runs_on ENVIRONMENT executes TEST produces RESULT;
    MODEL produces EVIDENCE; EVIDENCE supports ASSURANCE."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(i: str, t: str, **kw: Any) -> str:
        nodes.setdefault(i, {"id": i, "type": t, **kw})
        return i

    def edge(a: str, rel: str, b: str) -> None:
        e = {"from": a, "rel": rel, "to": b}
        if e not in edges:
            edges.append(e)

    sysid = node("SYS:" + (system or {}).get("name", "system"), "MODEL", label=(system or {}).get("name", "system"))
    for e in evs:
        ev_id = node(e.id, "EVIDENCE", metric=e.metric, result=e.result)
        eva = node("EVAL:" + e.profile + ":" + e.timestamp[:19], "EVALUATION", profile=e.profile)
        test = node("TEST:" + e.metric, "TEST")
        res = node("RESULT:" + e.id, "RESULT", value=e.result)
        env = node("ENV:" + e.evaluator.get("environment_hash", "env"), "ENVIRONMENT")
        edge(sysid, "evaluated_by", eva)
        edge(eva, "runs_on", env)
        edge(eva, "executes", test)
        edge(test, "produces", res)
        edge(sysid, "produces", ev_id)
        for name, h in e.context.get("datasets", {}).items():
            edge(eva, "uses", node("DATA:" + name, "DATASET", hash=h))
        if assurance_id:
            edge(ev_id, "supports", node(assurance_id, "ASSURANCE"))
    return {"nodes": list(nodes.values()), "edges": edges}


def graph_to_dot(g: dict) -> str:
    lines = ["digraph CATERYA {", "  rankdir=LR; node [shape=box,fontname=Helvetica];"]
    lines += [f'  "{n["id"]}" [label="{n["type"]}\\n{n["id"][:28]}"];' for n in g["nodes"]]
    lines += [f'  "{e["from"]}" -> "{e["to"]}" [label="{e["rel"]}"];' for e in g["edges"]]
    return "\n".join(lines + ["}"])
