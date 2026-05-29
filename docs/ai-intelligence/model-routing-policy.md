# Model Routing Policy

This document defines **how** Hermes picks a worker for a delegable
task. The companion files are:

- `model-registry.yaml` — the catalog of workers Hermes knows about.
- `tool-capability-matrix.md` — what each worker is allowed to do on
  the host.
- `skills/model-router/SKILL.md` — the runtime entry point that loads
  this policy and applies it per task.
- `oss-model-catalog.yaml` / `oss-model-catalog.md` — the **OSS model
  brain**: the cross-referenced catalog of open-weight models (which
  *open model* is best per task) that JARVIS Prime can route to via the
  installed providers. The worker layer here answers "which agent";
  the OSS brain answers "which open model that agent should run."

The policy is intentionally deterministic. Two Hermes sessions on the
same machine with the same registry and the same task should produce
the same routing plan.

---

## 1. Inputs

Every routing call gets:

- `task` — free-text description of what the user wants.
- `task_type` — classification from the list below (the router picks
  one before scoring).
- `evidence` — files, stack traces, PR diffs, prior validation results.
- `workspace` — cwd, git status, presence of `AGENTS.md` / `CLAUDE.md`.
- `available_workers` — set produced by the detection step.
- `user_preferences` — `model_router.*` keys from `config.yaml` plus
  any in-session overrides (`/route …`).

The router rejects a task that has no `task_type` rather than guessing.
Hermes downgrades unclassified work to `research` only after asking the
user once.

---

## 2. Task classification

| Task type | One-line definition |
|-----------|---------------------|
| `implementation` | Add new functionality. |
| `bug_fix` | Restore broken behavior. |
| `test_repair` | Make a red test green without changing intent. |
| `refactor_small` | One or two files, single responsibility. |
| `refactor_large` | Cross-module / cross-package restructure. |
| `architecture` | Design a system or contract before code exists. |
| `code_review` | Critique a diff. |
| `long_context_review` | Read a large body of code/text and reason about it. |
| `plumbing` | Shell, env, install, scripts, CI glue. |
| `research` | Read external sources and summarize. |
| `redaction_safe_draft` | Output must not leave the device. |
| `github_publish` | Branch, push, PR, comment, merge. |
| `manual_handoff` | The user wants to drive the worker by hand. |

If a request mixes types, split it into sub-tasks before routing.

---

## 3. Detection

The detection step is run once per session and cached. Reset by
`/route detect` or `hermes doctor`.

For each non-internal entry in `model-registry.yaml`:

1. Run `detection.command` via `which` (and/or `detection.command_help`
   for shims that mask `which`).
2. Check `detection.any_of` — at least one of the listed
   `env` / `file` / `port` predicates must pass.
3. Check structural requirements (`requires_git_repo`, etc.).
4. If all pass, mark the worker `available` and record the evidence.
5. Otherwise, mark `unavailable` with a one-line reason.

Internal workers (`hermes-local`, `github-publisher`) are always
`available`. `github-publisher` additionally records whether **writes**
are gated off by config — the router will still select it for read-only
publication (e.g., dry-run PR drafting) when writes are disabled.

---

## 4. Scoring rubric

For each available worker, compute:

```
score(worker, task) =
      0.35 * strength_match
    + 0.25 * tool_capability_match
    + 0.15 * quality_tier
    + 0.10 * speed_tier
    + 0.10 * cost_tier
    + 0.05 * validation_locality
```

### 4.1 `strength_match` (0..1)

Count overlap between `task_type → expected_strengths` (table below)
and the worker's `strengths` / `best_for`, divided by the size of the
expected set. A worker that lists every expected strength scores 1.0.

| Task type | Expected strengths |
|-----------|--------------------|
| `implementation` | implementation, fast code changes, tests |
| `bug_fix` | bug fixes, patch-oriented edits, repo evidence |
| `test_repair` | tests, test repair, surgical edits |
| `refactor_small` | surgical multi-file patches, careful diffs |
| `refactor_large` | multi-file reasoning, refactor planning, long-context review |
| `architecture` | architecture, refactor planning, multi-file reasoning |
| `code_review` | risk review, careful diffs, long-context review |
| `long_context_review` | long-context review, multi-file reasoning |
| `plumbing` | local shell + file agent, plumbing tasks on the host |
| `research` | offline reasoning, user-driven reasoning |
| `redaction_safe_draft` | privacy-preserving, offline reasoning, redaction-safe drafting |
| `github_publish` | branch / push / PR / comment, GitHub publishing |
| `manual_handoff` | user-driven reasoning, leverages an existing ChatGPT subscription |

### 4.2 `tool_capability_match` (0..1)

Read `tool-capability-matrix.md`. For the task's required capabilities
(file edit, terminal, network, GitHub write, long-context, browser,
etc.), what fraction does this worker cover? A worker missing any
*hard* capability scores 0 — capability gaps are disqualifying, not
discount-able.

### 4.3 Tier mappings

| Tier | `quality` | `speed` | `cost` (cheaper is higher) | `validation_locality` |
|------|-----------|---------|----------------------------|------------------------|
| 1.0  | critical | instant | free | runs validation in Hermes itself |
| 0.75 | high | fast | low | reads diff, defers tests to Hermes |
| 0.50 | standard | medium | medium | reads diff only |
| 0.25 | draft | slow | high | no intermediate checks |

### 4.4 Tie-breaking

If two workers tie within ±0.02:

1. Prefer the one earlier in `model_router.preferred_workers`.
2. Then prefer the worker whose `surface` is `cli` over `app` over
   `web` over `user-driven` (closer to scriptable Hermes control).
3. Then alphabetical `id`.

