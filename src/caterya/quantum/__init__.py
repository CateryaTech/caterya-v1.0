"""Quantum extension. Importing submodules registers metrics via ``caterya.metrics``.

Default backend is the classical statevector. PennyLane and Qiskit are optional
and are never silently substituted.
"""
from __future__ import annotations

from .backend import BACKENDS, get_backend
from .symmetry import evaluate_rates, evaluate_rows
from .types import CircuitSpec, QuantumRun

__all__ = [
    "BACKENDS",
    "CircuitSpec",
    "QuantumRun",
    "evaluate_rates",
    "evaluate_rows",
    "get_backend",
]
