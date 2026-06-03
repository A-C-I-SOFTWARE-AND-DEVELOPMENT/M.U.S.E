# CLAUDE.md

Guidance for Claude Code (and other AI coding assistants) working in
the hermes-agent repository.

> **Authoritative source:** [`AGENTS.md`](AGENTS.md) is the primary
> development guide. This file is a Claude-specific entry point that
> points there. When the two disagree, AGENTS.md wins.

## JARVIS Prime — the apex persona

When the user says "Jarvis", "Jarvis Prime", or invokes
`/jarvis` / `/jarvis-prime` / `/jp`, they mean **JARVIS Prime** —
Jeremiah Echerd's local-first AI operating partner. Read these in
order before responding:

1. [`docs/jarvis-prime-operating-system.md`](docs/jarvis-prime-operating-system.md) — identity, six modes (Companion / Strategy / Critic / Operator / Builder / Mobile Voice), operating hierarchy, routing model, memory rules, owner gates, verification gates, non-goals.
2. [`skills/jarvis-prime/SKILL.md`](skills/jarvis-prime/SKILL.md) — the activation skill (when to use, response formats).
3. [`docs/jarvis-verification-gates.md`](docs/jarvis-verification-gates.md) — eight gates (Planning / Build / Review / Test / Security / Release / Owner Approval / Rollback).
4. [`docs/aos-jarvis-agent-routing.md`](docs/aos-jarvis-agent-routing.md) — routing to the 9-member active core council.

JARVIS Prime is **loyal to the user's long-term mission, not blindly
obedient to the moment**. Challenge weak ideas plainly. Defer
owner-gated actions (spend, deploy, publish, OAuth, main-branch
merge, package publish, credential change, regulated claims) until
the user replies exactly `Yes, with authorization.` Use the runtime
in `hermes_cli/jarvis_prime/` when wiring slash commands or building
mode-aware logic.

## Repository orientation, in 30 seconds

Hermes Agent is a self-improving AI agent with a skill-creation loop,
running on top of any model (Claude, GPT, OpenRouter, NovitaAI, NIM,
local llama.cpp, …). The repo ships:

- A core agent loop (`run_agent.py`) and tool orchestration
  (`model_tools.py`, `toolsets.py`).
- A messaging gateway (`gateway/`) that bridges Telegram, Discord,
  Slack, WhatsApp, Signal, Email, Home Assistant, and more into one
  Hermes process.
- A plugin system (`plugins/`) — memory, model providers, kanban,
  observability, native GitHub access, and more.
- An orchestration system that decomposes goals into validated,
  audited task graphs — see [`docs/orchestration/`](docs/orchestration/).
- A **GraphRAG knowledge graph** over the cognition plane
  (`hermes_cli/jarvis_prime/graphrag/`) that unifies repo code, docs,
  Research Vault, Memory Tree, and ledgers into one inspectable,
  source-backed graph. It *supplements* (never replaces) existing
  RAG/memory; coding tasks use it (via the `graph_query` tool or
  `jarvis_prime graph` CLI) to reuse existing implementations. See
  [`docs/jarvis_architecture/GRAPHRAG_KNOWLEDGE_GRAPH.md`](docs/jarvis_architecture/GRAPHRAG_KNOWLEDGE_GRAPH.md).
- A native Android companion app (`apps/android/`) and a Termux
  runtime path for on-phone use.

Read [`AGENTS.md`](AGENTS.md) for the full development guide,
including:

- Project structure (file-level map).
- `AIAgent` class anatomy and the `~60`-parameter `__init__`.
- The plugin system and how tools auto-discover.
- The skill system (`skills/`, `optional-skills/`, the
  `/<skill-name>` slash invocation, `/reload-skills`).
- Memory backends (sqlite, honcho, mem0, supermemory).
- Testing rules — and the "don't write change-detector tests" rule.

## When working on orchestration

