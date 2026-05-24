# Model Routing Policy

This document defines **how** Hermes picks a worker for a delegable
task. The companion files are:

- `model-registry.yaml` — the catalog of workers Hermes knows about.
- `tool-capability-matrix.md` — what each worker is allowed to do on
  the host.
- `skills/model-router/SKILL.md` — the runtime entry point that loads
  this policy and applies it per task.

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

The router uses a **canonical task category** as the routing key. The
fifteen categories below cover Hermes' end-to-end workflow surface;
``hermes_cli/model_router.py:TASK_CATEGORIES`` is the source of truth
and the router rejects categories outside this list rather than
guessing.

| Task category | One-line definition |
|-----------|---------------------|
| `mobile-android` | Android Gradle build / Termux runtime / APK packaging. |
| `voice-pipeline` | Speech-to-text, text-to-speech, voice gateway plumbing. |
| `backend-orchestration` | Hermes-side wiring: gateways, plugins, tool routing. |
| `research` | Read external sources and summarize. Current docs matter. |
| `planning` | Draft a plan, schedule, contract before code exists. |
| `implementation` | Add new functionality. |
| `refactor` | Cross-file or cross-module restructure. |
| `debug` | Restore broken behavior, repair a failing test. |
| `validation` | Run the test/lint/typecheck suite and report. |
| `security` | Security review, secret hygiene, threat-model write-up. |
| `deployment` | Push to Vercel / Supabase / production. Gated. |
| `github-pr` | Branch, push, PR, comment, merge. Gated. |
| `user-profile-learning` | Capture / refine Hermes' user-profile facts. |
| `remote-execution` | Run a worker on a remote host via a secure tunnel. |
| `secrets-management` | Read / rotate / store secrets. Gated. |

If a request mixes categories, split it into sub-tasks before routing.

### Legacy fine-grained types

For backwards compatibility with the original Phase 05 vocabulary the
router also accepts these descriptors inside a worker's ``best_for``
list (so older registry entries keep working): ``implementation``,
``bug_fix``, ``test_repair``, ``refactor_small``, ``refactor_large``,
``architecture``, ``code_review``, ``long_context_review``,
``plumbing``, ``research``, ``redaction_safe_draft``,
``github_publish``, ``manual_handoff``. These are not categories
themselves; they only inform scoring.

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
  preferred_workers: [claude-code-windows, codex, aider]
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

1. **Hermes Local is always included.** Every routing plan lists
   `hermes-local` as at least the validator. It is the only worker
   that runs final validation, owns persistent memory, and writes
   the decision ledger.
2. **Claude Code Windows is preferred for complex repo-wide coding —
   if the secure tunnel is healthy.** When `tunnel_healthy=False`
   the router demotes `claude-code-windows` and falls back to
   `claude-code-local` for the same kind of work. The tunnel health
   check is part of detection; it is *not* score-able.
3. **Codex is preferred for focused implementation and test repair.**
   It tops the preference list for the `implementation` and `debug`
   categories.
4. **Aider is preferred for git-native local patch loops.** It tops
   the preference list when the task is framed as surgical
   multi-file patches over an existing git tree.
5. **Goose is optional for recipe/extension workflows.** It is never
   the default. The router only routes to Goose when a Goose recipe
   or MCP extension is the natural way to express the task — or when
   no preferred worker is available.
6. **Browser research is required when current external docs
   matter.** The router adds `browser-research` as a sidecar
   (`role=researcher`) whenever the category is `research` or the
   caller flags `needs_external_docs=True`.
7. **Human approval is required for:** secrets management,
   destructive commands, publish, remote-tunnel setup, and
   continuous-listening mode. The router adds `human-approval` to
   the selected list and emits the relevant approval tag in
   `approval_requirements`.
8. **Supabase worker only runs after schema and/or deployment
   approval.** Until the `schema-approval` tag is in
   `approvals_granted`, the router places `supabase-worker` in
   `rejected` with the reason `requires schema/deployment approval`.
