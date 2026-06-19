# muse orchestration — next roadmap

Concrete, scoped enhancements to take the Phase 24 substrate from "10/10
substrate" to "10/10 product". Each item is sized to fit in a single
phase and has an exit criterion.

## 1. Real worker actuators — turn proposals into patches

Currently workers describe the change they would make. Wire them to the
local tools their names imply (Codex CLI, Claude Code CLI, OpenCode CLI,
etc.) so the worktree actually contains a diff after `execute()`. The
merge engine should then operate on diffs, not just Markdown bodies.

**Exit criterion:** A worker run produces a non-empty `git diff` inside
its worktree, and the merge engine concatenates or rebases those diffs
into a single mergeable branch.

## 2. Multi-host orchestration

Replace the in-process `ThreadPoolExecutor` with a queue-based dispatcher
(stdlib `multiprocessing.Queue` or a thin Redis/SQLite wrapper) so
workers can run on different machines. The worktree contract stays the
same — workers receive a path, write a result — but the path lives on a
shared filesystem or is shipped over SSH.

**Exit criterion:** Six workers fan out across at least two hosts and
the orchestrator collects all six proposals before scoring.

## 3. Web UI dashboard

Surface live orchestration state — which worker is running, which
worktree, which gate fired — in a small web UI under
`hermes_cli/web_server.py`. Read-only at first; later let an operator
trigger arbitration overrides and live-publish from the UI.

**Exit criterion:** `muse web` shows a per-run timeline with worker
status, score breakdown, and gate verdicts.

## 4. Adaptive scoring

Replace fixed weights in `hermes_cli/scoring.py:WEIGHTS` with an
online-updated table keyed on task metadata (e.g. `task.metadata.kind`
in {bugfix, feature, doc}). Update weights based on whether a published
proposal was merged, reverted, or amended.

**Exit criterion:** Weights persist across runs (e.g. in
`.hermes/scoring.json`) and the test suite exercises both update and
read paths.

## 5. Cost and time telemetry

Each worker should report `cost_estimate_cents`, `elapsed_seconds`, and
`tokens_used` (zero for local workers). Aggregate per-run totals into
`.hermes/runs/run-*.json` and emit a Prometheus textfile when
`HERMES_TELEMETRY_DIR` is set.

**Exit criterion:** A dashboard / cron-fed report can plot per-run cost
and elapsed-time trends over the last 30 days.

## 6. Multi-repo orchestration

Allow a single task to fan out across multiple repositories at once
(useful for cross-cutting changes like dependency bumps). The bash
entry would accept `--repo path1 --repo path2`, the orchestrator would
spawn six workers per repo, and the merge engine would emit one
`PublishDescriptor` per repo.

**Exit criterion:** A single `hermes-orchestrate.sh` invocation produces
N descriptors for N repos and the publisher round-trips each
independently.

## 7. Live GitHub transport plugin

Ship a stdlib-only transport that exchanges
`PublishDescriptor → POST /repos/:owner/:repo/pulls` using the GitHub
MCP server (or HTTP if MCP is unavailable) with explicit token scoping.
Default remains dry-run.

**Exit criterion:** With `HERMES_PUBLISH_LIVE=1` and a token in
`HERMES_GITHUB_TOKEN`, a successful run creates a draft PR and a smoke
test against a fixture repository passes in CI.

## 8. More validation gates

Add three more gates: a `tests` gate (re-runs `pytest -q` inside the
merged worktree), a `style` gate (runs `ruff check` if present), and a
`policy.skill` gate (rejects proposals that touch a skill without
updating its `SKILL.md` frontmatter `version`).

**Exit criterion:** GATES has eight entries; each new gate has a pass
and fail test; the bash entry's exit code reflects the new gates.

## 9. Replay and re-arbitration

A subcommand (`hermes-orchestrate replay <task_id>`) loads
`.hermes/runs/run-<task_id>.json`, re-runs the arbiter and merge engine,
and writes a fresh artefact. Useful when scoring weights change and an
operator wants to see whether the winner would have shifted.

**Exit criterion:** Replay produces a deterministic, byte-identical
result for unchanged weights and a documented diff when weights change.

## 10. Skill-aware routing

Pre-orchestration step: inspect the task prompt against the skills
index (`scripts/build_skills_index.py`) and pre-select which workers
get invoked. Tasks that match a single skill cleanly should not pay the
full six-worker cost.

**Exit criterion:** A task that matches `skills/research/arxiv`
unambiguously runs only the workers most likely to use it (e.g.
`claude`, `hermes`) and the orchestrator records the routing decision
under `task.metadata.routing`.

## MOBILE-JOBS-STREAMING-001 — Optional SSE/WebSocket job event stream

**Current state.** The Android Jobs cockpit drives live updates with REST
polling (lifecycle-aware back-off in `JobsViewModel` / `JobsPolling`) plus
foreground notifications (`JobNotifier`). The gateway exposes the
job control + detail surface over plain HTTP
(`gateway/cockpit/handlers.py`), **not** SSE. The contract's
`GET /v1/cockpit/jobs/stream` is documented as *specified-but-pending* —
no shipped code claims SSE exists.

**Future target.** Evaluate SSE vs WebSocket for lower-latency job events
and a per-job event tail, falling back to polling when unavailable.

**Required before this can be called canonical:**

- a backend stream endpoint (`/v1/cockpit/jobs/stream` and/or
  `/v1/cockpit/jobs/{id}/events`),
- an Android streaming client (kept off the buffered `HermesCockpitClient`
  transport, like the chat stream),
- reconnect/back-off + heartbeat-timeout logic,
- bearer-token auth on the upgrade,
- unit + integration tests on both sides,
- a migration note in this file and the API contract, and
- an automatic fallback to the existing polling path.

**Exit criterion:** the cockpit consumes job deltas over the stream when
the gateway offers it, transparently falls back to polling when it does
not, and no doc claims SSE is the only transport.