This makes the choice reproducible across sessions.

---

## 5. Fallback ladder

Every routing plan returns `primary` + an ordered `fallbacks` list.
Build the ladder by:

1. Take the top-scored available worker as `primary`.
2. Take that worker's `fallbacks:` from the registry, filter to
   workers that are currently `available`.
3. Append any other available workers, ordered by score, excluding
   ones already in the ladder.
4. Append `hermes-local` if it is not already there — it is the
   **terminal fallback** so no task ever dead-ends.

The router records *why* each rejected worker was rejected (detection
failure, score gap, capability gap, user opt-out).

---

## 6. Validation loop

After the primary worker reports completion, `hermes-local` runs
validation. The exact suite depends on the task type:

| Task type | Validation |
|-----------|------------|
| `implementation`, `bug_fix`, `test_repair`, `refactor_*` | `git diff` review, full test command, lints, type checks, smoke run of the changed code path. |
| `architecture` | Repo evidence read-back: does the design actually fit the file layout it references? |
| `code_review`, `long_context_review` | Sanity check that cited files/symbols actually exist. |
| `plumbing` | Re-run the script / command and capture exit status + stderr. |
| `research`, `redaction_safe_draft` | Spot-check at least one citation; confirm no secrets in the output. |
| `github_publish` | Diff parity check (what was pushed == what was validated); allowlist + write-gate confirmed. |
| `manual_handoff` | The user pastes the result back; Hermes runs the relevant validators on the pasted artifact. |

If validation fails:

1. Capture the failure as evidence.
2. Move to the next entry in `fallbacks`.
3. Re-emit the routing plan with the new `primary` and the prior
   worker's failure attached.
4. Stop when validation passes or the ladder is exhausted.

When the ladder is exhausted, Hermes writes a clear TODO into the
session (and the task card, if running under the kanban dispatcher)
and notifies the user via their preferred delivery channel.

---

## 7. User overrides

In-session slash commands (`/route ...`):

- `/route <worker>` — pin `<worker>` as primary for the next delegation.
- `/route prefer-local` — toggle `model_router.prefer_local`.
- `/route ladder` — print the current routing plan.
- `/route detect` — re-run detection and print results.
- `/route reset` — clear pinned overrides.

`config.yaml` knobs (under `model_router`):

```yaml
model_router:
  preferred_workers: [claude-code, codex, aider]
  prefer_local: false
  allow_manual_handoff: false
  cost_ceiling: medium        # low | medium | high | unlimited
  quality_floor: standard     # draft | standard | high | critical
  max_fallbacks: 3
```

`cost_ceiling` and `quality_floor` act as hard filters before scoring:
workers above the ceiling or below the floor are removed from the
candidate set entirely.

---

## 8. Hard rules

These rules override scoring. If they conflict, the router obeys the
rule and explains the override in the plan's `rationale`.

1. **Never bypass GitHub gates.** If a task requires
   `github-publisher` to write, but `github.allow_writes: false` or
   the repo isn't on the allowlist, the router demotes the publish
   step to a dry-run (diff preview + draft PR description only) and
   asks the user.
2. **Never pick `chatgpt-handoff` automatically.** It only appears in
   the candidate set when `task_type == manual_handoff` or the user
   explicitly invokes `/route chatgpt-handoff`.
3. **Never skip local validation.** `hermes-local` always runs the
   validation step. The router cannot route around it.
4. **Never run a worker whose detection failed.** Even with a manual
   `/route <worker>`, the router refuses and surfaces the detection
   failure so the user can fix it.
5. **Prefer local under `HERMES_OFFLINE=1`.** Cloud workers are
   removed from the candidate set entirely. If nothing local is
   available, the router stops and tells the user.
6. **Quality floor wins.** If no worker meets `quality_floor`, the
   router does not lower the bar silently — it asks.

---

## 9. Worked examples

### 9.1 Add a feature in a small Python repo

Inputs:
- `task_type: implementation`
- Detection: `codex`, `claude-code`, `aider`, `hermes-local`,
  `github-publisher` available; `goose`, `local-model` not.
- `cost_ceiling: medium` (default).

Scoring favors `codex` (high strength match, fast, medium cost, in
a git repo). `claude-code` scores close but loses on cost. Ladder:

```
primary: codex
fallbacks: [claude-code, aider, hermes-local]
validator: hermes-local
publisher: github-publisher
```

### 9.2 Cross-package refactor in a 200-file repo

Inputs:
- `task_type: refactor_large`
- All workers available.

Scoring favors `claude-code` (long-context, multi-file reasoning,
critical quality). `codex` is fallback. `aider` follows for surgical
follow-up edits if `claude-code` proposes a plan but doesn't finish.

```
primary: claude-code
fallbacks: [codex, aider, hermes-local]
validator: hermes-local
publisher: github-publisher
```

### 9.3 Offline drafting of a private note

Inputs:
- `task_type: redaction_safe_draft`
- `HERMES_OFFLINE=1`.

Cloud workers are removed. `local-model` wins (detected via Ollama on
:11434). `aider` is unavailable for prose. `hermes-local` is the
fallback.

```
primary: local-model
fallbacks: [hermes-local]
validator: hermes-local
publisher: (omitted)
```

### 9.4 User pastes a task into ChatGPT manually

Inputs:
- `task_type: manual_handoff`
- User ran `/route chatgpt-handoff`.

`chatgpt-handoff` is selected. Hermes drafts the structured prompt,
copies it to the clipboard / shows a deep link, and waits for the
user to paste the result back. Validation runs on the pasted
artifact.

```
primary: chatgpt-handoff
fallbacks: [hermes-local]
validator: hermes-local
publisher: (only if user asks; defaults off)
```