9. **Vercel worker only runs after deployment approval.** Until the
   `deployment` tag is in `approvals_granted`, the router places
   `vercel-worker` in `rejected` with the reason
   `requires deployment approval`.
10. **Never bypass GitHub gates.** If a task requires
    `github-publisher` to write, but `github.allow_writes: false` or
    the repo isn't on the allowlist, the router demotes the publish
    step to a dry-run (diff preview + draft PR description only) and
    asks the user.
11. **Never pick `chatgpt-handoff` automatically.** It only appears
    in the candidate set when the user explicitly invokes
    `/route chatgpt-handoff` or sets the worker in
    `model_router.preferred_workers`.
12. **Never skip local validation.** `hermes-local` always runs the
    validation step. The router cannot route around it.
13. **Never run a worker whose detection failed.** Even with a manual
    `/route <worker>`, the router refuses and surfaces the detection
    failure so the user can fix it.
14. **Prefer local under `HERMES_OFFLINE=1`.** Cloud workers are
    removed from the candidate set entirely. If nothing local is
    available, the router stops and tells the user.
15. **Quality floor wins.** If no worker meets `quality_floor`, the
    router does not lower the bar silently — it asks.

### Approval tag vocabulary

The `approval_requirements` list is a multiset drawn from this fixed
vocabulary so the orchestrator and the gateway can match on it
without prose parsing:

| Tag | Triggered by |
|-----|--------------|
| `publish` | `github-pr` category, `github-publisher` in selected. |
| `deployment` | `deployment` category, `vercel-worker` in selected. |
| `schema-approval` | `supabase-worker` in selected. |
| `remote-tunnel-setup` | `remote-execution` category, `claude-code-windows` in selected. |
| `secrets` | `secrets-management` category. |
| `security-review` | `security` category. |
| `continuous-listening` | Caller set `continuous_listening=True`. |

### Required outputs

Every routing decision returns the following structure (see
``hermes_cli/model_router.RoutingDecision``):

- `selected` — the workers Hermes will run, with role + score + rationale.
- `rejected` — every other registered worker plus the reason it was
  passed over (detection / capability / approval / category miss).
- `explanation` — one-paragraph human-readable rationale.
- `decision_ledger_entry` (``ledger_entry`` on the dataclass) — JSON-
  serialisable dict appended one-per-line to
  `$HERMES_HOME/orchestrator/decision_ledger.jsonl`.
- `fallback_plan` — ordered ladder terminating at `hermes-local`.
- `approval_requirements` — list of tags from the vocabulary above.
- `validation_plan` — concrete steps `hermes-local` runs after the
  primary worker returns.

---

## 9. Worked examples

### 9.1 Add a feature in a small Python repo

Inputs:
- `task_category: implementation`
- Detection: `codex`, `claude-code-local`, `aider`, `hermes-local`,
  `github-publisher` available; `claude-code-windows`, `goose`,
  `local-model` not.
- `cost_ceiling: medium` (default).

Scoring favors `codex` (high strength match, fast, medium cost, in
a git repo). `claude-code-local` scores close but loses on cost.
Ladder:

```
primary: codex
fallbacks: [aider, claude-code-local, hermes-local]
validator: hermes-local
publisher: (omitted unless task ends in a PR)
```

### 9.2 Cross-package refactor across a 200-file repo, tunnel up

Inputs:
- `task_category: refactor`
- All workers available; `tunnel_healthy: true`.

Scoring favors `claude-code-windows` (long-context, multi-file
reasoning, critical quality, preference #1 for `refactor`). The
router emits `remote-tunnel-setup` in `approval_requirements` and
includes `human-approval` in the selected list.

```
primary: claude-code-windows
fallbacks: [claude-code-local, codex, aider, hermes-local]
validator: hermes-local
publisher: (omitted unless task ends in a PR)
approval_requirements: [remote-tunnel-setup]
```

If the same refactor runs with `tunnel_healthy: false`,
`claude-code-windows` is rejected with "secure tunnel to Windows
host is not healthy" and the router falls back to `claude-code-local`
as primary.

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
