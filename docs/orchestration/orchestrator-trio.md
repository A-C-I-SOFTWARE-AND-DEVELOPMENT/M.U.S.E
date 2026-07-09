# The Orchestrator Trio — planner / executor / critic in one install

A ready-made three-role team for muse orchestration, installed by the
setup wizard (`hermes setup trio`) or offered at the end of the full
wizard. It maps the classic **Orchestrator-Worker harness** pattern onto
muse's existing five primitives — no new machinery, just profiles and
routing config:

| Role | Profile | Model | Why this model |
|---|---|---|---|
| Global orchestrator & planner | `orchestrator` | `z-ai/glm-5.2` (OpenRouter) | Project-level coherence over 50+ step loops; 1M-token context holds the whole repo, module boundaries, and historical decisions without fragmenting |
| Tactical executor & tool caller | `executor` | `meituan/longcat-2.0` (OpenRouter) | Distilled "Agent Expert" tuning for tool use and self-correction; recovers well when a command fails or an API errors |
| Independent reviewer & critic | `critic` | `x-ai/grok-4.5` (OpenRouter) | Frontier reasoning from a third vendor — reviews are independent of both the planner's and the builder's failure modes |

Beyond the trio, the preset ships an **extended bench** for teams that
want the full six-seat roster:

| Role | Profile | Model |
|---|---|---|
| Long-context researcher | `researcher` | `moonshotai/kimi-k2` |
| Operations & infrastructure | `operator` | `deepseek/deepseek-v4` |
| Documentation & knowledge curator | `scribe` | `minimax/minimax-m2` |

Everything routes through OpenRouter, so a single `OPENROUTER_API_KEY`
serves the whole roster. The models carry the `candidate` tag in
[`config/model-catalog.yaml`](../../config/model-catalog.yaml) — confirm
availability on OpenRouter's live model list before relying on them for
spend, and swap any role's model with
`hermes -p <profile> model` if you prefer a different engine. The
routing playbook the agent itself follows lives at
[`skills/orchestration/seat-roster/SKILL.md`](../../skills/orchestration/seat-roster/SKILL.md).

## Install

```bash
hermes setup trio          # interactive, opt-in: core trio or full roster
```

Headless / scripted installs call the Python API directly:

```bash
python -c "from hermes_cli.orchestrator_trio import install_trio; print(install_trio())"                 # core trio
python -c "from hermes_cli.orchestrator_trio import install_trio; print(install_trio(extended=True))"   # full roster
```

The installer is **idempotent and conservative**: existing profiles are
kept, a profile's model is only written when it has none, descriptions
are only written when empty, and kanban routing keys are only set when
unset. It never silently overwrites a choice you already made. Re-pin
everything to the preset with `install_trio(force=True)`.

## How the division of labor maps onto muse primitives

The harness loop — *plan → dispatch → execute → verify → merge or
reject* — is already what the orchestration stack does. The trio just
pins the right model to each seat:

1. **Context initialization (planner).** `kanban.orchestrator_profile`
   is set to `orchestrator`, so triage decomposition runs on GLM-5.2.
   It is the only role that needs the heavy global context; it breaks
   the goal into atomic, dependency-mapped cards (the **task graph**)
   and every decision lands in the **decision ledger**.
2. **Task dispatch (harness logic).** The kanban dispatcher promotes
   dependency-satisfied cards to ready and spawns
   `hermes -p <assignee> …` per card. `kanban.default_assignee` is set
   to `executor`, and roster-description matching routes
   implementation-shaped cards there too.
3. **Tool execution & coding (executor).** LongCat-2.0 sees one bounded
   ticket at a time — the files that ticket needs, not the whole
   repo. That is the context-window economics of the pattern: only the
   planner pays for global context.
4. **Verification & QA (critic).** Review-shaped cards route to the
   `critic` profile by description matching, and **validation gates**
   (schema, policy, optional judge call) run on every worker result.
   Builder ≠ reviewer is preserved — the critic never gets its own
   build tasks, and a builder never self-merges.
5. **Merge or reject (harness logic).** Approved work proceeds through
   the normal owner gates (main-branch merge stays owner-gated); a
   rejection loops the critique back to the executor as a follow-up
   card.

