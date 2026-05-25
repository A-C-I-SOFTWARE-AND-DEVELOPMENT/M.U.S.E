# Tool Capability Matrix

The model router uses this matrix as **ground truth** for what each
worker can actually do on the host. A capability listed as `no` here
is disqualifying: the router will not route a task to a worker that
needs a capability it doesn't have, regardless of how well its
strengths match.

The matrix complements the per-worker strength descriptions in
`model-registry.yaml`. Strengths describe *what a worker is good at*;
this matrix describes *what a worker can technically perform on the
machine*.

## Legend

| Symbol | Meaning |
|--------|---------|
| `yes` | Native, first-class support. |
| `gated` | Supported but behind explicit user / config gates. |
| `assist` | Drafts the action but Hermes (or the user) must execute it. |
| `no` | Not supported — the router treats this as disqualifying. |

## Capability columns

- **read_files** — Can read files in the workspace.
- **write_files** — Can write or patch files in the workspace.
- **run_terminal** — Can execute arbitrary shell commands.
- **run_tests** — Can invoke the project test runner.
- **multi_file_refactor** — Can coherently edit many files in one pass.
- **long_context_review** — Can hold a large amount of code in context
  and reason about it as a whole.
- **architecture** — Can produce design docs / contracts before code.
- **network_fetch** — Can fetch URLs / browse the web.
- **github_read** — Can read GitHub issues, PRs, repos.
- **github_write** — Can push branches, open PRs, comment, merge.
- **persistent_memory** — Survives across Hermes sessions.
- **offline_capable** — Works without internet.
- **redaction_safe** — Output never leaves the device.
- **validation_local** — Runs validation in-process (tests, lints).

---

## Matrix

| Worker | read_files | write_files | run_terminal | run_tests | multi_file_refactor | long_context_review | architecture | network_fetch | github_read | github_write | persistent_memory | offline_capable | redaction_safe | validation_local |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `hermes-local`     | yes    | yes    | yes    | yes    | assist | assist | assist | yes    | yes    | gated  | yes    | yes    | gated  | yes    |
| `codex`            | yes    | yes    | yes    | yes    | yes    | gated  | assist | yes    | yes    | gated  | no     | no     | no     | no     |
| `claude-code`      | yes    | yes    | yes    | yes    | yes    | yes    | yes    | yes    | yes    | gated  | no     | no     | no     | no     |
| `aider`            | yes    | yes    | gated  | gated  | yes    | gated  | assist | no     | gated  | no     | no     | gated  | no     | no     |
| `goose`            | yes    | yes    | yes    | yes    | yes    | gated  | assist | yes    | gated  | no     | no     | gated  | no     | no     |
| `chatgpt-handoff`  | assist | assist | no     | no     | assist | assist | assist | assist | assist | assist | no     | no     | no     | no     |
| `local-model`      | gated  | gated  | gated  | no     | gated  | gated  | assist | no     | no     | no     | no     | yes    | yes    | no     |
| `github-publisher` | no     | no     | no     | no     | no     | no     | no     | gated  | yes    | gated  | no     | no     | no     | no     |

### Cell notes

- `hermes-local.github_write = gated` — only via the
  `github_assistant` plugin, with `github.enabled: true`,
  `github.allow_writes: true`, and the repo on
  `github.allowed_repositories` (or that list empty).
- `hermes-local.redaction_safe = gated` — depends on which provider
  the user has selected. When using a local model, drafting stays on
  the device; when using a cloud provider, it does not.
- `codex.long_context_review = gated` — works for moderately large
  contexts but the router prefers `claude-code` for true
  long-context reviews.
- `codex.persistent_memory = no` — Codex sessions don't carry state
  the way Hermes does; the router relies on Hermes memory instead.
- `claude-code.architecture = yes` — preferred for design work; print
  mode + long context window are the reason.
- `aider.run_terminal = gated` — Aider can run shell commands when
  invoked with the right flags but the router uses Hermes for shell
  in most flows.
- `aider.network_fetch = no` — Aider doesn't browse; pair it with
  Hermes' web tools when external context is needed.
- `aider.github_read = gated` — possible via `aider --read`, but the
  router prefers `hermes-local` (via `github_assistant`) for repo
  metadata.
- `goose.github_read/write = gated/no` — depends on which Goose
  extensions / MCP servers the user has enabled; the router treats
  GitHub as Hermes' responsibility.
- `chatgpt-handoff.*` — every action is `assist` or `no`: the user
  performs it manually after Hermes drafts the prompt.
- `local-model.read_files/write_files/run_terminal = gated` — only
  when the local model is wired into Hermes as the agent's brain
  (i.e., Hermes executes tools on its behalf). A bare local
  inference endpoint with no tool runtime cannot do these things.
- `local-model.run_tests = no` — local models don't directly invoke
  the test runner; Hermes does, after the model produces a patch.
- `local-model.redaction_safe = yes` — provided the endpoint stays
  on-device and Hermes' provider is set to it.
- `github-publisher.network_fetch = gated` — only the GitHub API
  surface needed for branch/PR/comment operations; not general
  browsing.
- `github-publisher.github_write = gated` — same gates as
  `hermes-local`, since it *is* the channel `hermes-local` uses.

---

## How the router uses this

For each routing decision, the router builds a `required_capabilities`
set from the task type and evidence:

| Task type | Required capabilities |
|-----------|----------------------|
| `implementation` | read_files, write_files, run_terminal, validation_local (Hermes side) |
| `bug_fix` | read_files, write_files, run_tests |
| `test_repair` | read_files, write_files, run_tests |
| `refactor_small` | read_files, write_files, multi_file_refactor |
| `refactor_large` | read_files, write_files, multi_file_refactor, long_context_review |
| `architecture` | long_context_review, architecture |
| `code_review` | read_files, long_context_review |
| `long_context_review` | read_files, long_context_review |
| `plumbing` | read_files, run_terminal |
| `research` | network_fetch (or offline_capable, if `HERMES_OFFLINE=1`) |
| `redaction_safe_draft` | offline_capable, redaction_safe |
| `github_publish` | github_read, github_write |
| `manual_handoff` | (whatever the user asks; the assist row covers it) |

A worker that has `no` for any required capability is **disqualified**
before scoring. A worker with `gated` capabilities is allowed, but the
router includes the gate condition in the plan's `evidence` so the
user can see what would need to be unlocked.

---

## Maintenance

When adding a new worker:

1. Add an entry to `model-registry.yaml`.
2. Add a row to this matrix with honest values — `assist` and `gated`
   are better than `yes` if there's any caveat.
3. Document any non-obvious gate condition in the cell notes above.
4. Update `model-routing-policy.md` if the worker changes the
   fallback ladder shape for any task type.

The matrix is intentionally short and human-readable. If it grows
past a single screen, split capabilities into "build" vs "publish"
vs "research" tables rather than letting the master table sprawl.
