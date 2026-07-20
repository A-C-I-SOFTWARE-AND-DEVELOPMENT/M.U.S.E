# MUSE — Agent-Hiring & Swarm Capability Report
_Repo: C:\Users\Echer\M.U.S.E · Snapshot: 2026-07-20_

## CURRENT_CAPABILITY

MUSE today **can** spawn, route, and govern sub-agents, but it is a **first-class
sub-agent platform, not an agent market**. The plumbing is real and battle-tested;
the *self-creation* / *auction* layer is missing. Concretely:

**What works today**

- **Sub-agent dispatch** via the `delegate_task` tool. A parent AIAgent spawns
  child AIAgent instances in a `ThreadPoolExecutor`, each with a fresh
  conversation, isolated `task_id`/terminal session, a toolset allowlist, a
  depth-bound orchestrator-vs-leaf role, and per-child wall-clock + iteration
  budgets. Children are blocked from `delegate_task`, `clarify`, `memory`,
  `send_message`, `execute_code` (DELEGATE_BLOCKED_TOOLS, `tools/delegate_tool.py:45`).
- **Static council routing** via a JSON registry. The AOS dispatcher reads
  `skills/aos-enterprise-council/operating-registry/registry.json`, scores
  domain specialists by keyword overlap (`when_to_use` vs `when_not_to_use`),
  and returns a `CouncilSession` (who engages). It does **not** call models —
  the orchestrator LLM still drives execution via `delegate_task`.
- **Multi-grain fan-out** via `/swarm` (the `Grainler` pipeline). A goal is
  partitioned into disjoint-file-domain grains and run in parallel against a
  shared blackboard + Decision Ledger. Falls back to a single inline grain
  when decomposition can't find ≥2 disjoint components.
- **Hard guardrails** on top: `delegation.max_spawn_depth` (default 1, cap 3),
  `delegation.orchestrator_enabled` kill switch, `is_spawn_paused()` global
  freeze, `subagent_auto_approve` for dangerous-cmd callbacks, owner-gating
  via `enterprise/policy.py` + `enterprise/judge.py`, full audit log per
  plan / dispatch / leaf / judge / retry / escalate.
- **Cockpit surface**: `gateway/cockpit/agent_full.py` streams the full
  AIAgent loop (same tool surface as TUI/gateway, including `delegate_task`)
  to the web dashboard via `thinking`/`phase`/`tool_call`/`body_delta`/
  `approval`/`done`/`error` chunks.
- **Discovery**: `plugins/recommend/tools.py:handle_recommend` is an offline
  recommender that, given a free-text use-case, ranks MUSE's *own* surfaces
  (cockpit, swarm, GraphRAG, gateway, …) — useful UI glue, but a recommender,
  not a market.

**What is missing**

- No **runtime agent creation**. A MUSE run cannot synthesize a new persona,
  write a new `SKILL.md`, and register it as a discoverable tool. Personas
  are static — they live in `skills/`, `plugins/`, or the AOS `registry.json`.
- No **capability marketplace / auction**. There is no bid/ask surface, no
  reputation ledger, no price-discovery, no discovery-by-capability beyond
  keyword overlap on a hand-curated JSON file.
- No **self-hiring**. The "AOS council" is a *pre-declared roster*; a
  council member is a *path on disk + a SKILL.md*, not an agent the system
  can mint on demand.
- AOS is **routing-only**; the dispatcher picks a roster, but a separate
  orchestrator LLM (the `aos-council-director` skill) is what actually
  issues `delegate_task` calls. Two planners, two ledgers — partly unified
  in `unified_dispatch`, but the boundary is real.

---

## ENTRY_POINTS (file:line)

### 1. The single tool a parent MUSE calls to spawn a child

**`tools/delegate_tool.py:1927`** — `delegate_task(goal, context, toolsets, tasks,
max_iterations, acp_command, acp_args, role, parent_agent) -> str`
> "Spawn one or more child agents to handle delegated tasks. … The 'role'
> parameter controls whether a child can further delegate: 'leaf' (default)
> cannot; 'orchestrator' retains the delegation toolset … bounded by
> delegation.max_spawn_depth."

Schema registered as `DELEGATE_TASK_SCHEMA` at **`tools/delegate_tool.py:2670`**
(name=`"delegate_task"`), dynamic per `get_definitions()` via
`_build_dynamic_schema_overrides` so the model sees the live
`max_concurrent_children` / `max_spawn_depth` values.

### 2. The single dispatch chokepoint inside the agent

**`run_agent.py:4014`** — `AIAgent._dispatch_delegate_task(self, function_args)`
> "Single call site for delegate_task dispatch. New DELEGATE_TASK_SCHEMA
> fields only need to be added here to reach all invocation paths
> (concurrent, sequential, inline)."

Forwards to `tools.delegate_tool.delegate_task` with `parent_agent=self`.

Reached from two callers:
- `agent/agent_runtime_helpers.py:1701` — `elif function_name == "delegate_task": return agent._dispatch_delegate_task(function_args)`
- `agent/tool_executor.py:893` — `function_result = agent._dispatch_delegate_task(function_args)` (concurrent / batch path)

