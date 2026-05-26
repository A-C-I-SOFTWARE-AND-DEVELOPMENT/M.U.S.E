# Jarvis Prime task & worker command cards

This document describes the Jarvis Prime extension of the Hermes Android
companion app. The Hermes task model (`HermesTask`,
`HermesTaskRepository`) and the existing Orchestrator / Task Detail screens
were extended in place — there is no second task store or second screen.

## Where things live

| Concern | File |
| --- | --- |
| Task model + Jarvis enums | `app/src/main/java/com/aci/hermes/data/model/HermesTask.kt` |
| Persistence + legacy-status migration | `app/src/main/java/com/aci/hermes/data/orchestrator/HermesTaskRepository.kt` |
| Dashboard (worker lanes + sectioned task list) | `app/src/main/java/com/aci/hermes/ui/screens/orchestrator/OrchestratorScreen.kt` |
| Dashboard ViewModel (sectioning + lane state) | `app/src/main/java/com/aci/hermes/ui/screens/orchestrator/OrchestratorViewModel.kt` |
| Task editor (new Jarvis fields) | `app/src/main/java/com/aci/hermes/ui/screens/orchestrator/TaskDetailScreen.kt` |
| Editor ViewModel (new field setters) | `app/src/main/java/com/aci/hermes/ui/screens/orchestrator/TaskDetailViewModel.kt` |
| Nav wiring for Approvals / Audit links | `app/src/main/java/com/aci/hermes/ui/navigation/HermesNavGraph.kt` |
| Strings | `app/src/main/res/values/strings.xml` |
| Tests | `app/src/test/java/com/aci/hermes/...` |

## Data model additions

`HermesTask` keeps every original field and adds Jarvis Prime worker-card
metadata:

| Field | Type | Purpose |
| --- | --- | --- |
| `riskTier` | `RiskTier` | Blast-radius label (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). Rendered as a chip on every card. |
| `approvalState` | `ApprovalState` | `NOT_REQUIRED` / `PENDING` / `APPROVED` / `REJECTED`. Drives the Approvals chip + deep-link CTA. |
| `workerPhase` | `WorkerPhase` | Which lane the task is currently routed through. Independent of `status` — a blocked task remembers its lane. |
| `evidenceSummary` | `String?` | Short summary of the evidence Jarvis gathered before acting. |
| `blockedReason` | `String?` | Surfaced on every card whose `status == BLOCKED`. |
| `rollbackSummary` | `String?` | What rollback / undo plan was prepared. |
| `verificationResult` | `String?` | Result of the post-execution verification gate. |
| `proofLink` | `String?` | Audit / proof URL. Preferred destination for the Open Audit CTA. |
| `nextAction` | `String?` | Concrete next step the user (or another worker) should take. Already existed; reused. |
| `emergencyStopActive` | `Boolean` | When `true`, contributes to the dashboard emergency-stop banner. |

### Worker phases

```
PLANNER → NAVIGATOR → EDITOR → EXECUTOR → REVIEWER → JARVIS_FINAL_SYNTHESIS
```

`WorkerPhase` is rendered in the **Worker lanes** dashboard card. A lane
lights up (uses the `primaryContainer` color and shows the active task
title) when any task is currently mapped to it.

### Task statuses

The status enum is now the Jarvis Prime lifecycle:

```
draft, queued, planning, navigating, editing, executing, reviewing,
waiting_for_approval, blocked, failed, complete, stopped
```

Status routes deterministically into one Tasks-screen section:

| Status | Section |
| --- | --- |
| `DRAFT`, `QUEUED`, `PLANNING`, `NAVIGATING`, `EDITING`, `EXECUTING`, `REVIEWING`, `STOPPED` | **Active** |
| `WAITING_FOR_APPROVAL` | **Waiting for approval** |
| `BLOCKED` | **Blocked** |
| `FAILED` | **Failed** |
| `COMPLETE` | **Complete** |

