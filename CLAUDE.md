# CLAUDE.md

Guidance for Claude Code (and other AI coding assistants) working in
the hermes-agent repository.

> **Authoritative source:** [`AGENTS.md`](AGENTS.md) is the primary
> development guide. This file is a Claude-specific entry point that
> points there. When the two disagree, AGENTS.md wins.

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
