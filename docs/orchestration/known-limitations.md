# muse orchestration — known limitations

This document is the honesty contract for Phase 24. Every component that
is mocked, stubbed, or otherwise not yet production-grade is listed here
with its location and the reason it landed in this state. If you ship a
fix, *remove* the corresponding bullet from this file in the same PR.

## 1. Worker proposals are descriptive, not executable

**Where:** `hermes_cli/workers/*.py`.
**What:** Each worker returns a Markdown proposal that *describes* what
it would do. None of the workers actually mutate files in their
worktree. The worktree exists so that, in a follow-on phase, workers
*can* mutate it without colliding — the substrate is ready; the actuator
is not.
**Why:** Phase 24's mandate was release hardening, not closing the
mutate-and-merge loop. Hooking a real model call (Codex, Claude, etc.)
would have introduced a paid-API dependency that the phase explicitly
forbade.
**Mitigation:** The arbiter / merge engine / gates / publisher are all
shaped to handle real proposals the day a worker starts writing patches.

## 2. Workers do not call external models

**Where:** every worker's `_execute` method.
**What:** Heuristics are derived from local repo structure (file counts,
SKILL.md presence, SECURITY hits). No HTTP egress, no API key reads.
**Why:** "No external paid API calls" is a hard constraint of Phase 24.
**Mitigation:** Each worker is a thin subclass — swapping its
`_execute` for a network-aware implementation is a one-file change and
will not require touching the orchestrator, scoring, or gates.

## 3. Scoring is a fixed-weight linear combination

**Where:** `hermes_cli/scoring.py:WEIGHTS`.
**What:** Weights are set in source, not learned. There is no per-task
adaptation.
**Why:** Deterministic and auditable beats clever-but-opaque for a
release-hardening phase. Adapting weights based on outcomes is on the
roadmap.
**Mitigation:** Weights are documented and asserted to sum to 1.0.
`tests/test_scoring.py` pins the contract.

## 4. The GitHub publisher's "live" path is a seam, not a turnkey integration

**Where:** `hermes_cli/github_publisher.py:publish`.
**What:** Live mode invokes a caller-supplied `transport` callable. The
default build ships *no* transport, so even with
`HERMES_PUBLISH_LIVE=1` the worst case is a `NameError` at the call
site — never an accidental post.
**Why:** Embedding a GitHub HTTP client (or an MCP wrapper) is a
separate phase, primarily because the repository network policy and
token scope decisions belong to the operator, not the orchestrator.
**Mitigation:** Dry-run is the default and emits a complete JSON
descriptor under `.hermes/publish/` so an operator can hand-post or
script the transport.

## 5. Worktree cleanup is best-effort

**Where:** `hermes_cli/orchestrator.py:WorktreeManager.remove`.
**What:** If `git worktree remove --force` fails, we fall back to
`shutil.rmtree(ignore_errors=True)`. A truly hostile filesystem state
(e.g. read-only mounts) could leave directories behind.
**Why:** The cost of forcing a hard failure is worse than the cost of an
orphaned `.hermes/worktrees/<name>/` directory, which is easy to spot
and remove manually.
**Mitigation:** The orchestrator logs which worktrees it created and
exposes `WorktreeManager.cleanup_all` for explicit teardown in test
fixtures.

## 6. No per-task budget or timeout enforcement at the orchestrator level

**Where:** `hermes_cli/orchestrator.py:Orchestrator.run`.
**What:** The orchestrator imposes a `timeout_seconds` default of 60s
per worker via `Future.result(timeout=...)`, but a misbehaving worker
that ignores cooperative cancellation will still consume its thread for
the lifetime of the process.
**Why:** Workers in this build are pure-Python and complete in
milliseconds. Hard cancellation matters only once workers start calling
external tools.
**Mitigation:** Each worker runs in a sandboxed worktree so the blast
radius of a stuck worker is bounded.

## 7. Validation gates are intentionally narrow

**Where:** `hermes_cli/validation_gates.py:GATES`.
**What:** Five gates: structure, size, secrets (six credential
patterns), unicode, policy (four destructive-command patterns). They
catch the documented failure modes; they do not run linters,
type-checkers, or domain-specific schema validation.
**Why:** A small, deterministic gate set is auditable. Bolting on heavy
checks (mypy, ruff, integration tests) belongs in CI, not at the
orchestrator gate.
**Mitigation:** The gate registry is a tuple — adding a gate is one
function and one entry. New gates do not need to know about the rest.

## 8. The orchestrator is single-host

**Where:** `hermes_cli/orchestrator.py:ThreadPoolExecutor` fan-out.
**What:** All workers run inside the same Python process. There is no
support for distributing workers across machines.
**Why:** Out of scope for Phase 24.
**Mitigation:** Multi-host orchestration is roadmap item #2 in
`next-roadmap.md`.

## 9. Test coverage is targeted at orchestration, not at integration

**Where:** `tests/test_orchestrator.py`, `tests/test_worker.py`,
`tests/test_scoring.py`, `tests/test_merge_engine.py`,
`tests/test_validation_gates.py`, `tests/test_github_publisher.py`.
**What:** 60 tests exercise the substrate end-to-end but do not run the
bash entry point under `pytest`. The bash script is validated by
`bash -n` only.
**Why:** Running the bash script under `pytest` would re-enter the
Python interpreter and complicate sandboxing.
**Mitigation:** The release checklist requires a manual smoke run of
the bash entry against a throwaway repo for every release.

## 10. No telemetry, no audit log

**Where:** *missing by design*.
**What:** The orchestrator records per-run JSON under
`.hermes/runs/run-*.json` and per-publish JSON under `.hermes/publish/`,
but there is no log aggregator, no metrics export, no remote audit
sink.
**Why:** Telemetry is a privacy and policy decision, not a default.
**Mitigation:** Per-run JSON is sufficient for hand audit. Telemetry is
roadmap item #5.
