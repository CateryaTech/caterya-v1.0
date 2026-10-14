"""Measures the overhead of the Python AgentGuard hook on THIS machine. No performance number is claimed in docs
unless produced by this script; run it on your hardware and publish the output with your evidence."""
from __future__ import annotations

import statistics
import time

from caterya.core.system import SystemDescriptor
from caterya.datasets import builtin_agent_policy
from caterya.sdk import AssuranceEngine


def main(n: int = 5000) -> None:
    eng = AssuranceEngine(SystemDescriptor("latency"))
    g = eng.guard(builtin_agent_policy(), "bench")
    lat = []
    for i in range(n):
        g._last = None
        t = time.perf_counter()
        g.check("weather.lookup", {"q": i}, "read")
        lat.append((time.perf_counter() - t) * 1000)
        g.steps.clear(); g.tokens.clear()
    lat.sort()
    print(f"AgentGuard.check over {n} calls (includes SHA3-256 state hash and signature):")
    print(f"  p50={lat[n // 2]:.3f} ms  p95={lat[int(n * .95)]:.3f} ms  p99={lat[int(n * .99)]:.3f} ms  mean={statistics.mean(lat):.3f} ms")
    print(f"  throughput (single thread) ≈ {1000 / statistics.mean(lat):,.0f} checks/s")


if __name__ == "__main__":
    main()
