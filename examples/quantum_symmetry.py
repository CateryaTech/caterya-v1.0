"""Research-grade quantum symmetry on a classical statevector.

    python examples/quantum_symmetry.py

Prints a signed Evidence record. The score is a function of the encoded
positive rates. It is not a fairness certificate. PennyLane or Qiskit are used
only when you pass a backend name and the extra is installed; otherwise this
script stays on the classical simulator and says so.
"""
from __future__ import annotations

import json
import sys

from caterya.guardrails.evidence import seal_decision
from caterya.provenance.signing import HmacSigner
from caterya.quantum.symmetry import evaluate_rows


def main() -> None:
    backend = sys.argv[1] if len(sys.argv) > 1 else "classical"
    rows = [{"y_pred": y, "sensitive": {"region": g}} for g, ys in (("jawa", [1, 1, 0, 1, 1]), ("papua", [0, 0, 1, 0, 0])) for y in ys]
    payload = evaluate_rows(rows, backend=backend, shots=0, seed=1337, min_support=1)
    signer = HmacSigner(b"example-only-not-for-production")
    evidence = seal_decision(
        signer,
        metric_id="quantum_symmetry_index_v1",
        value=payload["value"],
        claim=f"example quantum symmetry via {backend}; research metric, not a certificate",
        details={"per_attribute": {k: {"value": v.get("value"), "circuit_hash": v.get("circuit_hash"), "backend": v.get("backend")} for k, v in payload["per_attribute"].items()}},
        limitations=payload["limitations"],
        seed=1337,
        n=len(rows),
        mode="pre_release",
    )
    print(json.dumps({"value": payload["value"], "evidence_id": evidence.id, "circuit_hash": evidence.context["details"]["per_attribute"]["region"]["circuit_hash"], "limitations": evidence.limitations[:3]}, indent=2))
    print("signature verifies:", signer.verifier().verify(evidence.content_hash.encode(), evidence.signature) is True)


if __name__ == "__main__":
    main()
