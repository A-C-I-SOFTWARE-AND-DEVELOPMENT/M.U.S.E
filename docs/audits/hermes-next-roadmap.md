# Hermes — Next Roadmap

**Phase:** 27 (final 10/10 readiness gate)
**Posture:** the substrate is 10/10. Everything here moves the
*product* from "10/10 substrate" to "10/10 turnkey product".

This file supersedes
[`docs/orchestration/next-roadmap.md`](../orchestration/next-roadmap.md)
for product-level planning; that file is preserved for its
orchestration-substrate context. Items are sized to fit in a single
phase and each carries an exit criterion.

Sequencing rule: do not start item *n+1* until the
[`hermes-known-limitations.md`](hermes-known-limitations.md) bullet
it retires has actually been removed.

---

## 1. Live GitHub transport plugin (retires limitation §1)

Ship a stdlib-only transport that exchanges
`PublishDescriptor → POST /repos/:owner/:repo/pulls` using the
GitHub MCP server when present, falling back to direct HTTPS when
not. Default stays dry-run.

**Why first:** the rest of the substrate already produces the
descriptor; this is the only gap between "we know what to post" and
"we post it".

**Exit criterion:** with `HERMES_PUBLISH_LIVE=1` and a token in
`HERMES_GITHUB_TOKEN`, a successful run creates a draft PR on a
fixture repository and a smoke test asserts the PR exists and is in
draft state. The transport refuses to push to `main` or to any
protected branch without an explicit `--force-protected` flag.

---

## 2. Gateway end-to-end smoke in CI (retires limitation §2)

Stand up a per-platform smoke harness that exercises each
`gateway/platforms/*` adapter against a recorded fixture (no live
network) and, for the platforms whose vendors expose sandbox
environments (Telegram, Slack, Discord), an opt-in nightly job that
posts to a test channel and asserts the round-trip.

**Exit criterion:** every adapter under `gateway/platforms/` has a
`tests/gateway/test_<platform>_smoke.py` that passes in the default
CI run, and at least three platforms have a sandbox-mode nightly
job that posts and reads back its own message.

---

## 3. Worker actuators — close the patch loop (retires limitation §3)

Wire every worker adapter to its named tool so the worktree actually
contains a diff after `run()`. The merge engine should then operate
on diffs, not just Markdown bodies.

**Exit criterion:** a worker run produces a non-empty `git diff`
inside its worktree, the scoring tier rewards real-diff outputs over
descriptive outputs, and the merge engine concatenates or rebases
those diffs into a single mergeable branch.

---

## 4. Closed-loop self-improvement (retires limitation §9)

Promote the AI radar + retrospective + decision-ledger trio from
*open* loop to *closed*: outcomes feed scoring weights, prompt
templates, and worker selection automatically, with a single human
"apply" still required by default but with a per-operator
"auto-apply when confidence > X" mode.

**Exit criterion:** weights persist across runs (e.g.
`.hermes/scoring.json`), the radar can emit a one-line "weights
changed because …" entry to the decision ledger, and an operator
can review a 30-day delta of scoring weight drift in
`muse orchestrator retro`.

---

## 5. More validation gates (retires limitation §7)

Add three more gates: a `tests` gate (re-runs `pytest -q` inside
the merged worktree), a `style` gate (runs `ruff check` if
present), and a `policy.skill` gate (rejects proposals that touch a
skill without updating its `SKILL.md` frontmatter `version`).

**Exit criterion:** `GATES` has eight entries; each new gate has a
pass and fail test; the bash entry's exit code reflects the new
gates; existing gate tests are still green.

---

## 6. Multi-host orchestration (retires limitation §8)

Replace the in-process `ThreadPoolExecutor` with a queue-based
dispatcher (stdlib `multiprocessing.Queue` or a thin Redis/SQLite
wrapper) so workers can run on different machines. The worktree
contract stays the same — workers receive a path, write a result —
but the path lives on a shared filesystem or is shipped over SSH.

