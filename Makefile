.PHONY: install test lint docs serve demo bench clean
install: ; pip install -e ".[all,dev]"
test:    ; python -m pytest
lint:    ; ruff check src tests benchmarks examples scripts
docs:    ; python scripts/gen_schemas.py && python scripts/gen_docs.py
serve:   ; caterya serve
demo:    ; caterya demo
bench:   ; python benchmarks/validate.py && python benchmarks/latency.py
clean:   ; rm -rf .caterya build dist *.egg-info .pytest_cache .ruff_cache
