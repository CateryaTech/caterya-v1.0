"""Quickstart: evaluate a (mock) system, review the assurance record, record a governance decision, export a verifiable bundle.

    pip install -e ".[crypto]" && python examples/quickstart.py
"""
from caterya import AssuranceEngine, MockModel, SystemConfig
from caterya.assurance.report import render_markdown
from caterya.evidence.bundle import export_bundle, reproduce_bundle, verify_bundle

system = SystemConfig(
    name="support-assistant", version="2.3.0", kind="model+tools", provider="caterya-mock", model_id="mock-robust",
    model_version="1.0", code_hash="sha256:replace-with-git-sha", environment={"image": "sha256:replace"},
    dataset_hashes={"finetune": "sha256:replace"},
    deployment={"environment": "staging", "use_case": "bank support", "jurisdiction": "ID", "sector": "finance",
                "criticality": "high", "exposure": 0.6})

engine = AssuranceEngine(system)
result = engine.evaluate(MockModel("robust"), "CATERYA-LLM")          # <- swap in OpenAICompatAdapter / AnthropicAdapter / CallableAdapter
print(result.summary())

# CATERYA recommends; people decide.
car = engine.decide(result.car["car_id"], "CONDITIONALLY_ASSURED", decided_by="Dr. Putri", role="AI governance lead",
                    rationale="Accepted for staging; re-evaluate before production.", conditions=["re-run on production traffic sample"])
print(render_markdown(car))

# Anyone can verify and re-run the evidence without trusting the evaluator.
bundle = export_bundle(engine.runner.store, engine.runner, result.id)
print("verified:", verify_bundle(bundle)["ok"], "| reproduced:", reproduce_bundle(bundle, MockModel("robust"))["all_match"])
