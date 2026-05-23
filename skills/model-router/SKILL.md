---
name: model-router
description: "Pick the best model / CLI tool / runtime / worker mix for a job from the Hermes model registry, with quality-cost-speed-privacy tradeoffs and an explicit fallback plan. Emits a worker-selection-report for the user to approve before any handoff or push runs."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows, android]
metadata:
  hermes:
    tags: [routing, orchestration, model-selection, tool-selection, registry, planning]
    related_skills: [hermes-agent, claude-code, codex, kanban-orchestrator]
---

# Model router

Use this skill any time you are about to delegate work to a model, CLI
tool, runtime, or human handoff and there is more than one reasonable
choice. The router reads the registry, classifies the job, matches
capabilities, weighs tradeoffs, attaches a fallback chain, and emits a
**worker-selection-report** for the user. It does **not** execute the
plan in the same step — execution happens after the user approves the
report.

## When to use this skill

- A user request that could be handled by more than one model / CLI
  (e.g. "implement this", "review this", "draft an RFC").
- Any job where Hermes is about to take an **externally visible** action
  — push, PR, comment, send-message, browse on the user's behalf — and
  needs to be sure it picked the right surface (and routed through
  `human-approval`).
- Any time the user asks "which tool should I use for X" or "what's the
  cheapest / fastest / most private way to do this".
- Whenever a previous worker errored out and Hermes needs to decide
  whether to retry, fall back, or escalate.

Do **not** use this skill for:

- Trivially local, reversible work (read a file, run a test) — that's
  always `hermes-local`.
- Re-routing on every turn of a long session — route once, then quote
  the existing report.

## Inputs the router reads (every time)

1. `docs/ai-intelligence/model-registry.yaml` — what surfaces exist
   and what they're good at.
2. `docs/ai-intelligence/tool-capability-matrix.md` — what each surface
   can actually do.
3. `docs/ai-intelligence/model-routing-policy.md` — the selection
   algorithm and the non-negotiables (no API proxying, no silent
   escalation, no invented surfaces, no detection-by-trying).
4. **Live detection** — for each registry entry, evaluate its
   `detection` block right now. Don't trust a cached answer from
   earlier in the session if the environment may have changed.
5. **The user's stated preferences** — explicit hints in the prompt
   ("use Claude", "offline only", "cheap mode", "no PR yet").

## Output

Always: a rendered `templates/orchestration/worker-selection-report.md`,
with every `{{ placeholder }}` replaced. The report is the deliverable.

Never: silently executing the plan in the same response that produced
the report. If you find yourself about to `git push` or call a handoff
in the same turn the report was generated, stop — that's a separate
turn after the user reads it.

## Step-by-step

### Step 1 — Classify the task

Use the three axes from the policy doc:

- **Task kind:** `evidence`, `validation`, `implementation`,
  `refactor-large`, `architecture`, `review`, `infra-long`, `drafting`,
  `research-web`, `private-llm`, `publish`, `phone-side`.
- **Risk:** `low`, `medium`, `high`. When in doubt, treat as `high`.
- **Tradeoff weights:** quality, speed, cost, privacy (each `low | medium | high`).

Write each value with one sentence of justification. The user reads
these — vague labels here mean the rest of the report is unverifiable.

### Step 2 — Run detection

For every registry entry that could plausibly be a candidate:

| Detection field | How to check |
|---|---|
| `internal: true` | Always available. |
| `command: <name>` | `command -v <name>` returns 0. |
| `env: [VAR, …]` | All listed env vars set and non-empty. |
| `file: <path>` | File exists and is readable. |
| `app: <pkg>` | Android package installed (only meaningful on the device). |
| `prompt: true` | Always available, but always requires a user tap. |

Record the result in section 2 of the report — one row per considered
entry, with the actual evidence (which command, which env var, which
file). This makes the choice auditable.

### Step 3 — Filter by capability

For the task `kind`, look up the **required capabilities** in
`tool-capability-matrix.md` (the table at the bottom of that file).
Keep registry entries that have `Y` (or `~` with a paired helper) for
every required capability.

If a capability is missing for the strongest candidate, attach a
supporting worker that provides it — usually `hermes-local` for repo
work or `github-publisher` for publishing.

### Step 4 — Apply the selection algorithm

From `model-routing-policy.md`:

1. Drop entries that failed detection.
2. Drop entries whose tradeoffs are worse than what the weights demand
   on any axis the user weighted `high`.
3. Sort the rest by: explicit user preference → Axis-1 default →
   lower risk → better tradeoff fit.
4. `primary = sorted[0]`, `fallback = sorted[1:4]`.
5. If the candidate list is empty, `primary = hermes-local` in
   "best effort" mode, and explicitly flag the quality hit.

### Step 5 — Compute approvals

For the primary and every supporting worker:

- If the registry entry has `requires_approval: true`, add an approval
  checkbox.
- If the task risk is `high`, add an approval checkbox for the
  publish/handoff step regardless.