### 3. Slash / CLI entry points for the swarm pipeline

**`hermes_cli/orchestrator.py:1358`** — `def run_orchestrate(rest: str) -> str`
Handles `/orchestrate <prompt>`: submits a job, runs the Navigator to localize
the objective, queues the result.

**`hermes_cli/swarm/coordinator.py:400`** — `def run_swarm(goal, repo, *,
grains, decomposer, job_id, executor, memory_store, lease_store,
apply_reversible, apply_fn, claim_domains) -> SwarmResult`
> "Run the full Swarm Grainler Parallel pipeline for ``goal``."

Wired into:
- `cli.py:7836` — `"swarm": _orch.run_swarm`
- `gateway/run.py:9548` — `"orchestrator": _orch.run_orchestrator`
- `hermes_cli/background_learner/runner.py:254` (autonomous background invocation)

### 4. The AOS council dispatcher (static, registry-driven)

**`hermes_cli/jarvis_prime/aos_council/dispatcher.py:318`** — `def dispatch(
request, *, registry, max_council, effort_class) -> CouncilSession`
> "Route ``request`` to the active council + matching domain specialists."

**`hermes_cli/jarvis_prime/aos_council/dispatcher.py:635`** —
`def unified_dispatch(request, *, registry, navigator, nav_root, max_council,
nav_limit, effort_class) -> DispatchPlan`
> "Unify navigator (where) + council dispatcher (who) into one plan."

Reads `skills/aos-enterprise-council/operating-registry/registry.json`
(resolved at `dispatcher.py:81–88`, overridable via `AOS_REGISTRY_PATH` env).

### 5. The enterprise orchestrator (LLM-driven plan + retry)

**`enterprise/council.py:101`** — `def dispatch(planned, runner, *,
session_id, human_gate=_confirm_high_risk, max_retries=1, required_keys=("status",)) -> DispatchResult`
> "Drive a planned list of tasks to completion. … On schema_fail /
> policy_fail / judge_disagree, we retry up to ``max_retries`` times. …
> escalated … audit …"

Sibling `plan(goal, decomposer) -> list[PlannedTask]` at `enterprise/council.py:71`.

### 6. The cockpit chat surface (where users actually drive it)

**`gateway/cockpit/agent_full.py:257`** — `def full_agent_responder(prompt,
history, *, session_id, session_key, agent_factory, model, provider, effort,
fusion) -> Generator[dict, None, None]`
> "Stream one full-agent turn for ``prompt``."

Builds an `AIAgent` via `_create_agent` (line 154) — same constructor the
API server uses, same tool surface, same `delegate_task` access.

### 7. The recommender (offline discovery, not a market)

**`plugins/recommend/tools.py:143`** — `def handle_recommend(args, **_kw) -> str`
Catalog is a static tuple of `Surface` records (line 50), hand-curated,
keyword-substring scored. Tool name: `recommend_surfaces` (line 116).

### 8. Config knobs that gate the whole stack

**`hermes_cli/config.py:1346–1369`** — the `delegation:` block:
- `max_iterations: 50` (per child)
- `child_timeout_seconds: 600`
- `max_concurrent_children: 3` (no ceiling)
- `max_spawn_depth: 1` (clamped [1,3], `_MAX_SPAWN_DEPTH_CAP` in `delegate_tool.py`)
- `orchestrator_enabled: True` (kill switch for `role="orchestrator"`)
- `subagent_auto_approve: True` (defaults to YOLO per the comment block)

---

## GAPS — what's missing for full autonomy

### Gap 1 · Self-creating agents (M.U.S.E. forges new M.U.S.E.s)

- No API to **write a `SKILL.md` + scaffold a tool module + register it at
  runtime**. `tools/delegate_tool.py` is the *spawn* API; there is no
  *forge* API.
- The AOS roster is a **static JSON file**
  (`skills/aos-enterprise-council/operating-registry/registry.json`)
  validated by `verify_registry.py`. A MUSE cannot promote a freshly-minted
  specialist into it without a human commit.
- Needed: a `forge_agent(spec) -> skill_path` tool that scaffolds
  `skills/<slug>/SKILL.md` + a tool module, writes a registry entry, and
  re-runs `verify_registry.py`. Schema could extend `delegate_task` with
  `role="forge"`.

### Gap 2 · Self-hiring (capability-driven selection, not keyword overlap)

- `_overlap()` in `dispatcher.py:282` is **deterministic keyword scoring**.
  No semantic matching, no historical success rate, no cost model.
- AOS "engagement" is a `CouncilSession` data object — it never *hires* a
  process; the orchestrator LLM still issues `delegate_task` manually.
- Needed: a `hire_agent(capability, budget, sla) -> Contract` tool that
  returns a *contract* the orchestrator can dispatch (and that can fail
  if no candidate meets the SLA).

### Gap 3 · Market / auction of work

- No **bid surface**. `enterprise/council.py:dispatch` uses a fixed
  `runner: LeafRunner` callable — no competing implementations, no
  price discovery, no winner selection.
- No **reputation ledger**. `enterprise/audit.audit()` writes rows but
  nothing scores them per-agent (success rate, cost, latency, judge
  verdicts).
