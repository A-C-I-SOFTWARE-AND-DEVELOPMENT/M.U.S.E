# muse Orchestration

muse Orchestration is the umbrella name for the way muse
turns one human-sized request — *"Audit this repo"*, *"Build this into
production quality"*, *"Get my inbox to zero by Friday"* — into a
graph of small, validated, auditable jobs run by specialist workers.

It is not one tool. It is a stack:

```
┌───────────────────────────────────────────────────────────────┐
│  Entry surfaces                                                │
│    hermes (TUI)        scripts/hermes-orchestrate.sh           │
│    /orchestrate ...    /orchestrator status                    │
│    Android cockpit     Telegram / Discord / Slack gateway      │
├───────────────────────────────────────────────────────────────┤
│  Orchestrator skills                                           │
│    kanban-orchestrator         enterprise-council/orchestrator │
│    autonomous-ai-agents/*      (your custom orchestrator)      │
├───────────────────────────────────────────────────────────────┤
│  Job substrate                                                 │
│    Kanban board (SQLite)      Decision ledger (audit)          │
│    Dependency engine          Validation gates / Judge         │
├───────────────────────────────────────────────────────────────┤
│  Worker adapters                                               │
│    kanban workers   model providers   tool environments        │
│    (docker, ssh, modal, daytona, singularity, local, vercel)   │
├───────────────────────────────────────────────────────────────┤
│  Publishing                                                    │
│    github_assistant plugin     gateway delivery                │
│    GitHub MCP server           local filesystem / artifacts    │
└───────────────────────────────────────────────────────────────┘
```

Everything below tells you how those pieces fit together and how to
drive them from a prompt, a phone, a Termux shell, or a fully offline
laptop.

## Read this first

| If you want to… | Start here |
|---|---|
| Run your first orchestrated job | [getting-started.md](getting-started.md) |
| Install a ready-made planner/executor/critic team | [orchestrator-trio.md](orchestrator-trio.md) |
| See an end-to-end "prompt → PR" demo | [prompt-to-pr-demo.md](prompt-to-pr-demo.md) |
| Drive the orchestrator from your phone | [android-termux-demo.md](android-termux-demo.md) |
| Add a new worker / model / environment | [worker-adapters.md](worker-adapters.md) |
| Keep everything on-device (no cloud) | [private-local-mode.md](private-local-mode.md) |
| Debug a stuck job | [troubleshooting.md](troubleshooting.md) |
| Look something up quickly | [faq.md](faq.md) |

## What muse Orchestration is

muse Orchestration takes a high-level goal and:

1. **Decomposes** it into a task graph — independent lanes run in
   parallel, dependent lanes wait on their parents.
2. **Routes** each task to the right specialist profile (the *worker*),
   with the right model behind it, in the right execution environment.
3. **Validates** each result with a judge / gate before it counts as
   *done*. Failed validations re-spawn or escalate.
4. **Publishes** the outcome — a PR, a comment, a file, a Telegram
   message, an Android notification — over whichever channel the user
   asked for.
5. **Audits** every decision in a permanent ledger so you can rerun,
   compare, and learn from past sessions.

It is the same pattern whether you're auditing a repo, writing a
report, paying invoices, or running a 12-hour overnight refactor.

## What muse Orchestration is *not*

- Not a managed cloud service. Everything runs where you point it —
  laptop, $5 VPS, GPU cluster, Termux on your phone, an air-gapped
  workstation.
- Not a single-vendor stack. The model behind each worker is yours to
  pick (Anthropic, OpenAI, OpenRouter, Nous Portal, NovitaAI, NIM,
  z.ai/GLM, MiMo, MiniMax, Hugging Face, local llama.cpp, vLLM, ...).
- Not an opaque agent that "just does things." Every action goes
  through the decision ledger, every mutation goes through a policy
  gate, every high-risk step asks before acting.
- Not a wrapper around Claude Code Routines or any specific provider's
  agent runtime. muse Orchestration uses Claude when you point it at
  Claude, GPT when you point it at GPT, a local model when you point
  it at one. The orchestration shape doesn't change.

## The five primitives

You only need five concepts to use muse Orchestration end-to-end.
Every doc in this folder builds on them.

### 1. Job

A *job* is one orchestrated goal. It has:

