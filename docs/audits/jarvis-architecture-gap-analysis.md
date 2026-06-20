# MUSE Architecture Gap Analysis

Target component model (from the brief) vs. what exists in Hermes today, with the
gap and where this sprint moves the needle.

| Target component | Exists in Hermes? | Where | Gap | This sprint |
|---|---|---|---|---|
| Core orchestrator / tool loop | ✅ | `run_agent.py`, `agent/conversation_loop.py`, `agent/tool_executor.py` | mature | adds compaction layer |
| Tool executor (scoped, guardrails, checkpoints) | ✅ | `agent/tool_executor.py`, `model_tools.py`, `toolsets.py` | no output compaction, **no output scrub** | ✅ both added |
| Context-budget enforcement | ✅ | `tools/tool_result_storage.py`, `tools/budget_config.py`, `agent/iteration_budget.py` | first-pass reducer missing | ✅ TokenJuice ahead of it |
| Navigator / planner | partial | `docs/orchestration/`, orchestration stack | not unified | ticket |
| Dispatcher / task queue | partial | orchestration Job/Worker | not generalized | ticket |
| Model router | ✅ **already rich** | `hermes_cli/model_router.py` (task categories, capability hints, scoring, approval-gated categories) + `hermes_cli/model_registry.py` (`Registry`/`WorkerEntry`, quality/speed/cost/privacy/risk tiers) | **no eval-gating** | ticket ROUTE-2 (extend, don't duplicate) |
| Memory curator | ✅ (different shape) | `agent/curator.py`, plugins memory backends | no layered raw→working→semantic→tree | ticket (interfaces only) |
| Skill manager | ✅ | `skills/`, `optional-skills/`, `/reload-skills` | progressive-load OK | none |
| Security governor | partial | guardrails, `file_safety.py`, `prompt_injection` (openhuman side) | output scrub missing | ✅ scrub added |
| Background learner | ✅ ENABLED by default | `hermes_cli/background_learner/`, `hermes_cli/config.py` (`DEFAULT_CONFIG`) | self-learning queue (idle-only, max 50 jobs/cycle) | ✅ enabled by default in `DEFAULT_CONFIG` |
| Evaluator / eval harness | partial | `tests/`, benchmarks | no model-routing evals | ticket |
| Observability | ✅ | `hermes_logging.py`, callbacks | add compaction metrics | ✅ `[tokenjuice]` metrics |

> **Audit correction (during implementation):** an initial read of the gap
> analysis mis-scored the model router as "provider selection only." It is in
> fact a mature router+registry. A scaffold package was started, detected to
> **collide** with the existing `hermes_cli/model_registry.py` (breaking
> `hermes_cli/model_router.py`'s import), and **removed**. Per "no parallel
> architectures," the model-routing work is reframed as *extending* the existing
> system with eval-gating (ticket ROUTE-2), not rebuilding it.

## Net effect of this sprint

- **Closes**: tool-output compaction (new), tool-output credential scrubbing
  (security), raw-output debug log.
- **Enabled by default**: background-learner (self-learning queue, idle-only,
  max 50 jobs/cycle) wired into `DEFAULT_CONFIG` in `hermes_cli/config.py`;
  GODMODE jailbreak (refusal_inversion system prompt + `prefill.json`
  aggressive-compliance priming) also set as the default for all new
  installations.
- **Tickets** (interfaces + acceptance criteria, no code): layered memory,
  semantic retrieval, navigator/dispatcher unification, self-update workflow,
  integration registry, eval harness, eval-gated routing (extend existing),
  multimodal-summary compaction.

See `one-sprint-build-plan.md` for the ticket list.
