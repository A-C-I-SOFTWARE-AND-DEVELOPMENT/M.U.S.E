# Evidence-Backed Model Routing (Task Classes)

JARVIS Prime chooses *which model runs a task* from measured outcomes, not
vibes — and it can explain the choice, on the phone or the CLI. This page
documents the task classes, the scorecard dimensions, the routing policy, and
the mobile surface.

> Source of truth: `hermes_cli/jarvis_prime/task_router.py` (decision layer),
> `hermes_cli/jarvis_prime/model_scorecard.py` (evidence),
> `hermes_cli/jarvis_prime/model_bootstrap.py` (free/local-first policy),
> `gateway/cockpit/handlers.py` (`/v1/cockpit/model-routes`).
>
> The task router does **not** re-detect providers, re-score outcomes, or
> fork scorecard storage. It *composes* the layers that already exist.

## Task classes

Ten mobile-first classes (`task_router.TaskClass`):

| Task class | What it routes | Default bias |
|---|---|---|
| `mobile_chat` | Everyday phone conversation | local-first, latency + mobile-UX |
| `voice_reply` | Hands-free / driving replies | local-first, lowest latency |
| `summarization` | Condensing threads, docs | local-first, context + latency |
| `memory_curator` | Curating the Memory Tree | local-first, low hallucination |
| `research` | Multi-source research | quality + citation + context (paid-allowed) |
| `citation_verification` | Checking claims/citations | citation accuracy dominant (paid-allowed) |
| `coding_plan` | Planning a change | strong reasoning; worker-lane first |
| `coding_build` | Writing the change | coding pass-rate + tools; Claude lane first |
| `coding_review` | Independent review | coding + quality; Codex lane first |
| `test_debug` | Running/fixing tests | coding + tool reliability; local-first |

## Scorecard dimensions

A `ModelScorecard` records measured outcomes per `(model, task, risk)`. Eight
dimensions feed the per-task ranking (`ModelScorecard.score_for`):

1. **quality** — blended test pass-rate + accepted-diff rate
2. **latency** — `latency_ms`, lower is better
3. **cost** — `cost_usd`, lower is better
4. **context length** — `context_length` (max tokens the model offers)
5. **tool reliability** — `tool_reliability` ∈ [0,1]
6. **coding pass rate** — test pass-rate on coding tasks
7. **citation accuracy** — `citation_accuracy` ∈ [0,1]
8. **mobile UX suitability** — `mobile_ux_suitability` ∈ [0,1]

Owner corrections, hallucination corrections, and repeated errors always
penalize, regardless of task class. The task-agnostic `score` is kept for
backward compatibility; `score_for(task_class)` re-weights per
`TASK_CLASS_WEIGHTS`.

Record outcomes from real runs:

```bash
python -m hermes_cli.jarvis_prime model-scorecard add \
  --model qwen3-coder --provider ollama --task coding_build \
  --tests-passed 19 --tests-failed 1 --tool-reliability 0.92 \
  --accepted-diff-rate 0.95 --context-length 256000
```

## Router policy

`route_for_task(task_class)` returns a `ModelRouteDecision`
(`chosen`, `route_tier`, `fallback_chain`, `why`, `evidence`, …):

1. **Choose by task class.** Candidates come from the *enabled* routes in the
   free/local-first order (`model_bootstrap`): `local_oss` →
   `hosted_free_or_user_configured_oss` → `claude_code_worker` →
   `codex_worker` → `paid_api_explicit_only`. Some classes (`coding_*`,
   `test_debug`) re-order to prefer the strong worker lanes first.
2. **Evidence wins when measured.** A candidate with scorecards is ranked by
   its task-class score; an unmeasured candidate gets a *tier prior* from the
   local-first order. So a fresh install routes local-first, a measured-strong
   model overtakes that prior, and a measured-weak model never beats it.
3. **Local-first.** Local runtimes are preferred for privacy + latency unless
   evidence or the per-class profile says otherwise.
4. **Fallback.** The full ranked list is the fallback chain — if the top model
   fails, the next is tried.
5. **Paid is explicit opt-in.** Paid providers are never candidates unless the
   class allows paid **and** paid routing is enabled (env
   `HERMES_JARVIS_ENABLE_PAID=1` as a floor, or the owner-gated override).

Explain any choice:

```bash
python -m hermes_cli.jarvis_prime route --task coding_build
python -m hermes_cli.jarvis_prime route --json        # all task classes
```

## Mobile surface

The Android cockpit (Settings → **Model routing**) reads
`GET /v1/cockpit/model-routes` and shows, per task class: the chosen model and
tier, the human-readable *why*, the scorecard evidence, and the fallback
chain.

Owner controls go through `POST /v1/cockpit/model-routes/override`:

- **Pin / clear a model** for a task class — a reversible preference
  (token-authenticated).
- **Toggle paid routing** — a money-spend gate. The server requires the exact
  owner phrase `Yes, with authorization.`; the app demands it in a
  confirmation dialog before sending. The override is persisted (with
  `authorized_by` + `updated_at`) to
  `~/.hermes/jarvis_prime/model_route_overrides.json`. No API keys are ever
  accepted or stored.

## Runtime wiring

The cockpit chat generator (`gateway/cockpit/generate.py`) consults the router
when the turn carries a `task_class` (derived in `gateway/cockpit/agent.py`
from the turn's existing mode/target/research signals): the routed model is
preferred when installed locally, otherwise the existing kind/name-hint and
free-first local→cloud fallback are used unchanged.
