---
name: model-router
description: "Choose the best worker/model mix for each Hermes workflow. Considers task type, local tool availability, quality, cost, speed, validation needs, and fallback options."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [routing, orchestration, models, delegation, planning, hermes-local]
    related_skills:
      - hermes-orchestration-pipeline
      - codex-dispatch-governor
      - github-publisher
      - local-quality-gate
      - ai-improvement-radar
    intelligence_sources:
      - docs/ai-intelligence/model-registry.yaml
      - docs/ai-intelligence/model-routing-policy.md
      - docs/ai-intelligence/tool-capability-matrix.md
    orchestration_links:
      - docs/orchestration/worker-adapters.md
      - docs/orchestration/local-validation-gates.md
      - docs/orchestration/scoring-and-merge-engine.md
---

# Model Router

Hermes is the **planner of record** for every workflow. Even when another
worker (Codex, Claude Code, Aider, Goose, a local model, or a manual
ChatGPT/Claude/Gemini handoff) does the heavy lifting, Hermes is the one
that:

1. classifies the task,
2. inspects what workers are actually installed/reachable on the host,
3. picks a primary worker and at least one fallback,
4. emits a structured plan that the rest of the system can execute,
5. validates the result locally before declaring the job done.

This skill is the **decision procedure** Hermes runs every time it
needs to delegate. It is deterministic, evidence-first, and never
invents capabilities a worker doesn't have on this machine.

## Source documents

This skill is the runtime entry point. The reference data it consults
lives next to it:

| File | What it holds |
|------|---------------|
| `docs/ai-intelligence/model-registry.yaml` | Per-worker entry (id, provider, surface, strengths, best_for, detection, run_mode, cost, speed, quality, validation). |
| `docs/ai-intelligence/model-routing-policy.md` | The decision tree, scoring rubric, and fallback ladder. |
| `docs/ai-intelligence/tool-capability-matrix.md` | What each worker is allowed to touch (files, terminal, network, GitHub, long-context review, multi-file refactor, browser, etc.). |

When any of those files change, this skill picks up the new behavior on
the next session — no code changes required.

## Workers in scope

These are the worker IDs the router knows about. Each one has a full
entry in `model-registry.yaml`, including a `profile_hint` that the
orchestrator uses to resolve Kanban-card assignees (see
`docs/orchestration/worker-adapters.md`).

| Worker | Surface | Profile hint | Role in Hermes |
|--------|---------|--------------|----------------|
| `hermes-local` | internal | engineer | The planner, dispatcher, validator, and GitHub publisher. Always present. Runs on every job. |
| `codex` | OpenAI CLI / app / web | engineer | Default implementation worker — fast feature work, test repair, bug fixes. |
| `claude-code` | Anthropic CLI | reviewer | Long-context architecture, multi-file refactor planning, risk review. |
| `aider` | local CLI | engineer | Git-aware paired-edit worker. Surgical edits with explicit diffs. |
| `goose` | local CLI | engineer | Local agent with shell + file tools. Good for plumbing tasks on the host. |
| `chatgpt-handoff` | user-driven, web/app | researcher | Manual paste handoff to ChatGPT (no API). Used when the user wants ChatGPT in the loop without an API key. |
| `local-model` | local inference (Ollama / llama.cpp / vLLM) | researcher | Offline reasoning, redaction-safe drafting, free-tier fallback. |
| `github-publisher` | internal | publisher | The Hermes-owned worker that opens branches/PRs/comments. Never a primary "thinker" — it's the publication channel for everything else. |

`hermes-local` and `github-publisher` are always available because they
are internal to Hermes. The other six are **detected at runtime** (see
`detection:` in the registry). The router will never route to a worker
whose detection fails.

## The decision procedure

The router runs this procedure for every delegable task.

### Step 1 — Classify the task

Pick exactly one of these task types. If a task spans more than one,
break it up and run the router per sub-task.

| Task type | Examples |
|-----------|----------|
| `implementation` | Add a feature, write a CLI command, wire up a tool. |
| `bug_fix` | Fix a failing test, repair a regression, patch a stack trace. |
| `test_repair` | Make a red test green without changing intent. |
| `refactor_small` | Rename, extract function, tighten types within one or two files. |
| `refactor_large` | Cross-module restructure, architectural change, multi-file rename. |
| `architecture` | Greenfield design, system layout, API contract, migration plan. |
| `code_review` | Critique a diff, find risks, suggest changes. |
| `long_context_review` | Read a large repo / long file and reason about it as a whole. |
| `plumbing` | Shell-level glue, install deps, run scripts, set up env. |
| `research` | Read docs / papers / external pages and summarize. |
| `redaction_safe_draft` | Generate text that must never leave the device (private notes, secrets-adjacent prose). |
| `github_publish` | Open branch, push, open PR, comment, merge. |
| `manual_handoff` | The user wants to drive the worker themselves (paste the prompt into ChatGPT/Claude/Gemini). |

