# Eval Gates (ROUTE-2 + EVAL-1)

How model/worker routing is gated on evaluation results.

## Harness (EVAL-1)

`hermes_cli/evals` runs a deterministic, fast, model-optional suite and produces
fields consumable by the registry:

```python
from hermes_cli.evals import run_suite
report = run_suite("qwen3-coder", threshold=0.7)   # optionally pass runner=...
report.to_registry_fields()   # -> {"eval_passed": bool, "eval_results": (...)}
```

- **Model-independent cases** always run (e.g. `compaction_quality`,
  `scrub_no_leak`).
- **Model-dependent cases** (e.g. `tool_call_correctness`) run only when a
  `runner` callable is supplied. Heavy real-model SWE evals can delegate to
  `mini_swe_runner.MiniSWERunner` via that runner.
- A worker **passes** only if at least one case ran and the mean score ≥ the
  threshold.

## Gate (ROUTE-2)

`WorkerEntry` carries `eval_passed: bool` and `eval_results: tuple[(name, score)]`
(loaded from registry YAML, backward compatible — default unverified). The router
gate is opt-in via `RouterContext.require_eval_for`:

```python
from hermes_cli.model_router import route, RouterContext
ctx = RouterContext(require_eval_for=frozenset({"implementation", "security"}))
decision = route(task, "implementation", context=ctx)
```

For a gated category, workers with `eval_passed=False` are excluded from
candidates (surfaced in `decision.rejected` with an "eval gate" reason); internal
infra workers (`hermes-local`, `github-publisher`, `human-approval`) are exempt.
Empty `require_eval_for` (default) leaves routing behavior unchanged.

## Feeding results back

A background-learner `evaluate_model_routing` job runs the harness for a worker;
promoting the resulting `eval_passed=True` into the registry YAML is an
owner-gated change (RC3 proposal), so no worker silently becomes a gated-category
default.
