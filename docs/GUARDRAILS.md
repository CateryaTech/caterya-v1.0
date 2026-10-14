# Agentic guardrails

`CATERYAGuardrail` and `EthicsSwarm` produce a recommendation and a signed Evidence record. They do not delete the output, and they do not finalise an assurance decision. Blocking, deploying, or certifying still goes through `finalize()` with a named decider and role.

## Modes

- `heuristic` — weighted lexical screen (`caterya.guardrails.heuristic`). Weights are in the Evidence. Empty output, a configured PII pattern, or a configured injection marker is a **hard flag**: the recommendation is fail/remediate even if the weighted mean stays above the threshold.
- `full` — unweighted mean of `evaluation["scores"]`. If that map is missing, the decision is `untested`. No score is invented.

`request_remediation=True` labels the decision `remediate` and returns recommendations. The text is unchanged.

## Swarm

`EthicsSwarm` votes only from supplied metric scores, plus two narrow heuristic checks (provenance fields present in context; a token repeated at least eight times). Otherwise the agent **abstains**. Abstentions are left out of the mean. If every agent abstains, the consensus is `untested`, not 0.70. There is no random jitter.

Each agent vote and the consensus are separate Evidence records on one hash chain.

## Host frameworks

`as_langgraph_node` and `as_crewai_guard` do not import those libraries. The CrewAI adapter returns `(True, payload)` on purpose: returning `False` would let the host drop the output. Read `allow_release` and the Evidence id. LangGraph state keeps the original output and adds `caterya_guardrail`.

## Canary

`ContinuousMonitor.on_guardrail(score)` appends the score. Once `guardrail_min_samples` exist (default 5) and the window mean (default 20) is below `guardrail_min_score` (default 0.70), `plan()` requests `incident_replay` at depth `deep`. The monitor does not block traffic. The threshold is a research default (`CATERYA_GUARDRAIL_MIN_SCORE`).

```bash
caterya guardrail check --text "..." --mode heuristic
caterya guardrail check --text "..." --mode full --evaluation scores.json
caterya guardrail swarm --text "..." --evaluation scores.json
```

See `examples/guardrail_check.py`.
