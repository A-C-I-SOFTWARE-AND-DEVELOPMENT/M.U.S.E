# Self-Improvement Loop — Orchestration

This document is the operational counterpart to
`skills/self-improvement-loop/SKILL.md`. The skill says *what* a
worker must do at the end of every job; this doc says *where things
live*, *who runs what*, and *how proposals turn into durable
improvements*.

Mission anchor: `docs/mission/best-coding-tool-mission.md`.
Related runtime: `enterprise/` (council orchestrator + monitor),
`agent/curator.py` (curator drafts lane).

## Why we have a loop

Principles 8 and 9 of the mission:

> 8. muse learns from every job.
> 9. Current AI improvements update the routing policy.

A job that produced output but did not feed those two principles is
incomplete. The loop is the bookkeeping that makes "muse learns"
something you can audit rather than something you have to take on
faith.

## Lifecycle of one job

```
prompt
  │
  ▼
[best-coding-tool-mission]  ── writes goal.txt, routing.md, publish.md
  │
  ▼
orchestrator dispatches workers
  │  ├─ planner       → plan.md / plan.json
  │  ├─ builder(s)    → diffs/, transcripts/
  │  ├─ reviewer      → scorecard.json
  │  └─ publisher     → publish.md (with undo paths)
  │
  ▼
[self-improvement-loop]     ── reads everything above, writes proposals/
  │
  ▼
curator / monitor           ── promotes, applies, or defers proposals
  │
  ▼
next prompt is cheaper / faster / more correct
```

The two skill bookends — `best-coding-tool-mission` at the start and
`self-improvement-loop` at the end — are required. The orchestrator
will not mark a job complete without the trailer that the loop emits.

## Artifact directory layout

Every job gets its own directory. Default root:
`~/.hermes/jobs/<YYYY-MM-DD>/<job-id>/`. The job id is the short id
the orchestrator already prints when it dispatches.

```
<job-id>/
├── goal.txt                  # written by best-coding-tool-mission
├── routing.md                # worker/model mix + rationale
├── plan.md  or plan.json     # the dispatched plan
├── transcripts/
│   ├── planner-001.md
│   ├── builder-001.md
│   └── reviewer-001.md
├── diffs/
│   ├── 001.patch
│   └── 002.patch
├── evidence/
│   ├── test-output.txt
│   ├── screenshots/
│   └── eval-runs/
├── scorecard.json            # one per worker output, or one rollup
├── publish.md                # external actions + their undo paths
└── proposals/                # written by self-improvement-loop
    ├── prop-1a2b3c4d.json
    └── prop-5e6f7080.json
```

The directory is the durable artifact contract from Principle 4.
Workers may write into it; nothing may delete from it after the
trailer is written (history is append-only).

## Proposal storage

Active drafts live in:

```
~/.hermes/self-improvement/drafts/prop-<8hexchars>.json
```

The shape is defined in `skills/self-improvement-loop/SKILL.md`
("Write proposals"). Each proposal carries:

- the `kind` (skill_gap, new_skill, routing_miss, prompt_regression,
  tool_gap, evidence_gap, mission_drift),
- the `target` file or component,
- `evidence` pointers (relative paths inside the job directory or
  scorecard JSON-pointer fragments),
- `evidence_event_count` (1 on first sighting),
- the `proposed_change`,
- the expected `scorecard_delta_expected` (which axes should
  improve, by how much),
- which `principles` it serves (`P1`..`P10`),
- whether the change is `reversible`, and its undo path in `extra`.

## Routing of proposals

| destination | when |
|---|---|
| **applied immediately**, then archived under `~/.hermes/self-improvement/applied/` | Tag-only edits, additive routing-weight nudges (`<= 1` notch), additive policy rows. Must be reversible and must record `extra.previous_value`. |
| **curator drafts lane** (`agent/curator.py`) | Prompt edits, new skills, removed skills, ACL changes, risk reclassifications, any non-trivial routing changes. |
| **deferred** in `~/.hermes/self-improvement/drafts/` | The loop could not categorise the finding. Surfaced to the user as a count + one-line summary. |

## K=3 confirmation rule

A single-event finding (`evidence_event_count == 1`) does not
auto-promote unless the proposal carries `extra.user_confirmed =
true`. When the same `kind` + `target` pair appears across **three
consecutive jobs**, the loop auto-promotes the latest proposal to
the curator drafts lane.

This mirrors the enterprise-council monitor; see
`skills/enterprise-council/monitor/SKILL.md`. The intent is the
same: avoid thrashing on noise, but do not require manual
intervention for patterns the data has already proven.

## Routing policy as a living artifact (Principle 9)

When new capabilities appear — a new model, a new provider, a new
local executor, a new tool — the loop must emit a `routing_miss`
proposal even if the current job did not directly fail because of
the gap. The proposal names:

- the new capability (e.g. "local Codex-class model now available on
  device", "GPT-5.x provider added"),
- the routing slot it should be considered for
  (planner / builder / reviewer / cheap-loop / hard-loop / on-device
  fallback),
- the suggested weight change (small; the curator handles bigger
  reshuffles),
- the expected `scorecard_delta_expected` (typically `cost_efficiency`
  and `speed`, sometimes `local_first_fit`).

The router reads applied proposals on next dispatch. The user can
inspect the current policy at any time via the orchestrator's
"routing" surface.

## Reversibility (Principle 7) applies to the loop itself

Any change the loop applies directly must record its own undo path
in `extra.undo`. If a change cannot describe how to revert itself,
the loop must downgrade it to "promote to curator" and not apply it.
The loop is not allowed to leave the repo or the routing policy in a
state the user cannot back out of.

## Failure modes and how they are handled

| symptom | handling |
|---|---|
| Job ended without a `scorecard.json` | Loop emits a `mission_drift` proposal against Principle 5 and tags the job as untrusted. |
| `goal.txt` missing | Loop emits a `mission_drift` proposal against Principle 1 (or the orchestrator, if it dispatched without a goal) and asks the user whether to backfill. |
| Worker self-scored 10s across the board with no evidence | Loop re-scores from `diffs/` + `evidence/` and records the disagreement as its own `prompt_regression` finding against the worker. |
| Publish happened without an entry in `publish.md` | Loop emits a `mission_drift` proposal against Principle 7 and surfaces it as **high priority** to the user. |

## Where this hooks into the rest of the repo

- `enterprise/monitor` already implements a very similar post-run
  review for the enterprise council; the self-improvement loop is
  the **repo-wide** version that runs for every coding job, not just
  council runs. The two should stay aligned — proposals from either
  source land in the same `~/.hermes/self-improvement/drafts/`
  directory and are handled by the same curator.
- `agent/curator.py` is the existing drafts/promotion mechanism.
  This loop is a producer; the curator stays the gatekeeper.
- `apps/android/` (the cockpit) surfaces the loop's trailer line as
  the last thing the user sees for a job. That trailer is the
  visible proof that the loop ran.
