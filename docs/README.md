# Hermes — Plain-English Operating Manual

Welcome. This folder is the human-readable manual for **Hermes Agent**:
what it is, what each piece does, and how to actually use it from a
phone, a laptop, a Windows box, or a server.

If you've never seen Hermes before, read this whole page once. Then
pick whichever sub-guide matches what you're trying to do.

> If you're an AI coding assistant working *on* Hermes, read
> [`../AGENTS.md`](../AGENTS.md) instead. This file is for humans
> running and operating Hermes.

---

## What Hermes is, in one paragraph

Hermes is a **self-improving AI agent** that you talk to in English.
You can hand it goals as small as *"summarize my inbox"* or as large
as *"audit this repo and open a draft PR with the cleanup,"* and it
will decompose the goal into a graph of small validated tasks, dispatch
each task to the right specialist worker (model + tools + environment),
run a peer-reviewer over the output, and publish the final result —
a pull request, a report, a Telegram message, a notification on your
phone — to wherever you asked. Every decision lands in an append-only
ledger so you can replay, diff, and audit what it did. The whole thing
runs on infrastructure you own — a $5 VPS, your laptop, your GPU
cluster, or Termux on your phone — with no telemetry and no
forced-cloud anything.

That's the system. The rest of this folder explains the parts.

---

## The shape of the system

Hermes has three layers you'll touch:

```
┌────────────────────────────────────────────────────────────────┐
│  Surfaces — where you talk to Hermes                           │
│    • Terminal (the `hermes` CLI / TUI)                          │
│    • Phone (Android cockpit app, Termux runtime)                │
│    • Voice (the voice-first capture path; driving mode)         │
│    • Chat (Telegram / Discord / Slack / WhatsApp / Signal DM)   │
│    • Remote (Windows Claude Code bridge, gateway HTTP API)      │
├────────────────────────────────────────────────────────────────┤
│  Backend — the brain that does the work                         │
│    • Agent loop (run_agent.py)                                  │
│    • Orchestrator (decomposes goals into task graphs)           │
│    • Kanban dispatcher (claims ready cards, spawns workers)     │
│    • Validation gates (schema, policy, judge)                   │
│    • Decision ledger (append-only audit trail)                  │
│    • Memory + skills (the self-improvement loop)                │
├────────────────────────────────────────────────────────────────┤
│  Integrations — where work goes when it's done                  │
│    • GitHub (PRs, issues, releases via github_assistant)        │
│    • Supabase (database / auth / storage via MCP)               │
│    • Vercel (deploys + runtime logs via MCP)                    │
│    • Files (artifacts in the job folder)                        │
│    • Notifications (gateway DM, phone push)                     │
└────────────────────────────────────────────────────────────────┘
```

The **surface** changes how the prompt gets in and how the answer
comes back. The **backend** never changes — same brain whether you
typed in a terminal or spoke into a phone in the car.

---

## Map of this manual

| If you want to… | Read this |
|---|---|
| Run your first orchestrated job | [orchestration/getting-started.md](orchestration/getting-started.md) |
| See an end-to-end **Prompt to PR** walkthrough | [orchestration/prompt-to-pr-demo.md](orchestration/prompt-to-pr-demo.md) |
| Drive Hermes from your phone | [mobile/mobile-app-guide.md](mobile/mobile-app-guide.md) |
| Operate the native JARVIS phone app, end to end | [mobile/README.md](mobile/README.md) → [mobile/JARVIS_MOBILE_NATIVE_USER_GUIDE.md](mobile/JARVIS_MOBILE_NATIVE_USER_GUIDE.md) |
| Understand JARVIS capabilities, permissions & emergency stop | [mobile/JARVIS_CAPABILITY_AND_PERMISSION_GUIDE.md](mobile/JARVIS_CAPABILITY_AND_PERMISSION_GUIDE.md) |
| Write code from your phone (Codex / Claude Code lanes) | [mobile/JARVIS_CODING_FROM_PHONE_GUIDE.md](mobile/JARVIS_CODING_FROM_PHONE_GUIDE.md) |
| Understand JARVIS evidence / cited research | [jarvis/JARVIS_EVIDENCE_RAG_GUIDE.md](jarvis/JARVIS_EVIDENCE_RAG_GUIDE.md) |
| Use high-autonomy coding mode safely (scoped/logged/revocable) | [jarvis/JARVIS_HIGH_AUTONOMY_CODING_MODE.md](jarvis/JARVIS_HIGH_AUTONOMY_CODING_MODE.md) |
| Ship the mobile cockpit (launch gate) | [launch/MOBILE_NATIVE_LAUNCH_CHECKLIST.md](launch/MOBILE_NATIVE_LAUNCH_CHECKLIST.md) |
| Use Hermes hands-free (voice-first, driving mode) | [voice/voice-first-user-guide.md](voice/voice-first-user-guide.md) |
| Run Hermes from Windows / drive Claude Code remotely | [remote/windows-claude-code-bridge-guide.md](remote/windows-claude-code-bridge-guide.md) |
| Have Hermes profile your GitHub history & learn your patterns | [profile/github-history-profile-guide.md](profile/github-history-profile-guide.md) |
| Lock everything down to private / local-only | [security/private-local-security-guide.md](security/private-local-security-guide.md) |
| Wire up GitHub, Supabase, and Vercel | [integrations/github-supabase-vercel-guide.md](integrations/github-supabase-vercel-guide.md) |
| Diagnose a stuck job or a broken integration | [troubleshooting/hermes-orchestration-troubleshooting.md](troubleshooting/hermes-orchestration-troubleshooting.md) |
| Deep-dive on a specific orchestration topic | [orchestration/](orchestration/) (full subfolder) |

