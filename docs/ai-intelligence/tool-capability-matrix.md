# Tool capability matrix

What each surface in `model-registry.yaml` can actually do. The router
uses this matrix to filter candidates: a surface is only a candidate
for a `kind` of task if it has the capabilities that `kind` requires.

If a capability is missing, the router pairs the primary worker with a
supporting worker that provides it — usually `hermes-local` for repo /
filesystem work, or `github-publisher` for publishing.

## Capability legend

| Symbol | Meaning |
|---|---|
| `Y` | Supported natively. |
| `~` | Partial / situational. Needs a flag, an MCP server, or a wrapper. |
| `N` | Not supported. Pair with another surface or route the job elsewhere. |
| `H` | Supported but requires explicit **human approval** before each use. |

## Matrix

| Capability                | hermes-local | codex | claude-code | aider | goose | chatgpt-handoff | local-model | github-publisher | android-termux-runtime | browser-research | human-approval |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Read files in repo        | Y | Y | Y | Y | Y | N | N | N | Y | N | N |
| Edit files in repo        | Y | Y | Y | Y | Y | N | N | N | Y | N | N |
| Run shell / terminal      | Y | Y | Y | ~ | Y | N | N | N | Y | N | N |
| Run tests / linters       | Y | Y | Y | ~ | Y | N | N | N | Y | N | N |
| Long-context reasoning    | ~ | ~ | Y | ~ | ~ | Y | N | N | N | N | N |
| Architecture / design     | ~ | ~ | Y | N | ~ | Y | N | N | N | N | ~ |
| Code review               | ~ | ~ | Y | N | ~ | Y | N | N | N | N | ~ |
| Multi-file refactor       | ~ | Y | Y | Y | Y | N | N | N | N | N | N |
| Structured JSON output    | ~ | Y | Y | N | ~ | N | ~ | N | N | N | N |
| Subagent orchestration    | Y | ~ | Y | N | Y | N | N | N | N | N | N |
| Web fetch / browse        | ~ | N | ~ | N | ~ | ~ | N | N | N | Y | N |
| Git operations (local)    | Y | Y | Y | Y | Y | N | N | ~ | Y | N | N |
| Push to remote            | H | H | H | H | H | N | N | H | H | N | Y |
| Open / update PRs         | N | N | ~ | N | N | N | N | H | N | N | Y |
| Comment on PRs / issues   | N | N | ~ | N | N | N | N | H | N | N | Y |
| Persistent memory         | Y | N | ~ | N | ~ | N | N | N | N | N | N |
| Offline / private exec    | Y | N | N | N | N | N | Y | N | Y | N | Y |
| Runs without auth         | Y | N | N | N | N | N | Y | N | Y | ~ | Y |
| Runs without network      | Y | N | N | N | N | N | Y | N | Y | N | Y |
| Runs on Android phone     | ~ | N | N | N | N | Y | N | N | Y | N | Y |
| User-facing handoff       | N | N | N | N | N | Y | N | N | N | N | Y |

## Notes per capability

- **Read / edit files.** `aider` reads and writes through git; behave
  the same as the others in practice. `chatgpt-handoff` and
  `local-model` cannot touch the filesystem — pair them with
  `hermes-local`.
- **Run shell / tests.** `aider` only runs commands when invoked
  through its `/run` or `--test-cmd` flow; treat as `~`.
- **Long-context reasoning.** `claude-code` is the strongest here; use
  it whenever the relevant context spans many files. `chatgpt-handoff`
  is also strong but is gated on a user tap.
- **Subagent orchestration.** `hermes-local` orchestrates via the
  Kanban / skill systems; `claude-code` via its built-in agents; `goose`
  via its MCP fan-out. `codex` only loosely "orchestrates" by spawning
  parallel exec sessions.
- **Web fetch / browse.** Most coding CLIs only browse through an MCP
  server or plugin (`~`). For first-class browsing, route to
  `browser-research`.
- **Push to remote.** Marked `H` everywhere except `github-publisher`
  (which is the sanctioned publish surface) and `human-approval`
  (which is what gates the push). Even on `github-publisher`, the
  router must surface the destination + diff for approval first.
- **Open / update / comment on PRs.** Only `github-publisher` does
  this safely. `claude-code` can prepare the body, but the actual
  GitHub call goes through `github-publisher`.
- **Persistent memory.** Only `hermes-local` has full Hermes memory.
  `claude-code` has its own per-project memory (CLAUDE.md and
  `~/.claude/projects/.../memory`) — treat as `~` because it's
  isolated from Hermes' main memory store. `goose` has session memory
  only.
- **Offline / private exec.** Used to gate jobs where the user said
  "stay on-device". Only `hermes-local`, `local-model`,
  `android-termux-runtime`, and `human-approval` satisfy this.
- **Runs on Android phone.** `hermes-local` is `~` because the Hermes
  Android orchestrator is read-mostly: it stages tasks, copies prompts,
  and watches results — it does not execute arbitrary code on the
  device. For real execution on the phone, pair with
  `android-termux-runtime` (and require approval, since every external
  Android action needs a tap).
- **User-facing handoff.** Only the `handoff` surfaces. Used to mark
  steps in the worker-selection-report that need the user to physically
  do something (copy a prompt, paste a result, tap a deep link).

## How the router uses this matrix

For each task `kind` from the routing policy:

1. Look up the required capabilities (below).
2. Keep registry entries whose row has `Y` (or `~` paired with a
   helper) for every required capability.
3. For capabilities marked `H`, attach the `human-approval` surface as
   a required supporting worker.
4. Feed the filtered list into the selection algorithm in
   `model-routing-policy.md`.

### Required capabilities per task kind

| Task kind | Required capabilities |
|---|---|
| `evidence` | Read files, persistent memory |
| `validation` | Run shell / tests |
| `implementation` | Read + edit files, run tests |
| `refactor-large` | Read + edit files, multi-file refactor |
| `architecture` | Long-context reasoning, architecture / design |
| `review` | Long-context reasoning, code review |
| `infra-long` | Run shell / tests, subagent orchestration |
| `drafting` | Long-context reasoning, user-facing handoff |
| `research-web` | Web fetch / browse |
| `private-llm` | Offline / private exec |
| `publish` | Open / update PRs OR comment on PRs / issues OR push to remote |
| `phone-side` | Runs on Android phone |
