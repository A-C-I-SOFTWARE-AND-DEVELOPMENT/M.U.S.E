# Model Registry & Router — existing system + eval-gating extension

## Correction: Hermes already has a registry + router

An initial gap analysis mis-scored this area. Hermes **already ships** a mature
model registry and router:

- **`hermes_cli/model_registry.py`** — `Registry` + `WorkerEntry`, with
  `QUALITY_TIERS`/`SPEED_TIERS`/`COST_TIERS`/`PRIVACY_TIERS`/`RISK_TIERS`, YAML
  loading, a builtin registry, and merge helpers.
- **`hermes_cli/model_router.py`** — canonical `TASK_CATEGORIES`,
  capability-hint maps per category, `APPROVAL_GATED_CATEGORIES`,
  `BROWSER_REQUIRED_CATEGORIES`, worker scoring (`_score`, `_strength_overlap`,
  cost-ceiling / quality-floor gates), and `RoutingDecision`.

A scaffold package (`hermes_cli/model_registry/`) was begun before this was
discovered; it **collided** with the existing module and broke
`model_router`'s import. It was **removed**. Per the brief's "no parallel
architectures" rule, model-routing improvements must **extend** the existing
system, not duplicate it.

## The real gap: eval-gating (ticket ROUTE-2)

The existing router scores workers on declared capability tiers but has **no
eval gate** — a worker can be selected for a task without having passed
project-specific benchmarks. Proposed extension (no code this sprint):

- Add an optional `eval_passed: bool` / `eval_results: dict` to `WorkerEntry`
  (default `False`/`{}`; backward compatible).
- In `model_router._score` (or a wrapper), when a configurable
  `require_eval_for: frozenset[str]` includes the task category, **exclude**
  workers with `eval_passed=False` and surface the decision as `unverified` in
  `RoutingDecision` rather than silently defaulting.
- Feed `eval_results` from the eval harness (ticket EVAL-1).

Acceptance: for an eval-gated category, an un-evaluated worker is never the
selected default; the routing decision records why; existing non-gated behavior
is unchanged.

## Open-weight model families to track (registry-updater ticket REG-1)

The capability families worth keeping current in `WorkerEntry` rows (confirm via
REG-1, never auto-download): **Qwen** (Qwen3 / Qwen3-Coder), **DeepSeek**
(V3/R1), **Kimi** (K2), **Mistral / Devstral**, **Gemma**, **Phi**, **GLM**,
**MiniMax**, **Nemotron**, **Llama** open-weight. A scheduled updater checks
curated sources and flags missing/updated models.