Other useful pages outside this manual:

- [`../README.md`](../README.md) — install + quick start for the
  whole project.
- [`../AGENTS.md`](../AGENTS.md) — full development guide for AI
  coding assistants.
- [`../CLAUDE.md`](../CLAUDE.md) — Claude-specific entry point.
- [`../SECURITY.md`](../SECURITY.md) — security reporting.
- [`./github-integration.md`](github-integration.md) — the
  `github_assistant` plugin (native GitHub access).
- [`./hermes-local-orchestrator.md`](hermes-local-orchestrator.md) —
  the Android clipboard handoff flow (predates the orchestration
  stack, still relevant for the simplest mobile workflow).

---

## Plain-English glossary

These nine terms come up everywhere. Learn them once.

### Job
One orchestrated goal. *"Audit this repo and open a PR"* is one job.
A job has a prompt, a task graph, a ledger, and a folder under
`~/.hermes/jobs/<job-id>/`.

### Phase
The orchestrator decomposes a job into **phases** (the cards on the
kanban board). Each phase is a small, validatable unit — *"find unused
imports,"* *"apply the diff,"* *"open the PR."* Phases run in
parallel where they can; phases that depend on other phases wait on
their parents. Inside this manual you'll also see them called
**cards** or **tasks** — they're the same thing.

### Worker
The thing that executes a phase. In Hermes, a worker is a **profile**:
a model + a toolset + a skill set + an execution environment. You
configure profiles in `~/.hermes/config.yaml`. Examples ship under
`researcher`, `engineer`, `reviewer`.