The Tasks screen always renders all five sections in this order. Empty
sections show a one-line empty-state caption rather than disappearing, so
the user sees the same shape every visit.

## Migration from Hermes-era envelopes

`HermesTaskRepository` decodes its JSON envelope through `decodeEnvelopeText`,
which walks each task object and rewrites legacy status values before
deserialization:

| Legacy status | Migrated to |
| --- | --- |
| `READY_FOR_HANDOFF` | `QUEUED` |
| `HANDED_TO_CODEX` | `EXECUTING` |
| `HANDED_TO_CLAUDE` | `REVIEWING` |
| `IN_REVIEW` | `REVIEWING` |
| `NEEDS_REVISION` | `BLOCKED` |

Unknown keys are ignored (`Json { ignoreUnknownKeys = true }`), so any
field the user persisted before the upgrade is preserved on the next
write. Missing Jarvis fields default to safe values (`RiskTier.LOW`,
`ApprovalState.NOT_REQUIRED`, `WorkerPhase.PLANNER`, no narrative,
emergency stop off).

The envelope `version` field bumps from `1` to `2` on the next write
after migration.

## Card surfaces

Every task card renders:

- title
- chips: task type, status, target tool
- chips: `Risk: <tier>`, `Phase: <worker phase>`, `Approval: <state>` (when not `NOT_REQUIRED`)
- description (truncated)
- evidence summary, when present
- **blocked reason** when `status == BLOCKED` (emphasised in error color)
- **failure** when `status == FAILED` — uses `resultNotes` or "No failure notes recorded."
- rollback summary, when present
- verification result, when present
- next action, when present
- bottom actions: `Copy prompt`, `Open task`, plus:
  - `Open Approvals` when `approvalsRoute()` is non-null
  - `Open Audit` when `auditRoute()` is non-null

## Approvals & Audit links

Two pure extension functions on `HermesTask` compute the deep-link
destinations:

- `approvalsRoute()` returns `"approvals/<id>"` when the task is
  `WAITING_FOR_APPROVAL` or its `approvalState == PENDING`. Otherwise
  null and no CTA appears.
- `auditRoute()` returns the explicit `proofLink` if present, otherwise
  `"audit/<id>"` for `COMPLETE` tasks. Returns null when the task is
  in-flight without a proof link.

`HermesNavGraph` maps the CTAs to navigation:

- `approvals/<id>` and `audit/<id>` open the task editor for that id.
- An http(s) `proofLink` is opened via `ACTION_VIEW` so the system
  browser handles it.

This keeps the surface UI-only (no new screens) while still wiring the
Tasks screen into the words "Approvals" and "Audit" the worker spec
calls out.

## Emergency-stop awareness

A red banner appears at the very top of the dashboard whenever any task
has `emergencyStopActive = true`. Pressing **Clear stop** clears the flag
on every task at once via `OrchestratorViewModel.clearEmergencyStop()`.
Tasks with an active emergency stop are also excluded from the Worker
lanes view so the lane state mirrors reality.

The same `Emergency stop` switch appears on the Task Detail editor so
the flag can be set or cleared on a single task.

## Test coverage

`apps/android/app/src/test/java/com/aci/hermes/...`:

- `HermesTaskTest` — default values, every status maps to a section,
  worker-lane mapping, blocked / failed narrative, Approvals & Audit
  routes.
- `HermesTaskRepositoryMigrationTest` — every legacy status name maps
  to its Jarvis equivalent; missing Jarvis fields default in; modern
  envelopes pass through unchanged; corrupt envelopes don't crash.
- `OrchestratorSectioningTest` — every status lands in exactly one
  section bucket; blocked / failed / waiting / complete tasks survive
  the sectioning step with their narrative; worker lanes light up for
  each routing status; emergency-stop tasks vacate the lane.

Run them with:

```
cd apps/android && ./gradlew testDebugUnitTest
```

## Build

```
cd apps/android && ./gradlew assembleDebug
```
