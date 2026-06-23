# muse orchestration — phase log

This file records the orchestration phases delivered against the muse
codebase. Each phase entry summarises what shipped, where to find it, and
what was deliberately deferred.

> **Status:** Phase 24 is the final release-hardening phase.

## Phase 24 — Release hardening and 10/10 final gate

**Branch:** `claude/hermes-release-hardening-10-10-Wx2MN`
**Date:** 2026-05-23

### What landed

- `scripts/hermes-orchestrate.sh` — bash entry point that parses CLI flags,
  validates the environment, and dispatches the Python orchestrator. Passes
  `bash -n` syntax check.
- `hermes_cli/orchestrator.py` — fan-out coordinator. Spawns one worker per
  member of `ALL_WORKERS` in parallel via `ThreadPoolExecutor`, each in its
  own sandboxed git worktree (`.hermes/worktrees/<worker>-<task_id>`).
  Falls back to a directory copy when the repo is not a git checkout so
  unit tests can run hermetically.
- `hermes_cli/workers/` — six concrete workers
  (`codex`, `claude`, `opencode`, `kanban`, `council`, `hermes`) plus a
  shared `Worker` base with deterministic, network-free heuristics.
- `hermes_cli/scoring.py` — four-signal weighted scorer
  (success, structure, coverage, hint) with weights that sum to 1.0.
- `hermes_cli/arbiter.py` — picks a single winner, a draw, or abstains
  below `MIN_PASS_SCORE`.
- `hermes_cli/merge_engine.py` — produces a single `MergeArtifact`, either
  the winner's proposal or a side-by-side union when the arbiter flagged
  a draw.
- `hermes_cli/validation_gates.py` — five gates (`structure`, `size`,
  `secrets`, `unicode`, `policy`). Every gate is stdlib-only and
  deterministic.
- `hermes_cli/github_publisher.py` — emits a `PublishDescriptor` (PR or
  issue). Dry-run by default; live mode requires both
  `HERMES_PUBLISH_LIVE=1` and a caller-supplied transport. No embedded
  credential path.
- Tests: `tests/test_orchestrator.py`, `tests/test_worker.py`,
  `tests/test_scoring.py`, `tests/test_merge_engine.py`,
  `tests/test_validation_gates.py`, `tests/test_github_publisher.py`
  (60 tests total, all passing).
- Docs: `docs/orchestration/final-10-10-readiness-report.md`,
  `release-checklist.md`, `known-limitations.md`, `next-roadmap.md`.

### Validation evidence

```
$ bash -n scripts/hermes-orchestrate.sh          # OK
$ python -m py_compile hermes_cli/*.py hermes_cli/workers/*.py   # OK
$ pytest tests/test_orchestrator*.py tests/test_worker*.py \
         tests/test_scoring.py tests/test_merge_engine.py \
         tests/test_validation_gates.py tests/test_github_publisher.py -q
60 passed
```

End-to-end smoke (against a throwaway repo at `/tmp/demo-repo`) confirms:

- six sandboxed git worktrees created and torn down per run,
- arbiter, scoring, and merge engine wired correctly,
- five gates run and report PASS,
- publisher writes a JSON descriptor under `.hermes/publish/` and never
  contacts the network in dry-run mode.

### Out of scope

- Direct execution of worker proposals (workers describe what they would
  do; they never apply patches). See
  `docs/orchestration/known-limitations.md`.
- Live PR/Issue creation. The transport is a plug-in seam; the default
  build ships with no transport so it cannot accidentally publish.
- Multi-repo orchestration; see `docs/orchestration/next-roadmap.md`.
