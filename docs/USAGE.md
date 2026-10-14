# Usage reference

## CLI
| Command | Purpose |
|---|---|
| `caterya init` | create state dir and signing key (`CATERYA_HOME`, default `./.caterya`) |
| `caterya register --file system.json` | register a system descriptor |
| `caterya evaluate --system system.json --profile CATERYA-LLM --adapter mock:robust\|openai\|anthropic [--agent safe\|reckless] [--depth light\|standard\|deep] [--datasets extra.json] [--out dir]` | run a profile; `--out` writes `bundle.json`, `report.md`, `report.html` |
| `caterya evidence export <CAR\|EVAL> --out bundle.json` · `verify` · `reproduce` · `graph [--dot]` | portable evidence |
| `caterya assurance report\|show\|history\|decide <CAR>` | records and governance decision (`--decision --by --role --rationale [--override-reason] [--condition]`) |
| `caterya compare <old CAR> <new CAR>` | trustworthiness regression (exit 4 on regression) |
| `caterya gate <CAR> --policy policy.json [--baseline CAR]` | CI/CD policy gate (exit 1 = BLOCK) |
| `caterya regmap <EVAL> [--framework EU_AI_ACT] [--seal --out map.json]` | regulatory evidence map; `--seal` writes a signed coverage record (not a certification) |
| `caterya quantum backends\|symmetry\|fidelity\|entanglement` | research quantum metrics; default backend `classical`. See `docs/QUANTUM.md` |
| `caterya guardrail check\|swarm` | recommendation + Evidence. Does not block. See `docs/GUARDRAILS.md` |
| `caterya list profiles\|metrics\|params\|capabilities\|datasets` | catalogues |
| `caterya serve` · `caterya demo` | API + dashboard · end-to-end demo |

`system.json` fields: `name, version, kind, provider, model_id, model_version, tools, memory, policies, config, code_hash, environment, dataset_hashes, organization, access_mode, deployment{environment,use_case,jurisdiction,sector,criticality,exposure}`. Fill `code_hash`, `environment`, `dataset_hashes` honestly — `provenance_completeness_v1` measures declaration.

## REST API (`caterya serve`, OpenAPI at `/docs`)
`GET /v1/health · /capabilities · /profiles · /metrics · /parameters` · `POST/GET /v1/evaluations[/{id}[/bundle]]` · `POST/GET /v1/evidence[/{id}[/verify]]` · `GET /v1/log/head · /v1/graph/{eval}` · `POST/GET /v1/assurance[/{car}[/decision|/verify|/report|/regulatory]]` · `POST /v1/compare · /v1/gate` · `GET /v1/history/{system}` · `POST /v1/monitor/signals · /v1/incidents`. Mutating routes require `Authorization: Bearer $CATERYA_API_KEY` when that variable is set. Dashboard: `/ui/`.

## Evaluating your own system
```python
from caterya import AssuranceEngine, SystemConfig
from caterya.adapters.base import CallableAdapter
adapter = CallableAdapter(lambda prompt, system=None, history=None, temperature=0.0, seed=None: my_client.chat(prompt, system=system, history=history))
engine = AssuranceEngine(SystemConfig("my-system", "1.0", provider="acme", model_id="x", model_version="1"))
engine.evaluate(adapter, "CATERYA-LLM", datasets={"tasks": my_tasks, "injection": my_attacks})   # replace built-in toy datasets
```
Bring domain datasets: `tasks` (`id,prompt,expected`), `injection`, `policy`, `pii`, `fairness`, `tabular_predictions`, `context`, `selfrefine`, `numeric_trajectories`, `agent_scenarios`, `agent_policy`, `quantum_states`, `quantum_fairness`, `quantum_circuits`, `agent_outputs`. Built-in datasets are small toy probes meant for pipeline testing. Pillar labels: `docs/PILLARS.md`.

## Quantum and guardrails
```python
from caterya.quantum.symmetry import evaluate_rows
from caterya.guardrails import CATERYAGuardrail
print(evaluate_rows([{"y_pred": 1, "group": "a"}, {"y_pred": 0, "group": "b"}], min_support=1)["value"])
print(CATERYAGuardrail().check("a short answer").decision)   # pass/fail/remediate/untested, plus .evidence
```
Scripts: `examples/quantum_symmetry.py`, `examples/guardrail_check.py`.

## Policy file (CI gate)
See `examples/policy.json`: `min_level, max_risk, block_dispositions, require_domains, min_metric, max_regression_drop, max_age_days, fail_on_untested_required`.
