# Unified Navigator + Dispatcher

> Closes gap-analysis findings **G03**: *"navigator/planner is not unified"* and
> *"dispatcher/task queue is not generalized"*. See
> `docs/audits/hermes-10-10-gap-report.md` (Gaps 10 & 12) and
> `docs/audits/hermes-full-repo-audit.md`.

## The problem this unifies

Before G03 the repo carried **two independent pre-dispatch planners that never
met**:

| Planner | Question it answers | Code | Ledger record |
|---|---|---|---|
| **Navigator** | *Where* to edit — issue localization, ranked edit sites, tests to run | `hermes_cli/jarvis_prime/navigation/navigator.py` | `navigation_decision` |
| **Council Dispatcher** | *Who* engages — routes a request to AOS council members + domain specialists | `hermes_cli/jarvis_prime/aos_council/dispatcher.py` | (ad-hoc, none) |

A coding job consulted both, recorded two separate decisions, and the council
dispatcher was **registry-specific** — it could only route to council members
listed in `skills/aos-enterprise-council/operating-registry/registry.json`, and
spoke no task-queue contract. The pipeline doc
(`hermes-orchestration-pipeline.md`) defines a `queue.json` contract
(`pending` / `in_flight` / `completed` / `failed`) that the dispatcher did not
implement.

## The unification — extend, don't duplicate

G03 does **not** introduce a parallel architecture. It **extends the existing
`dispatcher.py` in place** with one additive layer built *on top of* the
unchanged `dispatch()` / `CouncilSession` primitive:

```
                    unified_dispatch(request, navigator=?, registry=?)
                                   │
            ┌──────────────────────┼───────────────────────┐
            ▼                      ▼                       ▼
     dispatch(request)      navigator.navigate(req)   _build_tasks(...)
     → CouncilSession       → NavigationResult        → [Task, ...]
       (who engages)          (where to edit)            │
            │                      │                      ▼
            └──────────────────────┴────────────►  TaskQueue (queue.json)
                                                      │
                                                      ▼
                                                 DispatchPlan
                                            (one ledger record:
                                             dispatch_decision)
```

### New surface (all in `hermes_cli.jarvis_prime.aos_council`)

| Name | What it is |
|---|---|
| `Task` | One dispatchable unit: `{id, assignee, kind, status, payload}`. `kind` is `"council"`, `"specialist"`, `"edit_site"`, or caller-defined — so the queue is not coupled to the registry. |
| `TaskQueue` | Generalized queue matching the `queue.json` contract: `pending` / `in_flight` / `completed` / `failed`, with `claim()` / `complete()` / `fail()` transitions. Storage-agnostic; `to_dict()` serializes to the contract shape a caller persists. |
| `DispatchPlan` | The unified decision: `{request, session (CouncilSession), navigation (NavigationResult|None), queue (TaskQueue)}`. Emits **one** `dispatch_decision` ledger record and **one** worker packet. |
| `unified_dispatch()` | The single entry point. Calls `dispatch()` for the *who* and `Navigator.navigate()` for the *where`, then composes both into a `DispatchPlan` with a `TaskQueue`. |

### What did NOT change

- `dispatch()` — registry routing, byte-identical. `unified_dispatch` calls it.
- `CouncilSession` / `CouncilMember` — unchanged.
- `executor.execute()` — unchanged; still runs a `CouncilSession` through an
  injected runner. The unified plan's `session` field is exactly what
  `execute()` consumes.
- `Navigator` / `NavigationResult` — unchanged; `unified_dispatch` calls
  `navigator.navigate()` and reuses `NavigationResult.worker_packet()` /
  `to_ledger_record()` verbatim.

The existing tests (`test_aos_council_dispatcher.py`,
`test_aos_council_executor.py`) pass unmodified.

## Why "extend, don't duplicate"

The gap analysis's instruction was explicit: **do not create a sixth
orchestration primitive**. The five primitives (Job, Worker, Model routing,
Validation gate, Decision ledger) are unchanged. The unification is a
**composition** of two existing planners behind one entry point, plus a
generalized queue that lets the existing dispatcher emit tasks for *any*
consumer (council member, edit site, or a downstream worker adapter) rather
than only registry members.

No new package, no new primitive, no forked routing logic — `unified_dispatch`
delegates to `dispatch` + `Navigator.navigate` and only adds the composition.

## How the orchestrator uses it

```python
from hermes_cli.jarvis_prime.aos_council import unified_dispatch
from hermes_cli.jarvis_prime.navigation.navigator import Navigator