**Exit criterion:** six workers fan out across at least two hosts
and the orchestrator collects all six proposals before scoring.

---

## 7. Telemetry — opt-in metrics and audit (retires limitation §10)

Each worker reports `cost_estimate_cents`, `elapsed_seconds`, and
`tokens_used` (zero for local workers). Aggregate per-run totals
into `.hermes/runs/run-*.json` and emit a Prometheus textfile when
`HERMES_TELEMETRY_DIR` is set. Add an optional `audit_sink` callable
on the orchestrator that fires once per arbitration with the
decision and the rationale, suitable for piping into an enterprise
audit log.

**Exit criterion:** a dashboard fed from the textfile plots per-run
cost and elapsed-time trends over the last 30 days; the audit sink
has a test that asserts every arbitration produces exactly one
entry and zero exceptions in the orchestrator hot path.

---

## 8. Multi-repo orchestration

Allow a single task to fan out across multiple repositories at once
(useful for cross-cutting changes like dependency bumps). The bash
entry would accept `--repo path1 --repo path2`, the orchestrator
would spawn workers per repo, and the merge engine would emit one
`PublishDescriptor` per repo.

**Exit criterion:** a single `hermes-orchestrate.sh` invocation
produces N descriptors for N repos and the publisher round-trips
each independently.

---

## 9. Replay and re-arbitration

A subcommand (`hermes-orchestrate replay <task_id>`) loads
`.hermes/runs/run-<task_id>.json`, re-runs the arbiter and merge
engine, and writes a fresh artefact. Useful when scoring weights
change and an operator wants to see whether the winner would have
shifted.

**Exit criterion:** replay produces a byte-identical result for
unchanged weights and a documented diff when weights change.

---

## 10. Skill-aware routing

Pre-orchestration step: inspect the task prompt against the skills
index (`scripts/build_skills_index.py`) and pre-select which workers
get invoked. Tasks that match a single skill cleanly should not pay
the full worker fan-out cost.

**Exit criterion:** a task that matches `skills/research/arxiv`
unambiguously runs only the workers most likely to use it (e.g.
`claude_code`, `hermes_local`) and the orchestrator records the
routing decision under `task.metadata.routing`.

---

## 11. Android cockpit feature parity

The Android cockpit (`apps/android/`) currently surfaces
orchestration status, job listings, and clipboard handoff. Bring it
to feature parity with the desktop CLI for the slash commands most
useful on a phone: `/orchestrate`, `/orchestrator status`,
`/decision-ledger show`, `/profiles`, `/model-router explain`.

**Exit criterion:** every command in that list is invokable from
the Android cockpit and round-trips through the local API
(`hermes_cli/orchestrator_api.py`) without going through Termux
text input.

---

## 12. `hermes_cli/integrations/` package (retires limitation §12)

If — and only if — a refactor would make the integration surface
easier to discover for new contributors, fold the scattered
`hermes_cli/{gateway,webhook,slack_cli,vercel_auth,…}.py` modules
into `hermes_cli/integrations/<vendor>.py`. Keep stub re-exports at
the old paths for one release to avoid breaking external imports.

**Exit criterion:** every module that primarily wraps an external
vendor lives under `hermes_cli/integrations/`; the readiness
report's §2 note about the missing package is removed; no public
import path breaks.

---

## Out of scope, intentionally

These have come up in prompts and reviews but are explicitly **not**
on the roadmap until something changes upstream:

- **Bundled GitHub token** — Hermes will not ship a default token,
  ever. Live publishing always requires an operator-supplied
  credential.
- **Auto-merge of generated PRs** — the orchestrator will never
  merge its own work. A human reviewer is part of the contract.
- **Free-form natural-language gate config** — gates stay pinned to
  a hand-curated `GATES` tuple. Adding a gate is a code change with
  a test, not a config string.
