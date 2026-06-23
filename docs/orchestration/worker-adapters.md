# Worker adapters

A worker is the thing that actually executes a Kanban card. In
muse workers are **profiles** — named processes with their own
model, toolset, skill set, and execution environment. The
orchestrator does nothing more interesting than picking which
profile gets which card.

This doc covers:

- How profiles map to workers.
- The model-routing layer that overrides a profile's default.
- The terminal-environment backends the worker runs inside.
- Recipes for the most common worker fleets.
- How to add a custom worker.

## Profile = worker

```yaml
# ~/.hermes/config.yaml
profiles:
  researcher:
    model: nous:hermes-3-405b
    enabled_toolsets: [web, fetch]
    disabled_toolsets: [terminal, file_edit]
    preloaded_skills:
      - research/literature-review
    environment: local

  engineer:
    model: anthropic:claude-sonnet
    enabled_toolsets: [terminal, file_edit, github_assistant]
    preloaded_skills:
      - software-development/python-best-practices
    environment: docker
    environment_config:
      image: python:3.11-slim
      workspace_mount: ${CWD}

  reviewer:
    model: openai:gpt-5
    enabled_toolsets: [file_read, fetch]
    preloaded_skills:
      - enterprise-council/judge
      - software-development/code-review-best-practices
    environment: local
```

`muse profile list` shows what's loaded. `muse profile create
<name>` walks you through making a new one. Editing the YAML
directly works too; `/reload-skills` (or restarting) picks up the
change.

### Naming matters

The orchestrator only dispatches to profile names that exist. If
its plan says `researcher` and you don't have one, the card sits
in `ready` forever. The kanban dispatcher does **not** autocorrect
or fallback. See [troubleshooting.md#stuck-in-ready](troubleshooting.md#stuck-in-ready).

The conservative default: have at least these three names
configured before you start fanning out work:

- `researcher` — read-heavy, long context, no shell
- `engineer` — code edits, sandboxed shell, scoped GitHub access
- `reviewer` — read-only, judge-style skills loaded

The orchestrator skill (`skills/devops/kanban-orchestrator/SKILL.md`)
will adapt to whatever it finds via `muse profile list`. It does
not invent names.

## Model routing

Every profile has a default model, but a sufficiently fancy
orchestrator setup can override per-card. Routing rules live under
`orchestration.routing` in `~/.hermes/config.yaml`:

```yaml
orchestration:
  routing:
    # Card body longer than 80k tokens → switch researcher to a long-context model.
    - when: card.assignee == "researcher" and card.input_tokens > 80000
      use: nous:hermes-3-1m-context

    # HIGH-risk cards → upgrade to a stronger model for reviewer.
    - when: card.risk == "HIGH" and card.assignee == "reviewer"
      use: anthropic:claude-opus

    # Cost-cap an experimental run: clamp anything to Sonnet.
    - when: job.tags has "experiment"
      use: anthropic:claude-sonnet

    # Local-only mode: never call cloud providers.
    - when: profile.environment == "airgapped"
      use: local:llama-cpp/qwen-2.5-coder-32b
```

Rules evaluate top-down; first match wins; no match → use the
profile's default model. The active route is recorded in the
ledger, so you can later answer *"why did this card go to Opus and
that one to Sonnet?"*.

### Manual override per job

```bash
bash scripts/hermes-orchestrate.sh "..." \
  --model engineer=anthropic:claude-opus,reviewer=openai:gpt-5-thinking
```

…or inside `muse`:

```
/orchestrator route engineer anthropic:claude-opus
/orchestrate <goal>
```

The override sticks for the lifetime of the job.

## Environments

The worker process runs inside an **environment** — the terminal
backend that owns its shell, filesystem, and network. muse ships
seven:

| Environment | Best for | Notes |
|---|---|---|
| `local` | Quick wins, low-trust agents, scripts | Workers share the host filesystem; isolate with `disabled_toolsets` |
| `docker` | Engineer / publisher profiles | Sandboxed, snapshot-able, no host bleed |
| `ssh` | Remote dev box, GPU box | Worker runs on the box, orchestrator stays on laptop |
| `singularity` | HPC, air-gapped | Reproducible OCI images, no daemon |
| `modal` | Serverless, hibernating | Workers wake on demand, ~zero idle cost |
| `daytona` | Persistent dev sandboxes | Long-lived, snapshot-restorable |
| `vercel` | Edge-style ephemeral runs | Fast cold start, short-lived |

Configure under a profile's `environment` key. Docker example:

```yaml
profiles:
  engineer:
    environment: docker
    environment_config:
      image: nousresearch/hermes-engineer:latest
      workspace_mount: ${CWD}
      gpus: 0
      memory: 4g
      env:
        - HERMES_TENANT
        - GITHUB_PERSONAL_ACCESS_TOKEN
