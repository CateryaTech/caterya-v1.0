# Contributing

Thanks for helping build verifiable AI assurance. Principles: **no claim without evidence**, **limitations are part of the spec**, **independence matters**.

1. Open an issue (or RFC for spec/metric/level changes — see `governance/CHARTER.md`).
2. `make install && make test && make lint` must pass. Add tests for behaviour; metrics need a dose-response or detection test.
3. New metrics: a `MetricSpec` with formula, assumptions and **limitations**; all model calls through `ctx.ask`; deterministic given `ctx.seed`; status starts at `research`/`experimental`.
4. Do not add real harmful-content corpora, secrets or personal data. Use canaries and clearly fake data.
5. Sign off commits (`git commit -s`, DCO). Two reviewers for `core/`, `provenance/`, `assurance/`.
6. Update docs: `make docs` regenerates parameter and metric references; edit `docs/CLAIMS.md` if a public claim changes.
