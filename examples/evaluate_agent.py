"""Agent assurance: evaluate system traces, then guard live tool calls inline (high-risk actions only)."""
from caterya import AssuranceEngine, MockModel, SystemConfig
from caterya.core.errors import PolicyViolation
from caterya.datasets import builtin_agent_policy
from caterya.evaluators.agent import SimulatedAgent

system = SystemConfig("refund-agent", "0.4.0", kind="model+agent", provider="caterya-mock", model_id="mock", model_version="1")
engine = AssuranceEngine(system)
for behavior in ("safe", "reckless"):
    r = engine.evaluate(MockModel("robust"), "CATERYA-AGENT", agent=SimulatedAgent(behavior))
    print(behavior, r.summary()["recommended"], [f["metric_id"] for f in r.findings])

guard = engine.guard(builtin_agent_policy(), goal="refund order 1042", human_approver=lambda tool, args: False)


@guard.tool("payments.refund", scope="write")
def refund(amount: str) -> str:
    return f"refunded {amount}"


try:
    refund(amount="25.00")
except PolicyViolation as e:
    print("blocked:", e.reasons, "| proof:", guard.tokens[-1].state_hash[:30], "…")
