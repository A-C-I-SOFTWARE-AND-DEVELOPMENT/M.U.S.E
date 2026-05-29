# Continuous Monitors & Daily Owner Brief

Status: **shipped** (policy/aggregation); live collectors are the
documented remaining integration step. Files:
`hermes_cli/jarvis_prime/monitors.py`,
`hermes_cli/jarvis_prime/owner_brief.py`. Tests:
`tests/test_jarvis_prime_monitors.py`,
`tests/test_jarvis_prime_owner_brief.py`.

## Monitors (read-only)
`MonitorBoard.default()` ships eight monitors: repo state, open PRs,
failing tests, stale docs, memory contradictions, skill proposals, model
failures, Android capability.

Each `check(context)` returns a `MonitorResult` with a `Severity`
(`ok` / `info` / `warning` / `critical` / `blind`). Key properties:

- **Read-only**: monitors observe a supplied context mapping; they never
  mutate state or perform owner-gated actions.
- **Fail-visible**: a monitor whose source is missing returns `BLIND`
  rather than silently passing; a throwing monitor is caught and reported
  as `BLIND` with an incremented `failure_count`.
- Per-source `last_success_at` and `failure_count` are tracked, so a
  silent/blind monitor is itself visible (blind-spot detection).

## Daily owner brief
`build_owner_brief(results, board=...)` produces an `OwnerBrief`:

- what changed · what matters · what needs approval · what is blocked ·
  what JARVIS learned · **monitor coverage attestation** (observed vs total
  + explicit blind spots).

`render()` formats it; `to_dict()` is JSON-friendly.

## Live collectors (`monitor_collectors.py`)
`monitor_collectors.collect_context()` assembles a real context from
locally observable, **read-only** sources:

- `repo` — `git status --porcelain` + current branch (no mutation; the
  command runner is injectable for tests).
- `open_contradictions` — `MemoryTreeStore.open_contradictions()`.
- `model_failures` — scorecards with test failures / repeated errors.
- `pending_proposals` — a proposals JSONL, if present.
- `tests` — supplied test results, if any.

Sources with no local collector yet (`open_prs`, `docs`, `android`) are
intentionally omitted so their monitors report BLIND — an honest coverage
gap rather than a fabricated OK.

## CLI
```bash
# Live local state (git, memory contradictions, scorecards, proposals):
python -m hermes_cli.jarvis_prime owner-brief --auto
python -m hermes_cli.jarvis_prime owner-brief --auto --memory-store ~/.hermes/jarvis_prime/memory_tree.jsonl --json
# Empty context → every source reports blind (the honest signal):
python -m hermes_cli.jarvis_prime owner-brief --json
# With a supplied monitor context file:
python -m hermes_cli.jarvis_prime owner-brief --context monitors.json
```

The context JSON may include `repo`, `open_prs`, `tests`, `docs`,
`open_contradictions`, `pending_proposals`, `model_failures`, `android`,
plus `changed` / `learned` / `blocked` lists for the brief.

## Owner gates / rollback / risks / remaining
- Owner gates: none (read-only; git is read-only `status`/`rev-parse`).
- Rollback: additive modules; revert branch.
- Remaining: GitHub PR list, docs-freshness, and Android-capability
  collectors (these need network / a docs manifest / a device snapshot).
  Until added they surface as honest blind spots in the coverage
  attestation.
