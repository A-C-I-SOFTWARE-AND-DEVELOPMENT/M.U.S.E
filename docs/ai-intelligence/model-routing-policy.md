# Model routing policy

How the Hermes model router picks the model / tool / worker mix for a job.
The policy is intentionally short and rule-based; the model-router skill
(`skills/model-router/SKILL.md`) is the operational playbook on top of it.

The router never silently does anything externally visible. It writes a
**worker-selection-report** (from
`templates/orchestration/worker-selection-report.md`) and the user
approves it before any handoff or push actually happens.

## Inputs

The router has access to:

1. **`docs/ai-intelligence/model-registry.yaml`** — what surfaces exist
   and what they are good at.
2. **`docs/ai-intelligence/tool-capability-matrix.md`** — what each
   surface can actually *do* (read files, run commands, browse, push
   to GitHub, ask the user, …).
3. **Live detection** — for each registry entry, run its `detection`
   block now: is the command on PATH, is the env var set, is the auth
   file present, is the Android app installed, …
4. **The task itself** — the user request, plus whatever context Hermes
   already has (open PR, current branch, recent skills loaded, memory).
5. **The user's stated preferences** — explicit hints like "use Claude
   for this", "no API calls", "offline only", "cheap mode".

## Outputs

For each job the router produces a single
worker-selection-report with:

- the **primary worker** (one registry id)
- 0–N **supporting workers** (registry ids, in execution order)
- the **fallback chain** if the primary is unavailable or fails
- the **handoffs that need user approval** before they run
- a 1–3 sentence rationale tying the choice back to the task

## Classification

Before picking a worker, classify the job along three axes.

### Axis 1: task kind

| Kind | Examples | Default primary |
|---|---|---|
| `evidence` | "what does this code do", "find all callers of X", "summarize the diff" | `hermes-local` |
| `validation` | "run the tests", "lint", "type-check", "reproduce the failure" | `hermes-local` |
| `implementation` | "add this feature", "fix this bug", "write tests for Y" | `codex` |
| `refactor-large` | "rename across the package", "split this module" | `aider` for known files, `claude-code` for unknown |
| `architecture` | "design X", "review the approach", "what's the risk" | `claude-code` |
| `review` | "review this PR", "security review the diff" | `claude-code` |
| `infra-long` | "upgrade deps", "rebuild CI", "set up the new env" | `goose` |
| `drafting` | "write the RFC", "draft the release note", "summarize for non-engineers" | `chatgpt-handoff` |
| `research-web` | "what's in the current docs for X", "fetch this page" | `browser-research` |
| `private-llm` | "classify these without leaving the box", "embed these locally" | `local-model` |
| `publish` | "open the PR", "post the review", "comment on the issue" | `github-publisher` |
| `phone-side` | "run this on my phone", "git pull on the device" | `android-termux-runtime` |

### Axis 2: risk

| Bucket | Definition | Effect on routing |
|---|---|---|
| `low` | Local, reversible, no external surface. (Reading files, running tests in a worktree.) | Run without approval. |
| `medium` | Touches the working tree, the local environment, or a sandbox. | Run; surface a diff at the end. |
| `high` | Externally visible or hard to reverse. (Push, PR, comment, merge, delete, force-push, sending messages, browsing on user's behalf.) | **Always** route through `human-approval` first. |

When in doubt about the bucket, treat as `high`. The "Executing actions
with care" rule in the system instructions is the source of truth and
this policy must not undercut it.

### Axis 3: tradeoff weight

The user (or context) implies a weighting across:

- **quality** — how much the result needs to be right the first time
- **speed** — how time-sensitive the job is
- **cost** — how much API spend is acceptable
- **privacy** — whether the data is allowed to leave the device

Each registry entry has `tradeoffs:` with `low / medium / high` per
axis. Pick the entry whose tradeoff profile best matches the implied
weights, breaking ties with the "default primary" from Axis 1.

## Selection algorithm

```
1. Classify(task) → (kind, risk, weights)
2. candidates = registry.filter(entry =>
       entry covers `kind` per capability matrix
       AND entry.detection() succeeds
       AND entry.tradeoffs satisfies weights
   )
3. If no candidates:
       primary = "hermes-local" with a "best effort" rationale
       fallback = []
   Else:
       Sort candidates by:
         (a) explicit user preference
         (b) Axis-1 default primary match
         (c) lower risk first
         (d) better tradeoff fit
       primary  = candidates[0]
       fallback = candidates[1:]  (cap at 3)
4. supporting = pick the smallest set that closes the capability gap
       (e.g. primary=codex needs `hermes-local` for validation,
        primary=claude-code for review needs `github-publisher`
        to actually post the result).
5. approvals = []
   if risk == "high": approvals.append("human-approval before publish")
   for s in [primary, *supporting]:
       if registry[s].requires_approval: approvals.append(s)
6. Render worker-selection-report.md and return it.
```

The router does **not** execute the plan in the same step it produces
the report. Producing the plan is the deliverable. Execution happens in
a subsequent turn, after the user has read the report.

## Fallback policy

- Each registry entry lists `fallback: [...]` in priority order.
- A fallback fires when the primary entry **fails detection** at the
  moment of routing, **or** when it errors out during execution and the
  job is idempotent enough to retry.
- Fallbacks are not silent. The router updates the worker-selection-
  report (or, mid-execution, posts a short note) explaining what
  changed and why.
- `hermes-local` is the universal last-resort fallback. If nothing else
  is available, the router falls back to `hermes-local` running in
  "best effort" mode, and explicitly flags reduced quality.

## Non-goals (do not let the router do these)

- **No API proxying.** Hermes does not call OpenAI / Anthropic / etc.
  from the device on the user's behalf. CLI surfaces use the vendor's
  own auth; handoff surfaces require a user tap. See
  `docs/hermes-local-orchestrator.md` for the rationale.
- **No silent escalation.** The router cannot upgrade a `medium`-risk
  plan into a `high`-risk one without re-emitting the report.
- **No invented surfaces.** The router only picks from the registry.
  Adding a surface is a registry edit + capability matrix edit; it is
  not the router's job.
- **No detection-by-trying.** The router uses the `detection` block,
  not "run it and see". A failed run is logged as a *fallback event*,
  not as a detection signal.

## When the policy and the registry disagree

Registry wins. The policy describes the algorithm; the registry
describes the world. If the registry says a surface is unavailable on
this machine, the policy doesn't get to override that.

When `tool-capability-matrix.md` and the registry disagree on whether a
surface can do a thing, treat the capability matrix as the binding
contract — it is what the router actually consults when matching `kind`
to candidates.