- a **prompt** (the user's request, verbatim where possible),
- a **task graph** (the cards the orchestrator decomposed it into),
- a **decision ledger** entry (audit trail),
- a **status** (`planning → running → validating → done | blocked | failed`).

Jobs live in `~/.hermes/jobs/<job-id>/` on disk and as rows in the
Kanban SQLite database. See [the job folder explanation](getting-started.md#the-job-folder)
for what's inside.

### 2. Worker

A *worker* is the thing that actually executes a card. In muse
workers are **profiles** — named muse processes with a specific
model, toolset, skill set, and execution environment. Examples:

- `researcher` — long-context model + web tools + no shell
- `engineer` — coding model + sandboxed terminal + GitHub plugin
- `reviewer` — careful model + read-only tools + judge skill loaded

`muse profile list` shows what's configured. The orchestrator only
hands work to profiles that actually exist on this machine — unknown
assignees silently fail. See [worker-adapters.md](worker-adapters.md).

### 3. Model routing

Every worker has a default model, but the orchestrator can override
per-card based on size, sensitivity, cost budget, or latency need.
Routing rules live in `~/.hermes/config.yaml` under `orchestration.routing`.
See [worker-adapters.md#model-routing](worker-adapters.md#model-routing).

### 4. Validation gate

Before a card flips to `done`, it goes through a gate:

- a **schema check** (did the worker return the expected shape?),
- a **policy check** (is the proposed mutation allowed for its risk
  tier?),
- optionally a **judge call** (an LLM peer-reviews the output against
  the card's acceptance criteria).

Failed gates either auto-retry, re-route to a different worker, or
escalate to the human. See
[getting-started.md#validation-gates](getting-started.md#validation-gates).

### 5. Decision ledger

Every spawn, every model call, every mutation, every escalation is
appended to a tamper-evident ledger at
`~/.hermes/jobs/<job-id>/ledger.jsonl`. The ledger is the audit trail
the Judge, the Monitor, and `muse orchestrator status` read from.
You can replay a job from its ledger and you can diff two ledgers
when one run goes wrong.

## Entry surfaces — pick whichever fits your hands

The orchestrator has the same brain no matter where you talk to it.
The surfaces differ only in how the request gets in and how the
result gets out.

| Surface | Best for |
|---|---|
| `muse` (TUI) | Iterative work, you're at a keyboard |
| `bash scripts/hermes-orchestrate.sh "<goal>"` | One-shot, scriptable, CI-friendly |
| `/orchestrate <goal>` slash command | From inside a muse conversation |
| `/orchestrator status` | Quick check on running jobs |
| Android cockpit (`apps/android`) | From your phone, with a real backend |
| Termux gateway | From your phone, *as* the backend |
| Gateway DM (Telegram / Discord / Slack / WhatsApp / Signal) | Hands-free, ambient |

All of them route into the same job substrate, so a job started on
your laptop can be watched from your phone and published to GitHub
without any state migration.

## A typical session

```bash
# 1. Drop a goal on the orchestrator.
bash scripts/hermes-orchestrate.sh "Audit this repo for unused code and stale deps, open a draft PR with the cleanup."

# 2. Watch it work.
muse orchestrator status            # live overview
muse kanban tail <job-id>           # follow one job

# 3. Land the result.
# The orchestrator opens the PR via the github_assistant plugin (or
# the GitHub MCP server, whichever you've wired up). You review it
# like any human PR.
```

That's the whole loop. The rest of this folder is variations on it.

## Swarm Grainler Parallel

For code-producing work specifically, **Swarm Grainler Parallel**
([swarm-grainler-parallel.md](swarm-grainler-parallel.md)) composes the five
primitives into one canonical, collision-free pipeline: a goal is decomposed
into **grains** with *provably disjoint file-domains*, each grain becomes its
own specialized LLM (own model lane, toolset, iteration budget, token-juice
context, dedicated memory namespace), the grains run in parallel in isolated
git worktrees, every step is dated and ledgered, and a self-update loop
auto-applies the reversible learnings. Run it with `python -m hermes_cli.swarm
"<goal>" --grains grains.json` or the `/swarm` skill.

## Where to go next

Start with [getting-started.md](getting-started.md). When that
clicks, the rest of these docs are reference material — read on demand.

For the unified pre-dispatch layer that composes the Navigator (where to edit)
with the council Dispatcher (who engages) into one `DispatchPlan` + generalized
`TaskQueue`, see
[unified-navigator-dispatcher.md](unified-navigator-dispatcher.md).