nav = Navigator.for_repo(".")
plan = unified_dispatch(
    "Fix the timeout in the issue localizer and have the council review it",
    navigator=nav,
)

# One ledger record (was two: navigation_decision + ad-hoc council).
ledger.append(plan.to_ledger_record(job_id=job_id))

# One worker packet (where to edit + who reviewed + what to verify).
packet = plan.worker_packet()

# A generalized queue the controller drains (queue.json contract).
queue_json = plan.queue.to_dict()
```

For a **non-code** request (no navigator), the plan is council-only and
`navigation` is `None`:

```python
plan = unified_dispatch("advise on pricing and positioning", registry=reg)
assert plan.navigation is None          # no edit sites
assert plan.to_ledger_record()["kind"] == "dispatch_decision"
```

## Task queue contract

The `TaskQueue` is the generalization that closes "dispatcher not generalized".
It matches the on-disk `queue.json` shape from
`hermes-orchestration-pipeline.md`:

```json
{
  "pending":   [{"id": "council:council-director", "assignee": "council-director", "kind": "council",   "status": "pending",   "payload": {...}}],
  "in_flight": [],
  "completed": [],
  "failed":    []
}
```

Lifecycle: a controller calls `claim(id)` → `in_flight`, then `complete(id)` or
`fail(id)`. Tasks are derived from the engaged council members (one per member)
and, when navigation is present, one per ranked edit site — so the same queue
serves both "who reviews this" and "which files get edited" without a second
dispatcher.

## Relationship to the five primitives

| Primitive | Unification effect |
|---|---|
| **Job** | A job now records one `dispatch_decision` instead of a split navigation + council entry. |
| **Worker** | The `TaskQueue` generalizes dispatch beyond registry members to any `assignee` a worker adapter resolves. |
| **Model routing** | Unchanged. |
| **Validation gate** | Unchanged; the plan's `verify_with` (from navigation) feeds the existing `tests` gate. |
| **Decision ledger** | `DispatchPlan.to_ledger_record()` is the single audit record; `navigation` is embedded, not a sibling record. |

## Test coverage

`tests/hermes_cli/test_aos_council_unified_dispatch.py` — 12 hermetic tests
(synthetic registry + fake Navigator; no repo indexing, no model, no FS writes)
covering:

- council-only vs. navigator-composed plans,
- the `queue.json` contract shape and `claim`/`complete`/`fail` lifecycle,
- the single `dispatch_decision` ledger record (with and without navigation),
- the combined worker packet (candidate files + council + queue),
- edit-site tasks carrying rank/confidence/suggested-tests.

Run with:

```bash
python -m pytest tests/hermes_cli/test_aos_council_unified_dispatch.py -q
```

## See also

- `docs/orchestration/hermes-orchestration-pipeline.md` — the `queue.json`
  contract the `TaskQueue` implements.
- `docs/orchestration/swarm-grainler-parallel.md` — the swarm decomposer, which
  is a *separate* code-producing pipeline; the unified dispatcher composes with
  the Navigator, not the swarm grainler.
- `docs/android/cockpit-canonical-contract-plan.md` — the cockpit
  `GET /v1/cockpit/navigation` surface reads `navigation_decision` entries;
  the unified `dispatch_decision` record embeds that same navigation payload,
  so the cockpit surface continues to work.
- `docs/audits/hermes-10-10-gap-report.md` — Gaps 10 (skill-aware routing) and
  12 (multi-host orchestration) that motivated the generalization.
