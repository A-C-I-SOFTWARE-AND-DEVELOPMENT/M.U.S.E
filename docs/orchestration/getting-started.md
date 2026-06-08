# Getting started with M.U.S.E. Orchestration

This doc walks you from a clean M.U.S.E. install to a first
orchestrated job, and explains every piece of jargon that shows up
along the way. Allow ~10 minutes.

> If you have not installed M.U.S.E. yet, do the
> [Quick Install](../../README.md#quick-install) first and come back.

## Prerequisites

- M.U.S.E. installed (`muse doctor` passes).
- At least one provider configured (`muse model` shows a default
  model). Anything that works for `muse` works for the
  orchestrator — there is no separate API key surface.
- A working directory with a `git` repo if you want the
  prompt-to-PR flow. For local-only jobs, any folder is fine.

If you want GitHub publishing later, also enable the
`github_assistant` plugin — see
[docs/github-integration.md](../github-integration.md). It's not
required for the first run.

## 1. Confirm your profiles

The orchestrator dispatches to **profiles**, not to abstract roles.
Find out what you have:

```bash
muse profile list
```

You'll see something like:

```
NAME            MODEL                     ENV       SKILLS LOADED
default         openrouter:sonnet         local     (auto)
researcher      nous:hermes-3-405b        local     web,fetch
engineer        anthropic:claude-sonnet   docker    coding,github
reviewer        openai:gpt-5              local     judge
```

A fresh install only has `default`. That's enough to run your first
orchestrated job — the orchestrator will route everything to
`default`. To get real parallelism and specialization, add a few
profiles with `muse profile create <name>` and assign different
models / toolsets to them. See [worker-adapters.md](worker-adapters.md)
for recipes.

## 2. Run your first job

The simplest entry point is the shell script:

```bash
bash scripts/hermes-orchestrate.sh "Audit this repo"
```

What happens:

1. The script resolves the current git repo (or CWD) and writes a
   new job folder under `~/.hermes/jobs/<job-id>/`.
2. It spawns a M.U.S.E. process with the **orchestrator profile**
   (default: `default` with the `kanban-orchestrator` skill
   pre-loaded). That process reads the prompt, decomposes it into
   Kanban cards, and assigns each card to a profile.
3. The Kanban dispatcher picks up `ready` cards and spawns worker
   processes for them.
4. As each card finishes, the validation gate runs, the ledger gets
   appended, and dependent cards get promoted.
5. When everything is `done`, the orchestrator writes a summary to
   the job folder and (optionally) opens a PR / sends a gateway
   message.

You'll see a job id in stdout — something like
`job_2026_05_23_a4f7c1`. Hold onto it; the next few commands take it
as an argument.

> **Equivalent in-CLI flow.** Inside `muse`, type
> `/orchestrate Audit this repo` and you get the same behavior. The
> shell script is what you reach for from CI or a phone shortcut.

## 3. Watch it run

Pick whichever you like:

```bash
muse orchestrator status             # all active jobs, one line each
muse orchestrator status <job-id>    # one job, with task graph
muse kanban tail <job-id>            # streaming task log
```

The TUI dashboard (under `ui-tui/`) shows the same data with a graph
view. Launch it with `muse --tui` and switch to the **Orchestrator**
pane.

If you have the Android cockpit installed, the same job appears on
your phone within seconds — see [android-termux-demo.md](android-termux-demo.md).

## 4. Approve or escalate

Some tasks finish silently. Some pause and ask you something — that's
the policy gate doing its job. You'll see them as:

- a row in `muse orchestrator status` with state `escalated`,
- a notification on the Android app or in your gateway DM,
- an `ESCALATE:` line in the streaming log.

Respond with:

```bash
muse kanban respond <task-id> approve
muse kanban respond <task-id> deny    --reason "drop the auth changes"
muse kanban respond <task-id> defer   --reason "ask me tomorrow"
```

Approve / deny / defer is the entire human-in-the-loop API. There is
no fourth option, on purpose — the council policy
(`enterprise.policy`) classifies risk and only HIGH-risk tasks (or
repeated judge failures) ever reach you.

## 5. Land the result

By default, the result lands wherever the orchestrator skill chose to
publish:

- A code-style job typically opens a **draft PR** via the
  `github_assistant` plugin (or the GitHub MCP server if that's what
  you have wired up). You review it like any human PR.
- A report-style job writes a Markdown file under
  `~/.hermes/jobs/<job-id>/output/` and posts a link to your gateway
  DM.
- A long-running automation publishes to wherever its cron job
  declares (`muse cron …` syntax — same engine).

You can override per-job with `--deliver`:

```bash
bash scripts/hermes-orchestrate.sh "Audit this repo" \
  --deliver pr,telegram \
  --pr-target "echerd27-design/hermes-agent" \
  --pr-draft
```

## Skill invocation — how the orchestrator picks its playbook

The orchestrator is a M.U.S.E. profile with the
**`kanban-orchestrator`** skill loaded (or
`enterprise-council/orchestrator` for enterprise mode). The skill is
the playbook — the "decompose, don't execute" rules, the fan-out
patterns, the pitfalls.

Skills are loaded in three ways:

1. **Pre-loaded by the orchestrator profile.** Configure in
   `~/.hermes/config.yaml`:

   ```yaml
   profiles:
     orchestrator:
       model: anthropic:claude-sonnet
       preloaded_skills:
         - kanban-orchestrator
         - autonomous-ai-agents/hermes-agent
   ```

2. **Invoked inline via slash.** Inside any M.U.S.E. conversation:

   ```
   /kanban-orchestrator     # loads the playbook on demand
   /enterprise-orchestrator # switches to enterprise council mode
   ```

3. **Auto-injected** for kanban workers. Every kanban worker process
   gets the `KANBAN_GUIDANCE` system-prompt block injected
   automatically — the "don't do the work yourself" rule and the
   basic lifecycle, no skill load required.

After editing a skill on disk:

```
/reload-skills
```

…inside any active conversation rescans and reloads. No restart
needed.

## Slash commands

The full orchestration vocabulary, available in any M.U.S.E.
conversation (CLI, gateway, Android cockpit when connected to a
gateway):

| Command | What it does |
|---|---|
| `/orchestrate <goal>` | Start a new job in the current context |
| `/orchestrator status` | List active jobs |
| `/orchestrator status <job-id>` | Detail for one job, with task graph |
| `/orchestrator cancel <job-id>` | Stop the job and mark it `cancelled` |
| `/orchestrator replay <job-id>` | Re-run from a chosen ledger entry |
| `/kanban-orchestrator` | Load the orchestrator playbook into the current session |
| `/reload-skills` | Re-scan skill files after edits |
| `/profiles` | List configured worker profiles |
| `/<skill-name>` | Load any skill by name |

The CLI also has top-level subcommands for the same operations
(`muse orchestrator …`, `muse kanban …`). The slash forms live
inside an interactive session; the subcommand forms are scriptable.

## The job folder

Each job gets a folder at `~/.hermes/jobs/<job-id>/`:

```
job_2026_05_23_a4f7c1/
├── prompt.md           # the original user goal, verbatim
├── plan.json           # the orchestrator's task graph (cards, parents, assignees)
├── ledger.jsonl        # append-only decision ledger
├── cards/              # one folder per Kanban card
│   ├── t_001_research/
│   │   ├── input.md    # what the worker was given
│   │   ├── output.md   # what the worker produced
│   │   ├── trace.jsonl # tool calls + model responses
│   │   └── gate.json   # validation gate result
│   └── ...
├── output/             # final artifacts (reports, diffs, transcripts)
└── summary.md          # human-readable wrap-up
```

Everything is plain files. You can `grep` the ledger, diff outputs
across two runs, or rsync a job folder to another machine to
continue it.

## Validation gates

Every card runs through a gate before flipping to `done`:

1. **Schema gate.** Did `kanban_complete` return the keys the card
   asked for? Did any `created_cards=[...]` list reference cards that
   actually exist?
2. **Policy gate.** Run `enterprise.policy.classify(task)` on the
   mutation. LOW → auto-approve, MEDIUM → auto-approve with audit,
   HIGH → escalate. Rules in
   [`enterprise/policy.py`](../../enterprise/policy.py).
3. **Judge gate** (optional, default on for orchestrators that load
   `enterprise-council/judge`). Show the worker's output to a peer
   model with the card's acceptance criteria. Pass / fail, with
   reasons.

If any gate fails:

- **Retry** up to `max_retries` (default 2) with a fresh worker if
  the failure looks transient.
- **Reassign** to a different profile if the worker keeps producing
  the same bad output. The `Recovery` section in the dashboard drawer
  exposes this.
- **Escalate** to the human if retries are exhausted.

You don't usually configure this — the orchestrator skill knows the
default policy and most users never touch the gate. The hooks are
there when you need them.

## What's next

- [prompt-to-pr-demo.md](prompt-to-pr-demo.md) — a real end-to-end
  example.
- [worker-adapters.md](worker-adapters.md) — when one default
  profile is no longer enough.
- [private-local-mode.md](private-local-mode.md) — turn off every
  cloud surface.
- [troubleshooting.md](troubleshooting.md) — the first thing to read
  when something is stuck.