## Why each role keeps improving

Every role is a full hermes **profile** — an isolated `HERMES_HOME`
with its own memory backend, skills, `SOUL.md`, and job history. That
persistence is the improvement loop:

- The `orchestrator` accumulates architectural decisions and
  decomposition patterns across jobs.
- The `executor` accumulates project-specific skills (and can grow new
  ones through the skill-creation loop).
- The `critic` accumulates the failure catalog — what actually broke
  before ships into its next review.

`hermes profile list` shows the roster; each profile's description (in
`<profile>/profile.yaml`) is what the decomposer routes by, so refining
those descriptions refines the routing.

## The rejection loop

With the seats installed, one config flip closes the plan → build → verify
loop (off by default — completions go straight to `done` exactly as before):

```yaml
kanban:
  review_before_done: true     # builder completions land in `review`, not `done`
  reviewer_profile: critic     # builder ≠ reviewer, enforced by routing
  review_reject_limit: 3       # then the task parks in `blocked` for a human
```

The flow: a builder's `kanban_complete` parks the task in the **review**
column; the dispatcher's review lane spawns the reviewer (with the
`sdlc-review` skill loaded), which either completes the task — that IS the
approval, emitting `review_approved` — or calls **`kanban_reject`** with a
critique. The critique lands as a comment the builder sees in its context
on the rework run, the task returns to `ready` under the original builder,
and children are only promoted on real completion. Every hop is an event
(`review_requested` / `review_approved` / `review_rejected`), so
`kanban_db.review_stats()` gives per-profile approve/reject counters and
`profile_outcome_stats()` gives per-profile run outcomes.

## The improvement flywheel

Each seat compounds across jobs through three additive hooks:

- **Roster descriptions learn from history** — `hermes profile describe
  --auto` now folds each profile's measured kanban history (run outcomes,
  review approve/reject counts) into the description prompt, so routing
  reflects what a seat has actually done, not just its skill list.
  User-authored descriptions are never overwritten.
- **Job outcomes feed the learning dataset** —
  `learning_ingest.from_kanban_outcome(task_id, store)` turns a finished
  task attempt into a dataset candidate: failures become
  `negative_example` traces automatically; successes become positive
  traces **only** with real gate evidence (`quality=QualityGates(...)`) —
  a "passed" example is never auto-minted, and export stays owner-gated.
- **Model portfolio proposals** — `python -m hermes_cli.jarvis_prime seats
  report` shows each seat's pinned model, measured scorecard evidence, and
  catalog candidates; `seats propose <seat> <candidate_ref>` stages an
  owner-gated swap proposal (RC2, with rollback) into the standard
  proposals queue. Nothing is ever applied without the owner's exact
  `Yes, with authorization.` — vendor benchmarks never promote; only
  measured scorecards do.

## Going global

- **Cockpit**: `GET /v1/cockpit/seats` reports every seat's installed
  state, pinned vs preset model, and the kanban routing — the roster is
  visible from the dashboard and the Android app.
- **Distribution**: `orchestrator_trio.export_seat_distributions(dest)`
  stages each installed seat as a single-profile distribution directory
  (manifest + payload, credentials stripped, `.env.EXAMPLE` generated)
  ready for `hermes profile install`. Publishing the staged repos
  anywhere is owner-gated — the export never touches the network.

## Tuning

- **Swap a model:** `hermes -p executor model` (or edit
  `~/.hermes/profiles/executor/config.yaml`).
- **Change routing:** `kanban.orchestrator_profile` and
  `kanban.default_assignee` in `~/.hermes/config.yaml`.
- **Add more seats:** the trio is a starting roster, not a limit —
  `hermes profile create researcher --description "…"` adds a fourth
  seat the decomposer can route to immediately.
- **Status:** `python -c "from hermes_cli.orchestrator_trio import trio_status; print(trio_status())"`.

See also: [getting-started.md](getting-started.md) for your first job,
[parallel-workers-and-worktrees.md](parallel-workers-and-worktrees.md)
for how parallel cards stay isolated, and
[agent-design-patterns.md](agent-design-patterns.md) for the pattern
vocabulary this preset instantiates.