### Approval
A decision point where Hermes pauses and waits for you. High-risk
phases (anything that mutates GitHub, sends external messages,
deletes data) classify as HIGH risk and **always** ask first. Low and
medium risk run automatically. You respond with `approve`, `deny`, or
`defer` — from the CLI, the phone app, or a gateway DM. See
[orchestration/getting-started.md §4](orchestration/getting-started.md#4-approve-or-escalate).

### Validation gate
Before a phase flips to `done`, it goes through three checks: a
**schema** check (did the worker return the expected shape?), a
**policy** check (is the mutation allowed?), and an optional **judge**
call (peer model reviews the output against acceptance criteria). A
failed gate auto-retries, reassigns, or escalates.

### Decision ledger
An append-only JSONL file at `~/.hermes/jobs/<job-id>/ledger.jsonl`.
Every spawn, model call, tool call, mutation, escalation, and gate
result lands here. You can `grep`, `jq`, or `diff` it; you can replay
a job from it.

### Skill
A Markdown playbook under `skills/` or `~/.hermes/skills/`. Skills
are not code — they are prompts the agent loads on demand via
`/<skill-name>`. Hermes ships hundreds; it also authors new ones for
itself after complex jobs (the self-improvement loop).

### Gateway
The messaging gateway (`gateway/`) that bridges your chat platforms
into a single Hermes process. Run `hermes gateway start` and a DM to
your Telegram bot lands as a Hermes turn, just like typing into the
CLI. Same backend on both ends.

### Profile
**Two meanings.** (a) A *worker profile* — the YAML config that
defines a model + tools + skills + environment combo. (b) A *user
profile* — the persistent model Hermes builds of you (your patterns,
preferences, repo history) by curating memory and observing past jobs.
Context usually disambiguates. The user-profile sense is documented
in [profile/github-history-profile-guide.md](profile/github-history-profile-guide.md).

---

## Quick start (60 seconds)

```bash
# 1. Install
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
source ~/.bashrc

# 2. Set a default model (any provider works)
hermes model

# 3. Talk to it
hermes

# 4. Or run a one-shot orchestrated job
bash scripts/hermes-orchestrate.sh "Audit this repo for unused imports"
```

That's it. The rest of this manual is variations on that loop.

Pick your next page from the [map above](#map-of-this-manual). If
you're unsure, read [orchestration/getting-started.md](orchestration/getting-started.md)
next — it walks you through your first real job and explains every
piece of jargon as it appears.

---

## What's the difference between "Hermes" and "the orchestrator"?

A reasonable question that comes up constantly.

- **Hermes** is the whole product. The CLI, the gateway, the plugins,
  the skills, the memory, the Android app — all of it.
- **The orchestrator** is one specific Hermes profile, running with a
  specific skill loaded (`kanban-orchestrator` or
  `enterprise-council/orchestrator`), whose job is to *decompose* a
  goal into the task graph that other profiles execute.

You can use Hermes without ever invoking the orchestrator — just type
`hermes` and chat. The orchestrator is what you reach for when a goal
is too big for one turn and you want fan-out, validation, and an audit
trail. The full orchestration system has its own folder:
[orchestration/](orchestration/).

---

## Where things live on disk

```
~/.hermes/
├── config.yaml          # your settings (profiles, providers, routing)
├── .env                 # API keys — never seen by the agent itself
├── jobs/                # one folder per orchestrated job
│   └── <job-id>/
│       ├── prompt.md
│       ├── plan.json
│       ├── ledger.jsonl
│       ├── cards/<card-id>/
│       └── summary.md
├── skills/              # user-created and auto-authored skills
├── memory/              # SQLite memory backend (default)
├── sessions.db          # SQLite session store (full-text search)
├── logs/
│   ├── agent.log
│   ├── errors.log
│   └── gateway.log
└── pid/                 # PID files for daemonized processes
```

Everything is plain files (or SQLite). You can back up `~/.hermes`
with rsync, you can grep the ledger, you can rsync a job folder to
another machine to continue it.

---

## How Hermes learns from past jobs

Three loops, all running quietly while you work.

1. **Skill proposals.** When the orchestrator completes a complex
   job, it can author a new skill that codifies what worked. The
   curator (`enterprise/monitor.py`) reviews proposals and either
   accepts them (writes to `~/.hermes/skills/`) or discards. List
   auto-authored skills with `hermes skills list --user-created`;
   the `[auto]` tag marks them.
2. **Memory curation.** The agent writes facts, preferences, and
   goals to its memory backend. Periodic nudges remind it to persist
   important context across sessions. Default backend is local
   SQLite; cloud backends (Honcho, Mem0, Supermemory) are optional.
3. **Routing learning.** The model router scores past completions per
   profile per model. When a profile's preferred model starts failing
   judges or escalating more often, the router can demote it. Routing
   rules live in `~/.hermes/config.yaml` under `orchestration.routing`.

You can turn each off independently. See
[`../AGENTS.md` §self-improvement](../AGENTS.md) for the dev side and
[orchestration/self-improvement-loop.md](orchestration/self-improvement-loop.md)
for the runtime side.

---

## When things go wrong

Read in this order:

1. **The job folder.** `~/.hermes/jobs/<job-id>/summary.md` and
   `ledger.jsonl` together explain almost everything.
2. **`hermes doctor`** — environment + install health.
3. **[Troubleshooting table](troubleshooting/hermes-orchestration-troubleshooting.md#quick-reference-table)** —
   the symptom-to-fix table.
4. **GitHub issues** — attach the job folder (tar / zip), `hermes
   doctor` output, and `hermes profile list`.

---

## Cross-references at a glance

| Topic | File |
|---|---|
| Install, providers, models | [`../README.md`](../README.md) |
| Develop on Hermes itself | [`../AGENTS.md`](../AGENTS.md) |
| Claude-specific dev hints | [`../CLAUDE.md`](../CLAUDE.md) |
| Security policy + reporting | [`../SECURITY.md`](../SECURITY.md) |
| Contributing process | [`../CONTRIBUTING.md`](../CONTRIBUTING.md) |
| Orchestration overview | [orchestration/README.md](orchestration/README.md) |
| Decision ledger schema | [orchestration/decision-ledger.md](orchestration/decision-ledger.md) |
| Worker adapters | [orchestration/worker-adapters.md](orchestration/worker-adapters.md) |
| Open data sources for training JARVIS | [ai-intelligence/top-open-data-sources-for-training.md](ai-intelligence/top-open-data-sources-for-training.md) |
| Termux phone-first runtime | [termux/hermes-phone-first-runtime.md](termux/hermes-phone-first-runtime.md) |
| Android app contract | [android/hermes-apk-api-contract.md](android/hermes-apk-api-contract.md) |

Welcome aboard. If something here is unclear, the docs are wrong —
open an issue.