- No **payment / settlement** primitive. The closest thing is the
  `subagent_auto_approve` flag — a binary YOLO, not a budget.
- Needed: a `TaskMarket` service (probably a new module
  `hermes_cli/market/`) with: capability catalogue, bid protocol, judge
  consensus (re-use `enterprise/judge.cross_check`), settlement to a
  reputation score, and a `market.submit(task, max_bid) -> awarded_agent`
  entry point the council dispatcher can call instead of `_overlap`.

### Gap 4 · Discovery beyond keywords

- `plugins/recommend/tools.py:50` is a **hand-curated 10-entry catalog**.
  No capability embeddings, no semantic search over the AOS registry's
  `domain_specialists`, no GraphRAG integration.
- Needed: plug `jarvis_prime.graphrag` into the recommender and the AOS
  dispatcher's `_overlap` to score by semantic similarity + historical
  win-rate.

### Gap 5 · Continuous / unsupervised spawning

- `is_spawn_paused()` (`tools/delegate_tool.py:159`) is a manual kill
  switch. There is no rate limiter per agent, no cost cap, no
  per-session spawn counter surfaced to the user.
- The `cron` tool can schedule future work but **cannot trigger
  `delegate_task` on its own** — every spawn has to flow through an
  LLM turn.
- Needed: a budgeted `spawn_loop(plan, budget_tokens, budget_usd) ->
  Stream[Outcome]` that the cron job can call unattended, with hard
  kill at budget.

### Gap 6 · Cross-process / cross-host spawning

- All spawning is in-process (`ThreadPoolExecutor` in
  `delegate_tool.py`). No remote-MUSE API, no federation protocol, no
  signed delegation token. The MUSE ecosystem is one Python process
  per host.
- Needed: a `/api/v1/agents/delegate` endpoint on `gateway/platforms/api_server.py`
  that accepts a signed goal + budget and runs `delegate_task` on a
  remote MUSE, with the same `DELEGATE_BLOCKED_TOOLS` semantics.

---

## TOP 5 FILES TO READ FOR SWARM WORK

1. **`tools/delegate_tool.py`** (2811 lines)
   The single source of truth for *how* a MUSE spawns a MUSE. Reads the
   `DELEGATE_TASK_SCHEMA` (line 2670), the `DELEGATE_BLOCKED_TOOLS`
   set (line 45), the `_subagent_auto_approve` / `_subagent_auto_deny`
   callbacks (lines 73, 87), the `_normalize_role` /
   `_get_max_spawn_depth` / `is_spawn_paused` guardrails, and the
   `delegate_task(...)` entry point (line 1927). This is the file
   that has to grow a `role="forge"` branch and a `role="market"`
   branch to close Gaps 1 & 3.

2. **`hermes_cli/jarvis_prime/aos_council/dispatcher.py`** (687 lines)
   The council routing layer — `dispatch()` (line 318),
   `unified_dispatch()` (line 635), `roster()` (line 286),
   `load_registry()` (line 91). The `TaskQueue` + `DispatchPlan`
   dataclasses (lines 380–633) are the closest thing the repo has to
   a work-contract object. Replace `_overlap()` here to close Gap 2.

3. **`enterprise/council.py`** (234 lines)
   The execution half of the council: `plan()` (line 71) wraps a
   decomposer's output into risk-classified `PlannedTask`s;
   `dispatch()` (line 101) drives each task through a `LeafRunner`,
   calls `enterprise.judge.cross_check`, retries on failure, and
   escalates per `human_gate`. This is the template for any new
   market dispatcher — the audit, retry, and judge-consensus logic
   here is exactly what a bid-winner evaluator needs.

4. **`hermes_cli/swarm/coordinator.py`** (513 lines)
   `run_swarm()` (line 400) is the only place in the repo that does
   *real* parallel multi-agent execution today — `Grainler` partitions
   the goal into disjoint file-domain grains, claims them via a lease
   store, runs them via `GrainExecutor`, reconciles with a
   `_converge()` conflict backstop, and writes a Decision Ledger.
   This is the production pattern to copy for any new autonomous
   fan-out (cron-driven, market-driven, or both).

5. **`hermes_cli/jarvis_prime/tool_broker.py`** (766 lines)
   The "what counts as side-effecting" hardcoded allowlist (line 352)
   that the owner-gate and approval layer enforce — `delegate_task`
   is on it (line 359). **Any new `role="forge"` or `role="market"`
   branch in `delegate_task` MUST be added here too**, or it will
   silently slip past the owner gate. Read lines 340–365 before
   shipping Gap 1 / Gap 3.

**Honourable mention** (read second):
- `skills/aos-council-director/SKILL.md` — the canonical playbook for
  what an orchestrator LLM is *supposed* to do today. It's the user-
  facing spec the director must follow when dispatching; any new
  autonomous orchestration has to be at least as disciplined.
- `hermes_cli/config.py:1346–1369` — the `delegation:` config block.
  All five new knobs for autonomy (budget, SLA, reputation weight,
  forge allowlist, market endpoint) belong here.