```

The orchestrator doesn't pick environments — the profile does.
Switching `engineer` from `local` to `docker` is a one-line config
change, no code edits.

## Recipes

### Solo developer, one machine

Two profiles is enough:

```yaml
profiles:
  default:
    model: anthropic:claude-sonnet
    environment: local
  engineer:
    model: anthropic:claude-sonnet
    environment: docker
    environment_config:
      image: python:3.11-slim
```

The orchestrator uses `default` for planning and `engineer` for
file edits. Quiet, cheap, no fan-out.

### Small team — full audit fleet

```yaml
profiles:
  researcher:
    model: nous:hermes-3-405b
    enabled_toolsets: [web, fetch]
    environment: local
  engineer:
    model: anthropic:claude-sonnet
    enabled_toolsets: [terminal, file_edit, github_assistant]
    environment: docker
  reviewer:
    model: openai:gpt-5
    enabled_toolsets: [file_read]
    environment: local
    preloaded_skills:
      - enterprise-council/judge
```

Three profiles, three models, two environments. This is the demo
fleet used in [prompt-to-pr-demo.md](prompt-to-pr-demo.md).

### Multi-tenant SaaS

Add `HERMES_TENANT` to every spawn and use Modal for serverless
isolation:

```yaml
profiles:
  tenant-engineer:
    model: anthropic:claude-sonnet
    environment: modal
    environment_config:
      app_name: hermes-tenant-${HERMES_TENANT}
      cpu: 2
      memory: 8192
```

Each tenant's workers hibernate when idle and wake on demand,
charging only for active seconds. Kanban rows are tagged with the
tenant id and the dispatcher only spawns workers whose tenant
matches.

### Fully offline

Local models, local environment, no plugins that touch the network:

```yaml
profiles:
  default:
    model: local:llama-cpp/qwen-2.5-coder-32b
    enabled_toolsets: [terminal, file_edit, file_read]
    disabled_toolsets: [web, fetch, github_assistant]
    environment: local

orchestration:
  routing:
    - when: true
      use: local:llama-cpp/qwen-2.5-coder-32b
```

See [private-local-mode.md](private-local-mode.md) for the full
recipe including provider configuration.

## Adding a custom worker

A "worker type" you can't get by composing existing primitives is
rare. Before writing code, try:

1. **A new profile with a different toolset / skill mix.** Usually
   sufficient.
2. **A new plugin under `plugins/`** that ships extra tools the
   profile can use. Plugins are auto-discovered; see
   [`plugins/github_assistant/`](../../plugins/github_assistant/)
   for the smallest end-to-end example (8 tools, gates, README,
   plugin.yaml).
3. **A new skill under `skills/`** that codifies a procedure. The
   `kanban-orchestrator` skill is itself just a Markdown playbook
   loaded into the orchestrator profile's system prompt.

If you really need a new *environment*, e.g. a custom serverless
backend, implement the protocol in `tools/environments/`. The
existing backends (`local.py`, `docker.py`, `modal.py`, …) are the
template — about 200–600 LOC each.

## Inspecting what a worker actually did

Every worker writes its trace to
`~/.hermes/jobs/<job-id>/cards/<card-id>/trace.jsonl`. One JSON
object per line:

```json
{"ts": "2026-05-23T14:03:11.041Z", "kind": "spawn", "profile": "researcher", "model": "nous:hermes-3-405b"}
{"ts": "2026-05-23T14:03:11.218Z", "kind": "model_call", "tokens_in": 4218, "tokens_out": 312}
{"ts": "2026-05-23T14:03:14.901Z", "kind": "tool_call", "tool": "web_search", "args_redacted": true}
...
{"ts": "2026-05-23T14:04:36.510Z", "kind": "gate", "schema": "ok", "policy": "LOW", "judge": "pass(0.92)"}
{"ts": "2026-05-23T14:04:36.677Z", "kind": "complete", "summary": "found 47 unused imports..."}
```

`grep`, `jq`, and a normal text editor are the supported tools for
analysis. The ledger format is intentionally stable — third-party
tooling can read it without a muse runtime.

## See also

- [`skills/devops/kanban-orchestrator/SKILL.md`](../../skills/devops/kanban-orchestrator/SKILL.md)
  — the orchestrator's actual playbook, in full.
- [`enterprise/`](../../enterprise/) — the council pattern (Orchestrator
  + Judge + Monitor + leaf agents). Useful when "engineer / reviewer"
  is too coarse for your domain.
- [`plugins/`](../../plugins/) — sample plugins (kanban dashboard,
  observability, model providers) and the layout you'd copy for a
  new one.