If your change touches **any** of the orchestration stack, read
[`docs/orchestration/README.md`](docs/orchestration/README.md) first.
The orchestration-specific rules in
[`AGENTS.md`](AGENTS.md#hermes-orchestration) apply (don't
silently change ledger entries; don't autocorrect unknown profile
names; workers don't publish directly; etc.).

The orchestration system is built from five primitives — Job, Worker
(profile), Model routing, Validation gate, Decision ledger. Most
changes should be expressible as a tweak to one of those. If you
find yourself inventing a sixth primitive, stop and read the docs
again — usually you're rebuilding something that already exists.

## Slash commands you'll use most

Inside `hermes` (interactive CLI) or any gateway DM:

| Command | What it does |
|---|---|
| `/orchestrate <goal>` | Start an orchestrated job |
| `/orchestrator status` | List active jobs |
| `/orchestrator status <job-id>` | One job's task graph |
| `/reload-skills` | Re-scan skill files after editing |
| `/profiles` | List configured worker profiles |
| `/<skill-name>` | Load any skill into the session |
| `/new` or `/reset` | Start a fresh conversation |
| `/model [provider:model]` | Switch model mid-conversation |

## Conventions to follow

1. **Edit before write.** Prefer `Edit` on an existing file over
   creating a new one. The repo has a lot of files; before adding
   one, check if the change belongs in an existing module.
2. **Tests live next to the code they cover.** Mirror the directory
   layout under `tests/`. Don't add a test file at the repo root.
3. **Skills are Markdown playbooks, not Python.** New skills go
   under `skills/<category>/<skill-name>/SKILL.md`. They are
   data, not code; treat them like prompts.
4. **Plugins ship as folders under `plugins/`.** Each plugin has a
   `plugin.yaml`, an `__init__.py`, and whatever modules implement
   its tools. See `plugins/github_assistant/` for the smallest
   end-to-end example.
5. **No secrets in code.** API keys live in `~/.hermes/.env`. The
   plugin layer reads them; the agent never sees them.

## Cross-references

- [`AGENTS.md`](AGENTS.md) — full dev guide (do read).
- [`README.md`](README.md) — user-facing intro.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — PR process.
- [`SECURITY.md`](SECURITY.md) — reporting vulnerabilities.
- [`docs/README.md`](docs/README.md) — plain-English operating
  manual index. Points to every user-facing guide below.
- [`docs/orchestration/`](docs/orchestration/) — orchestration
  end-to-end. Start with `getting-started.md` and the Prompt to PR
  demo (`prompt-to-pr-demo.md`).
- [`docs/mobile/mobile-app-guide.md`](docs/mobile/mobile-app-guide.md)
  — the Android cockpit, phone-first setup, approvals on the
  lockscreen.
- [`docs/voice/voice-first-user-guide.md`](docs/voice/voice-first-user-guide.md)
  — voice-first capture, driving mode, STT/TTS choices.
- [`docs/remote/windows-claude-code-bridge-guide.md`](docs/remote/windows-claude-code-bridge-guide.md)
  — the Claude Code Windows bridge.
- [`docs/profile/github-history-profile-guide.md`](docs/profile/github-history-profile-guide.md)
  — what the user profile stores and how Hermes learns from past
  jobs.
- [`docs/security/private-local-security-guide.md`](docs/security/private-local-security-guide.md)
  — secrets, approvals, private-local recipes.
- [`docs/integrations/github-supabase-vercel-guide.md`](docs/integrations/github-supabase-vercel-guide.md)
  — wiring up GitHub, Supabase, and Vercel.
- [`docs/troubleshooting/hermes-orchestration-troubleshooting.md`](docs/troubleshooting/hermes-orchestration-troubleshooting.md)
  — symptom-to-fix table across every surface.
- [`docs/github-integration.md`](docs/github-integration.md) — the
  native `github_assistant` plugin vs the GitHub MCP server.
- [`docs/integrations/sia-self-improvement.md`](docs/integrations/sia-self-improvement.md)
  — the owner-gated SIA (Hexo Labs) self-improvement worker: SIA
  iterates in a sandbox, JARVIS promotes the winner only by proposal.
- [`docs/ai-intelligence/jarvis-learning-dataset.md`](docs/ai-intelligence/jarvis-learning-dataset.md)
  — the JARVIS learning dataset pipeline: validated, source-backed,
  owner-approved traces for fine-tuning / preference / eval, with no
  secrets or chain-of-thought. CLI (`hermes_cli.jarvis_prime learning`),
  cockpit (`/v1/cockpit/learning`), and the Android Learning Queue tab.
- [`docs/hermes-local-orchestrator.md`](docs/hermes-local-orchestrator.md)
  — the Android-only handoff flow that predates the orchestration
  stack (still relevant for the "just hand off to ChatGPT/Codex via
  clipboard" workflow).
- [`apps/android/README.md`](apps/android/README.md) — the cockpit's
  own README.

## How to ask for help

If you're stuck, check in this order:

1. [`docs/orchestration/troubleshooting.md`](docs/orchestration/troubleshooting.md)
   — for orchestration-specific failures.
2. `hermes doctor` — for environment / install issues.
3. `hermes orchestrator status` plus
   `~/.hermes/jobs/<job-id>/ledger.jsonl` — for runtime issues.
4. GitHub issues with a tar of the job folder and `hermes doctor`
   output attached.

Welcome aboard.

## AOS Enterprise Council pack (installed 2026-05-24)

A complete autonomous-enterprise smart team is available as a Hermes
skill at `skills/aos-enterprise-council/`. When the user asks for
"audit repo", "build the app", "enterprise hardening", "launch
readiness", "improve the product", "use the AOS team", "activate the
council", "psychology audit", "Claude/Codex orchestration", "HazMat
Command review", or "Nourish review", load that skill first.

The pack contains 233 registered top-level agents + 108 sub-agents,
grouped into 18 category folders under `agents/`. The 5 registry
files in `skills/aos-enterprise-council/registry/` are the source of
truth — never improvise a council member that isn't in the registry.

The full recovery narrative + Termux install commands live at the
repo root: `AOS_AGENT_RECOVERY_REPORT.md` and `AOS_INSTALLATION_REPORT.md`.
