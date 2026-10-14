"""Plug in your own metric: define a MetricSpec (hash-bound), implement compute(), register, and add it to a profile run."""
from caterya import AssuranceEngine, MockModel, SystemConfig
from caterya.core.registry import register_metric
from caterya.core.types import Domain
from caterya.metrics.base import Metric, MetricSpec
from caterya.metrics.stats import bootstrap_ci, mean
from caterya.profiles.registry import MetricPlan, Profile


@register_metric
class ShortAnswers(Metric):
    spec = MetricSpec(id="short_answers_v1", domain=Domain.RELIABILITY, title="Answers stay under N words",
                      description="Share of answers within a word budget.", formula="mean[1{words <= N}]", status="experimental",
                      limitations=("Length is a weak proxy for concision.",))
    DEFAULTS = {"max_words": 12}

    def compute(self, ctx):
        vals = [1.0 if len(ctx.ask(t["prompt"]).text.split()) <= self.p["max_words"] else 0.0 for t in ctx.dataset("tasks")[:20]]
        return self.result(mean(vals), bootstrap_ci(vals, n_boot=100), len(vals))


profile = Profile("MY-PROFILE", "custom", (MetricPlan("short_answers_v1", {"max_words": 12}, 0.8, 0.9),), requires_human=False)
res = AssuranceEngine(SystemConfig("x", "1")).evaluate(MockModel("robust"), profile)
print(res.rows[0])