### Step 2 — Detect available workers

Run the `detection` block for every non-internal entry in the registry.
Common detectors:

- `command: <name>` — `which <name>` returns 0.
- `command_help: <name>` — `<name> --help` returns 0 (catches shims).
- `env: <VAR>` — env var is non-empty.
- `file: <path>` — file/dir exists (e.g. `~/.codex/auth.json`,
  `~/.claude/.credentials.json`).
- `port: <n>` — local server reachable (e.g. Ollama on 11434).
- `internal: true` — Hermes feature, always true.

Cache detection per process. Re-run on `/reload` or when the user runs
`hermes doctor`.

### Step 3 — Score candidates

For each available worker, compute a score against the classified task
using the rubric in `model-routing-policy.md`. The high-level weights
are:

```
score =
    0.35 * strength_match(task_type, worker.strengths)
  + 0.25 * tool_capability_match(task_needs, capability_matrix)
  + 0.15 * quality_tier(worker)
  + 0.10 * speed_tier(worker)
  + 0.10 * cost_tier(worker)              # cheaper = higher
  + 0.05 * validation_locality(worker)    # closer to hermes-local = higher
```

Ties are broken by (a) the user's `model_router.preferred_workers`
list in `config.yaml`, then (b) alphabetical worker id, so the choice
is reproducible.

### Step 4 — Pick primary + fallback ladder

The router always returns:

- `primary`: top-scored available worker.
- `fallbacks`: ordered list of the next best available workers, plus
  `hermes-local` as the *terminal* fallback so a workflow never dead-
  ends. (`hermes-local` can always at least draft a plan, leave a TODO,
  or hand off to the user.)
- `validator`: always `hermes-local` — Hermes runs the tests / lints /
  type checks / smoke tests on the result.
- `publisher`: `github-publisher` if the task ends in a branch, push,
  PR, or comment; otherwise omitted.

### Step 5 — Emit the routing plan

The router writes a structured plan into the session context (and, when
running under the `kanban` toolset, onto the task card):

```yaml
routing:
  task_id: <stable-id>
  task_type: implementation
  primary:
    worker: codex
    run_mode: official_cli
    rationale: "Codex CLI detected; task is feature implementation;
                workspace is a git repo; codex strengths match."
  fallbacks:
    - claude-code        # if codex is rate-limited or refuses
    - aider              # if claude-code unavailable
    - hermes-local       # always last
  validator: hermes-local
  publisher: github-publisher
  evidence:
    detected_workers: [codex, claude-code, aider, hermes-local, github-publisher]
    rejected:
      goose: "command not found"
      local-model: "no inference server on :11434"
      chatgpt-handoff: "user did not request manual handoff"
```

Every routing decision must include `rationale` and `evidence`. No
silent picks.

### Step 6 — Validate locally

After the primary worker returns, `hermes-local` runs:

- `git status` + diff inspection,
- the project's test command (`pytest`, `npm test`, etc.),
- type/lint checks if configured,
- a smoke run of the changed code path where feasible,
- any task-specific checks the user pinned.

If validation fails, the router re-engages: it picks the next entry in
`fallbacks`, attaches the failure evidence, and re-emits the plan. The
loop terminates when validation passes or the fallback ladder is
exhausted — at which point Hermes leaves a clear, actionable TODO and
notifies the user.

### Step 7 — Publish (optional)

If `publisher: github-publisher` is set and validation passed, Hermes
opens a branch, pushes, opens (or updates) a draft PR, and posts the
routing plan + validation summary as the PR description. Writes always
go through the `github_assistant` plugin's allowlist + `allow_writes`
gates (see `docs/github-integration.md`); the router does not bypass
them.

## Defaults the router honors

- **Repo evidence first.** Never plan from prose alone. If the task
  references files, read them. If it references a stack trace, locate
  the frames. If no evidence is reachable, downgrade the task to
  `research` and pick a worker tuned for that.
- **Terminal validation always.** A worker's "done" is never trusted
  until `hermes-local` validates. This is non-negotiable.