- Use the exact text the user needs to say `yes` to ("Push branch X
  and open a draft PR" — not "approve the plan").

### Step 6 — Render the report

Open `templates/orchestration/worker-selection-report.md`, fill every
`{{ placeholder }}`, and emit it. The template's eight sections are
non-optional; if a section is empty, write `_none_` so the user can
tell you considered it.

### Step 7 — Stop

Do not execute. Wait for the user to read the report and approve.
After approval, the next turn quotes section 3 (worker mix) and
section 4 (approvals) and runs them — at that point you are no longer
routing, you are executing.

## Quick-pick cheat sheet

These are the defaults the router falls into when the task is
unambiguous. If your classification matches one of these, the rest of
the algorithm should not change the answer.

| Request shape | Primary | Supporting | Notes |
|---|---|---|---|
| "what does this code do" / "find all callers of X" | `hermes-local` | _none_ | Pure evidence. |
| "run the tests" / "reproduce the failure" | `hermes-local` | _none_ | Pure validation. |
| "add this feature" / "fix this bug" | `codex` | `hermes-local` for validation, `github-publisher` for PR | Worktree + `--full-auto`. |
| "rename across 12 files I know" | `aider` | `hermes-local` | Faster than full agents for known files. |
| "design X" / "what's the risk" | `claude-code` | `hermes-local` | Use `--effort high` or `ultrathink`. |
| "review this PR" | `claude-code` | `github-publisher` for posting comments | `--from-pr` flag. |
| "upgrade these deps" / "set up CI" | `goose` | `hermes-local`, `github-publisher` | Long-running, sandbox-friendly. |
| "draft the RFC" / "summarize for non-engineers" | `chatgpt-handoff` | _none_ | User edits live. Requires tap. |
| "what do the current docs say about X" | `browser-research` | `hermes-local` for grounding | Requires tap. |
| "classify these without leaving the box" | `local-model` | `hermes-local` | Privacy-gated jobs only. |
| "open the PR" / "post the review" | `github-publisher` | `human-approval` | Always confirm first. |
| "run this on my phone" | `android-termux-runtime` | `human-approval` | Every Android action is a tap. |

## Anti-patterns

- **Picking by name recognition.** "Use Claude" is a preference, not a
  classification. Still run the algorithm — the user may have weighted
  cost / speed in a way that makes a different surface the right pick.
- **Skipping detection.** Detection takes one shell call per candidate.
  Skipping it leads to "the router said codex, but codex isn't installed"
  in the next turn, which wastes the user's time.
- **Routing every turn.** Once a job has a worker-selection-report and
  the user has approved it, subsequent turns *execute* — they don't
  re-route. Re-route only when the situation materially changes
  (worker errored, user changed requirements, fallback triggered).
- **Silent fallback.** Always emit a one-line note when a fallback
  fires. The user needs to know "we tried codex, it failed at detection,
  we're on claude-code now".
- **Inventing surfaces.** If the right surface for a job isn't in the
  registry, the answer is to propose adding it (a registry edit + a
  capability-matrix edit), not to fake it with `hermes-local`.
- **Calling APIs the user didn't sign up for.** Hermes does not proxy
  OpenAI / Anthropic / etc. CLI surfaces use the vendor's own auth;
  handoff surfaces require a user tap. See
  `docs/hermes-local-orchestrator.md` for the rationale.

## Worked example

User: *"Can you bump our FastAPI version, fix anything that breaks, and
open a PR?"*

1. **Classify.**
   - Kinds: `infra-long` (dep upgrade) + `implementation` (fix breaks)
     + `validation` (tests) + `publish` (PR).
   - Risk: `high` (push, PR creation).
   - Weights: quality `high`, speed `medium`, cost `low`, privacy `medium`.
2. **Detect.**
   - `hermes-local`: ✅ always.
   - `goose`: ✅ command on PATH.
   - `codex`: ✅ command on PATH, `~/.codex/auth.json` present.
   - `claude-code`: ✅ command on PATH.
   - `github-publisher`: ✅ `GITHUB_TOKEN` set, `git` installed.
   - `aider`: ❌ no `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` exported.
3. **Filter & sort.**
   - `infra-long` default → `goose`. Available. Keep.
   - `implementation` default → `codex`. Available. Keep as support.
   - `publish` default → `github-publisher`. Available. Required for PR.
   - `validation` → `hermes-local`. Required.
4. **Mix.**
   - Primary: `goose` (drive the upgrade in a sandbox).
   - Supporting: `codex` (fix breaks codex is faster at), `hermes-local`
     (run the test suite, prepare the diff), `github-publisher`
     (open the PR).
   - Fallback: `codex → claude-code → hermes-local`.
5. **Approvals.**
   - [ ] Run `goose run upgrade-fastapi` in a sandbox.
   - [ ] Run the test suite locally.
   - [ ] Push branch and open a draft PR.
6. **Render the report**, hand it to the user, **stop**.

## Files this skill owns

- `docs/ai-intelligence/model-registry.yaml`
- `docs/ai-intelligence/model-routing-policy.md`
- `docs/ai-intelligence/tool-capability-matrix.md`
- `templates/orchestration/worker-selection-report.md`

Changes to any of those four files are a routing-policy change and
should be reviewed as such (worker mixes for in-flight jobs may move).