- **Local-first when offline-equivalent.** If the user toggled
  `model_router.prefer_local: true` (or set `HERMES_OFFLINE=1`), local
  workers (`local-model`, `aider`, `goose`, `hermes-local`) score
  higher and cloud workers are demoted to fallbacks.
- **No API spoofing.** `chatgpt-handoff` is never auto-invoked. It is
  selected only when the user explicitly asks for "ChatGPT in the
  loop" or sets `model_router.allow_manual_handoff: true` and the
  task type is `manual_handoff`.
- **GitHub writes are gated.** `github-publisher` only acts if
  `github.enabled: true` and (for write actions) `github.allow_writes:
  true` in `~/.hermes/config.yaml`, and the repo is on the
  `github.allowed_repositories` list (or the list is empty).
- **Caching the decision.** The routing plan is written once per task.
  Re-routing happens on validation failure or explicit user override
  (`/route <worker>`), not on every turn — this preserves prompt
  caching the same way the rest of Hermes does.

## How to invoke

The router is meant to be loaded as a skill on sessions that delegate
work:

```
hermes -s model-router chat -q "Add a /diagnose subcommand that
prints versions of every detected coding agent."
```

Or from a session:

```
/skill model-router
```

Once loaded, any time Hermes encounters a delegable task, it will
follow the decision procedure above before calling `delegate_task`,
spawning a child `hermes` process, or running another worker via
`terminal(...)`.

## Override knobs

Users can steer the router without editing YAML:

- `/route <worker>` — pin the primary worker for the next delegation.
- `/route prefer-local` — toggle `model_router.prefer_local`.
- `/route ladder` — show the current routing plan for the active task.
- `/route detect` — re-run worker detection and print the result.
- `config.yaml` → `model_router.*`:
  - `preferred_workers: [claude-code, codex]`
  - `prefer_local: false`
  - `allow_manual_handoff: false`
  - `cost_ceiling: medium`           # low | medium | high | unlimited
  - `quality_floor: standard`        # draft | standard | high | critical

## What the router will NOT do

- It will not route to a worker whose detection failed.
- It will not skip local validation, even on "trivial" changes.
- It will not push to `main` or any branch without an explicit user
  instruction; default publication is always a draft PR on a feature
  branch.
- It will not invent worker capabilities. If `tool-capability-matrix.md`
  says a worker can't do something, the router treats that as ground
  truth.
- It will not silently switch providers mid-task. A re-route is always
  announced in the session and recorded on the task card.

## Integration with the orchestration system

The router does not replace the orchestrator — it slots into it. When
Hermes is running an orchestrated job (`/orchestrate <goal>`), the
orchestrator decomposes the goal into Kanban cards, each tagged with an
`assignee` profile (`researcher`, `engineer`, `reviewer`, `publisher`).
The router is what turns that profile name into a concrete worker:

1. The orchestrator emits a card with `assignee: engineer`.
2. The dispatcher hands the card to the router with `task_type` inferred
   from the card's labels (or supplied explicitly).
3. The router applies the policy in `model-routing-policy.md`, but
   filters the candidate set by `profile_hint == card.assignee` first.
4. If no available worker matches the profile, the router does **not**
   silently rename the assignee — it surfaces the gap and the card sits
   in `ready` until the user adds a worker or re-tags the card. (See
   `docs/orchestration/troubleshooting.md#stuck-in-ready`.)
5. The validation step is the orchestration validation gate
   (`docs/orchestration/local-validation-gates.md`). The
   `validation_needs` field on each worker tells the gate which
   signals to require for that card.
6. The publish step routes through `github-publisher`, gated by the
   same allowlist + `allow_writes` rules the rest of Hermes uses.

When the orchestrator is running parallel workers on a card (see
`docs/orchestration/scoring-and-merge-engine.md`), the router scores
each candidate worker and the orchestrator fans the card out to the
top N. The scoring engine then picks the winning output by re-applying
this skill's scoring rubric to the *results*, not just the workers.

## Pointers

- Worker registry: `docs/ai-intelligence/model-registry.yaml`
- Decision tree + scoring: `docs/ai-intelligence/model-routing-policy.md`
- Capability matrix: `docs/ai-intelligence/tool-capability-matrix.md`
- GitHub publication rules: `docs/github-integration.md`
- Worker profiles in the orchestrator: `docs/orchestration/worker-adapters.md`
- Local validation gate: `docs/orchestration/local-validation-gates.md`
- Parallel-worker scoring: `docs/orchestration/scoring-and-merge-engine.md`
- Hermes role on Android (planner-only handoffs): `docs/hermes-local-orchestrator.md`
