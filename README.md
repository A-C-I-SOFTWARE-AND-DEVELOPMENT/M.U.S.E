<p align="center">
  <img src="assets/banner.png" alt="muse" width="100%">
</p>

# muse — Multi-Use Synaptic Entity ◉

<p align="center">
  <a href="https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/Lang-中文-red?style=for-the-badge" alt="中文"></a>
</p>

> **📣 Latest release — [v1.2.0 · LM Studio native v1 REST API](docs/launch/RELEASE_NOTES_v1.2.0.md).** Accurate context-window detection for local **and** remote LM Studio, model lifecycle (load / unload / download) with agent tools, and auto-unload on model switch. ([all releases](docs/releases/README.md))

**One mind, many pathways.** muse is a self-improving, local-first AI operating partner: a single identity — the *mind* — running over a **synaptic substrate** (its gateway, routing, and model pathways). It creates skills from experience, improves them during use, remembers across sessions, builds a deepening model of who you are, and defers owner-gated actions until you authorize them. Run it on a $5 VPS, a GPU cluster, or serverless infrastructure that costs nearly nothing when idle — and talk to it from Telegram while it works on a cloud VM.

> **▶ Try it live — [musehq.io](https://musehq.io).** Chat with every model from one page: no sign-in, no setup. muse fuses every provider into a single resilient chat that never stops, routes each turn to the best model, and keeps every real-world action owner-gated.

Use any model you want — [OpenRouter](https://openrouter.ai) (200+ models), [NovitaAI](https://novita.ai), [NVIDIA NIM](https://build.nvidia.com), [z.ai/GLM](https://z.ai), [Kimi/Moonshot](https://platform.moonshot.ai), [MiniMax](https://www.minimax.io), [Hugging Face](https://huggingface.co), OpenAI, or your own endpoint. Switch with `muse model` — no code changes, no lock-in.

<table>
<tr><td><b>A real terminal interface</b></td><td>Full TUI with multiline editing, slash-command autocomplete, conversation history, interrupt-and-redirect, and streaming tool output.</td></tr>
<tr><td><b>Lives where you do</b></td><td>Telegram, Discord, Slack, WhatsApp, Signal, and CLI — all from a single gateway process. Voice memo transcription, cross-platform conversation continuity.</td></tr>
<tr><td><b>A closed learning loop</b></td><td>Agent-curated memory with periodic nudges. Autonomous skill creation after complex tasks. Skills self-improve during use. FTS5 session search with LLM summarization for cross-session recall. <a href="https://github.com/plastic-labs/honcho">Honcho</a> dialectic user modeling. Compatible with the <a href="https://agentskills.io">agentskills.io</a> open standard.</td></tr>
<tr><td><b>Scheduled automations</b></td><td>Built-in cron scheduler with delivery to any platform. Daily reports, nightly backups, weekly audits — all in natural language, running unattended.</td></tr>
<tr><td><b>Delegates and parallelizes</b></td><td>Spawn isolated subagents for parallel workstreams. Write Python scripts that call tools via RPC, collapsing multi-step pipelines into zero-context-cost turns.</td></tr>
<tr><td><b>Runs anywhere, not just your laptop</b></td><td>Seven terminal backends — local, Docker, SSH, Singularity, Modal, Daytona, and Vercel Sandbox. Daytona and Modal offer serverless persistence — your agent's environment hibernates when idle and wakes on demand, costing nearly nothing between sessions. Run it on a $5 VPS or a GPU cluster.</td></tr>
<tr><td><b>Research-ready</b></td><td>Batch trajectory generation, trajectory compression for training the next generation of tool-calling models.</td></tr>
<tr><td><b>A full operating layer, not just a chatbot</b></td><td>muse ships as a runtime (<code>hermes_cli/jarvis_prime/</code>): six modes (Companion, Strategy, Critic, Operator, Builder, Mobile Voice), an intent/mode classifier, runtime persona injection, eight verification gates, owner-authorization, and an emergency stop. Invoke with <code>/jarvis</code>.</td></tr>
<tr><td><b>Goal-to-PR orchestration</b></td><td>Decomposes one goal into a validated task graph — Job → specialist Worker → per-task Model routing → Validation gate → tamper-evident Decision ledger. Drive it with <code>/orchestrate</code> from the TUI, a gateway DM, or the Android cockpit.</td></tr>
<tr><td><b>An inspectable knowledge graph</b></td><td>GraphRAG unifies repo code, docs, Research Vault, Memory Tree, and ledgers into one typed, source-backed graph (measured 33,483 nodes over the repo as of 2026-06-10; see the attestation in the GraphRAG doc) with local, global, and coding query modes — so work reuses what already exists instead of rebuilding it.</td></tr>
<tr><td><b>An autonomous-enterprise council</b></td><td>The AOS Enterprise Council — a routed catalog of 233 registered agent roles + 108 sub-agent entries (registry tallies, not 341 standalone files) spanning architecture, security, compliance, QA, release, product, psychology, HazMat Command, and more — convened for audits, launch readiness, and multi-perspective review.</td></tr>
<tr><td><b>A native Android cockpit</b></td><td>Kotlin + Compose app (<code>apps/android/</code>) that pairs with the muse gateway: streaming chat, on-device voice intake, job control, lockscreen-style owner approvals, evidence/memory/graph views, and an emergency stop. No provider keys on the phone.</td></tr>
</table>

---

## What muse is

muse is a governed, local-first AI operating partner: **one mind over a synaptic substrate.** Everything below is real, tested code in this repository, not a roadmap. (Heritage + credits in small print at the very bottom.)

- **muse operating layer** — a runtime in [`hermes_cli/jarvis_prime/`](hermes_cli/jarvis_prime/) (~100 modules): six modes, an intent/mode classifier, runtime persona injection, owner-authorization with exact-phrase grants, an emergency stop, and read-only monitors with a daily owner brief. See [`docs/jarvis-prime-operating-system.md`](docs/jarvis-prime-operating-system.md).
- **Provenance-first cognition plane** — a Memory Tree (working/session/durable memory with source citations, confidence floors, contradiction reports, supersession, and no silent overwrites), a Research Vault, an evidence engine (BM25 + memory hybrid retrieval with citation verification), and TokenJuice — a deterministic, token-bounded context compiler that screens secrets.
- **GraphRAG knowledge graph** — [`hermes_cli/jarvis_prime/graphrag/`](hermes_cli/jarvis_prime/graphrag/) unifies code, docs, Research Vault, Memory Tree, and ledgers into one typed, source-backed graph (measured 33,483 nodes / ~63.3k edges over the repo as of 2026-06-10 — attestation in the GraphRAG doc) with local/global/coding queries. See [`docs/jarvis_architecture/GRAPHRAG_KNOWLEDGE_GRAPH.md`](docs/jarvis_architecture/GRAPHRAG_KNOWLEDGE_GRAPH.md).
- **Goal-to-PR orchestration** — five primitives (Job, Worker, Model routing, Validation gate, Decision ledger) decompose a goal into a validated task graph and publish the result, auditing every decision in a tamper-evident ledger. See [`docs/orchestration/`](docs/orchestration/).
- **AOS Enterprise Council** — a routed catalog of 233 registered agent roles + 108 sub-agent entries (registry tallies, not 341 standalone files; ~84 council agent files plus the general `agents/hermes/` skill library) for audits, hardening, launch readiness, and multi-perspective review. See [`skills/aos-enterprise-council/`](skills/aos-enterprise-council/).
- **Eight verification gates + verifiable guardrails** — Planning, Build, Review, Test, Security, Release, Owner Approval, and Rollback — backed by a hash-chained, tamper-evident evidence ledger (`verify_chain()`). See [`docs/jarvis-verification-gates.md`](docs/jarvis-verification-gates.md).
- **A versioned Constitution + self-audit layer** — an append-only behavioral rubric (clauses `C1…Cn`, severity-rated) the agent is scored against, plus reward-hacking / Goodhart detection and a capability-band wall. See [`docs/jarvis-constitution.md`](docs/jarvis-constitution.md).
- **Owner control by construction** — owner-gated actions (spend, deploy, publish, OAuth, credential change, package publish, regulated claims) defer until you reply exactly `Yes, with authorization.`; a workspace-scoped high-autonomy coding mode auto-approves only local friction and never weakens those gates; and every self-update is a reviewable proposal, never a silent rewrite.
- **Free-first model routing + a closed learning loop** — routes local OSS → hosted-free → official Claude Code / Codex worker lanes → paid (opt-in only), choosing per task class from measured scorecards; an owner-approved pipeline (SFT → ORPO/DPO → GRPO) promotes a model only when it beats the incumbent on a held-out benchmark wall. See [`docs/ai-intelligence/`](docs/ai-intelligence/).
- **Native Android cockpit + voice-first** — a Kotlin/Compose app ([`apps/android/`](apps/android/)) pairing to the cockpit gateway: streaming chat, on-device voice intake, job control, owner approvals, evidence/memory/graph views, autonomy controls, and an emergency stop — with a clipboard-handoff fallback when unpaired. Provider keys never leave the gateway.
- **Runs where you are** — native Windows support ([`scripts/install.ps1`](scripts/install.ps1), a scheduled-task service with a locked-down fallback, portable Git, no admin) alongside the Linux/macOS/WSL2 and Termux paths.

---

## muse Operating Layer

> **Status — runtime shipped (v1.0.0).** The operating contract, mode taxonomy, routing rules, and skill descriptions for muse live as `docs/jarvis-*.md` and `skills/jarvis-*`. The runtime (mode classifier, personality injection, verification-gate enforcement, owner-authorization mechanism, emergency stop, memory CLI) ships in `hermes_cli/jarvis_prime/` and is activated from the interactive `muse` CLI via `/jarvis`, `/jp`, or `/jarvis-prime`. See [`docs/launch/RELEASE_NOTES_v1.0.0.md`](docs/launch/RELEASE_NOTES_v1.0.0.md) for the full launch notes.

muse is a governed, local-first AI operating layer for users who want an active command center rather than a passive chatbot — a single identity (the *mind*) over a synaptic substrate (muse the gateway, routing, and model pathways) that coordinates conversation, tools, memory, local verification, and platform surfaces while preserving owner control.

The operating model is intentionally small and reviewable:

- **Hermes** is the command center and execution shell.
- **AOS** is the reasoning council for multi-perspective judgment.
- **Claude Code** is the primary builder for implementation work.
- **Codex** is the reviewer, bounded fix worker, or second-pass engineer.
- **Slack and Termux** are mobile command surfaces for Android-first workflows.
- **Mobile voice capture** supports jogging, walking, driving breaks, and away-from-desk idea capture.
- **Focused mode** handles long technical review, build planning, local verification, and PR handoff.

muse is loyal to the user's long-term mission, not blindly obedient to the moment. It should challenge weak ideas, route code work through builder/reviewer workflows, and defer risky actions such as merges, deploys, public posting, credential changes, and publishing until explicit owner approval.

Invoke from any gateway DM or REPL with `/jarvis-prime` (alias `/jarvis`, `/jp`), or pin a specific mode with `/companion`, `/strategy`, `/critic`, `/operator`, `/builder`, `/voice`. See [`docs/jarvis-prime-operating-system.md`](docs/jarvis-prime-operating-system.md) for the full identity, hierarchy, modes, and gates.

### Cognition plane — Memory OS, packetizer, research, routing, monitors

muse ships a provenance-first cognition plane (all stdlib-only,
local, no network) — see [`docs/jarvis_architecture/JARVIS_SYSTEM_OVERVIEW.md`](docs/jarvis_architecture/JARVIS_SYSTEM_OVERVIEW.md):

- **Memory Tree** (`memory_tree.py`) — working/session/durable memory with
  source provenance, confidence floors, sensitivity, approval, contradiction
  reports + supersession (no silent overwrite), ranked retrieval, and
  token-bounded context packs. Memory **cites sources**; it is not the source
  of truth.
- **Natural-language coder** (`natural_language_coder.py`) — turns plain
  English into a bounded, gate-compatible work packet (intent, risk class,
  owner gates, allowed/forbidden files, verification, rollback). It never
  executes; bypass/exfiltration requests are blocked.
- **Research Vault** (`research_vault.py`) — source-cited evidence; vendor
  benchmarks recorded as vendor-reported.
- **TokenJuice** (`tokenjuice.py`) — deterministic, token-bounded context
  compiler that carries provenance and screens secrets.
- **Model scorecards** (`model_scorecard.py`) — evidence-backed routing;
  local OSS models are "wired" via config/local-endpoint packets, **not**
  claimed running without a smoke request.
- **Proposal executor** (`proposal_executor.py`) — approved self-update
  proposals → bounded plans; never merges/deploys/publishes.
- **Monitors + daily owner brief** (`monitors.py`, `owner_brief.py`) —
  read-only, fail-visible monitors with a coverage attestation that surfaces
  blind spots.

These are **local OSS-capable, owner-gated, and reversible** — muse is
loyal and verification-first, not "fully autonomous." New CLI lanes:
`packetize`, `packet --gate-check/--validate/--markdown`, `memory-tree
{add,search,outline,export-markdown} --store`, `research`, `model-scorecard`,
`owner-brief`.

---

## Quick Install

### Linux, macOS, WSL2, Termux

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/main/scripts/install.sh)
```

### One-click muse launch (free-first)

Add `--jarvis-launch` to install **and** bring up muse in one
command — free / open-source model routes first, paid APIs explicit
opt-in only, Claude Code and Codex wired as official worker lanes:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/main/scripts/install.sh) --jarvis-launch
```

Already installed? Bring muse up (or re-verify) with:

```bash
muse jarvis launch                            # full free-first launch path
muse models bootstrap --free-first --jarvis   # (re)configure model routing only
muse doctor --jarvis-launch                   # verify launch readiness
```

Then invoke muse with `/jarvis` (aliases `/jp`, `/jarvis-prime`) and stop
it instantly with `/jarvis stop`. A missing local model runtime (Ollama,
etc.) is a warning, not a blocker. Full guide:
[`docs/jarvis-free-first-launch.md`](docs/jarvis-free-first-launch.md).

### Windows (native, PowerShell) — Early Beta

> **Heads up:** Native Windows support is **early beta**. It installs and runs, but hasn't been road-tested as broadly as our Linux/macOS/WSL2 paths. Please [file issues](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/issues) when you hit rough edges. For the most battle-tested Windows setup today, run the Linux/macOS one-liner above inside **WSL2**.

Run this in PowerShell:

```powershell
iex (irm https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/main/scripts/install.ps1)
```

For the one-click muse launch on Windows, download and run with the
`-JarvisLaunch` switch (parity with `--jarvis-launch`):

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/main/scripts/install.ps1))) -JarvisLaunch
```

The installer handles everything: uv, Python 3.11, Node.js, ripgrep, ffmpeg, **and a portable Git Bash** (MinGit, unpacked to `%LOCALAPPDATA%\hermes\git` — no admin required, completely isolated from any system Git install).  muse uses this bundled Git Bash to run shell commands.

If you already have Git installed, the installer detects it and uses that instead.  Otherwise a ~45MB MinGit download is all you need — it won't touch or interfere with any system Git.

> **Android / Termux:** The tested manual path is documented in the [Termux guide](https://hermes-agent.nousresearch.com/docs/getting-started/termux). On Termux, muse installs a curated `.[termux]` extra because the full `.[all]` extra currently pulls Android-incompatible voice dependencies. **A native Android companion app** (Kotlin + Compose) lives at [`apps/android`](apps/android/) — see [Android Native App](#android-native-app) below.
>
> **Windows:** Native Windows is supported as an **early beta** — the PowerShell one-liner above installs everything, but expect rough edges and please file issues when you hit them. If you'd rather use WSL2 (our most battle-tested Windows path), the Linux command works there too. Native Windows install lives under `%LOCALAPPDATA%\hermes`; WSL2 installs under `~/.hermes` as on Linux.  The only muse feature that currently needs WSL2 specifically is the browser-based dashboard chat pane (it uses a POSIX PTY — classic CLI and gateway both run natively).

After installation:

```bash
source ~/.bashrc    # reload shell (or: source ~/.zshrc)
muse                # start chatting!
```

---

## Getting Started

```bash
muse                # Interactive CLI — start a conversation
muse model          # Choose your LLM provider and model
muse tools          # Configure which tools are enabled
muse config set     # Set individual config values
muse gateway        # Start the messaging gateway (Telegram, Discord, etc.)
muse setup          # Run the full setup wizard (configures everything at once)
muse claw migrate   # Migrate from OpenClaw (if coming from OpenClaw)
muse update         # Update to the latest version (on a fork: autonomously consolidates upstream/main + your branch into main and pushes)
muse doctor         # Diagnose any issues
```

📖 **[Full documentation →](https://hermes-agent.nousresearch.com/docs/)**

## muse Orchestration

Turn a sentence into a graph of validated, auditable jobs run by
specialist workers. The orchestrator decomposes the goal, the kanban
dispatcher fans it out, every step goes through a validation gate,
every decision lands in a tamper-evident ledger, and the result
publishes to wherever you asked (PR, Telegram, file, Android
cockpit).

```bash
bash scripts/hermes-orchestrate.sh "Audit this repo"      # one-shot, scriptable
muse                                                      # interactive
/reload-skills                                            # after editing skills
/orchestrate Build this repo into production quality      # from inside a session
/orchestrator status                                      # see what's running
```

Same brain on every surface — CLI, gateway DM (Telegram / Discord /
Slack / WhatsApp / Signal), Android cockpit, Termux shell. Works
fully offline against a local llama.cpp / vLLM / Ollama server.

**📖 Full guide:** [docs/orchestration/](docs/orchestration/) —
overview, getting started, Prompt to PR demo, Android + Termux
demo, worker adapters, private-local mode, troubleshooting, FAQ.

## Plain-English operating manual

The [`docs/`](docs/) folder is the human-readable manual that
explains every muse surface in plain English. Start with
[`docs/README.md`](docs/README.md) — it's a single-page map that
points to one guide per topic:

| Want to… | Read |
|---|---|
| Run your first job | [docs/orchestration/getting-started.md](docs/orchestration/getting-started.md) |
| See end-to-end Prompt to PR | [docs/orchestration/prompt-to-pr-demo.md](docs/orchestration/prompt-to-pr-demo.md) |
| Drive muse from a phone | [docs/mobile/mobile-app-guide.md](docs/mobile/mobile-app-guide.md) |
| Use voice-first (driving mode) | [docs/voice/voice-first-user-guide.md](docs/voice/voice-first-user-guide.md) |
| Bridge to Claude Code Windows | [docs/remote/windows-claude-code-bridge-guide.md](docs/remote/windows-claude-code-bridge-guide.md) |
| Profile your GitHub history | [docs/profile/github-history-profile-guide.md](docs/profile/github-history-profile-guide.md) |
| Lock down private-local | [docs/security/private-local-security-guide.md](docs/security/private-local-security-guide.md) |
| Wire GitHub / Supabase / Vercel | [docs/integrations/github-supabase-vercel-guide.md](docs/integrations/github-supabase-vercel-guide.md) |
| Verify history with the AXIOM bridge | [docs/axiom-integration.md](docs/axiom-integration.md) |
| Fix something broken | [docs/troubleshooting/hermes-orchestration-troubleshooting.md](docs/troubleshooting/hermes-orchestration-troubleshooting.md) |

## CLI vs Messaging Quick Reference

muse has two entry points: start the terminal UI with `muse`, or run the gateway and talk to it from Telegram, Discord, Slack, WhatsApp, Signal, or Email. Once you're in a conversation, many slash commands are shared across both interfaces.

| Action | CLI | Messaging platforms |
|---------|-----|---------------------|
| Start chatting | `muse` | Run `muse gateway setup` + `muse gateway start`, then send the bot a message |
| Start fresh conversation | `/new` or `/reset` | `/new` or `/reset` |
| Change model | `/model [provider:model]` | `/model [provider:model]` |
| Set a personality | `/personality [name]` | `/personality [name]` |
| Retry or undo the last turn | `/retry`, `/undo` | `/retry`, `/undo` |
| Compress context / check usage | `/compress`, `/usage`, `/insights [--days N]` | `/compress`, `/usage`, `/insights [days]` |
| Browse skills | `/skills` or `/<skill-name>` | `/<skill-name>` |
| Interrupt current work | `Ctrl+C` or send a new message | `/stop` or send a new message |
| Platform-specific status | `/platforms` | `/status`, `/sethome` |

For the full command lists, see the [CLI guide](https://hermes-agent.nousresearch.com/docs/user-guide/cli) and the [Messaging Gateway guide](https://hermes-agent.nousresearch.com/docs/user-guide/messaging).

---

## Documentation

All documentation lives at **[hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/)**:

| Section | What's Covered |
|---------|---------------|
| [Quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart) | Install → setup → first conversation in 2 minutes |
| [CLI Usage](https://hermes-agent.nousresearch.com/docs/user-guide/cli) | Commands, keybindings, personalities, sessions |
| [Configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) | Config file, providers, models, all options |
| [Messaging Gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging) | Telegram, Discord, Slack, WhatsApp, Signal, Home Assistant |
| [Security](https://hermes-agent.nousresearch.com/docs/user-guide/security) | Command approval, DM pairing, container isolation |
| [Tools & Toolsets](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools) | 40+ tools, toolset system, terminal backends |
| [Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) | Procedural memory, Skills Hub, creating skills |
| [Memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory) | Persistent memory, user profiles, best practices |
| [MCP Integration](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp) | Connect any MCP server for extended capabilities |
| [Cron Scheduling](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron) | Scheduled tasks with platform delivery |
| [Context Files](https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files) | Project context that shapes every conversation |
| [Architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture) | Project structure, agent loop, key classes |
| [Contributing](https://hermes-agent.nousresearch.com/docs/developer-guide/contributing) | Development setup, PR process, code style |
| [CLI Reference](https://hermes-agent.nousresearch.com/docs/reference/cli-commands) | All commands and flags |
| [Environment Variables](https://hermes-agent.nousresearch.com/docs/reference/environment-variables) | Complete env var reference |

---

## Android Native App

A native Android companion app lives at [`apps/android`](apps/android/) — Kotlin + Jetpack Compose, Material 3, MVVM. It is a **thin client** over a running muse backend (CLI/gateway), not a wrapped webview and not a port of the desktop terminal UX.

**Three runtime modes:**

1. **Remote gateway** — point the app at a muse install on your VPS / home server. Recommended.
2. **Local Termux gateway** — `muse gateway start` inside Termux on the same device, app points at `http://127.0.0.1:8080`.
3. **Mock mode** — UI sandbox with canned responses, no backend required (great for trying the UI before committing to a setup).

**Build the debug APK:**

```bash
cd apps/android
./gradlew assembleDebug
# APK at: apps/android/app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

**Release AAB for Google Play:** see [`apps/android/README.md`](apps/android/README.md#release-aab-for-google-play). CI builds the debug APK on every change via [`.github/workflows/android-build.yml`](.github/workflows/android-build.yml).

Architecture, wire format, and the deliberate "no embedded Python" decision are documented in [`apps/android/docs/ARCHITECTURE.md`](apps/android/docs/ARCHITECTURE.md).

---

## muse Orchestration Pipeline

muse can be used as a private local-first developer command center. The
muse backend is the engine; the Android APK is the cockpit. Everything
runs on devices you own — VPS, home server, laptop, or Termux on
phone — and the Android cockpit talks to it over a gateway you control.

The pipeline ties together:

- **Agent skills** — composable procedures the agent calls at runtime.
- **Decision ledger** — every non-trivial decision is recorded with
  rationale, alternatives, and outcome so future runs can learn from it.
- **Model router** — picks the right model for the job (planner,
  builder, reviewer, summarizer) from the model registry.
- **AI improvement radar** — a continuous scan of new AI capabilities,
  models, and tools that muse should adopt.
- **Competitive feature harvester** — tracks shipping features from
  comparable tools and feeds them into the improvement radar.
- **Self-improvement loop** — muse proposes patches to its own
  skills, ledger, and routing policy, gated by the decision quality gate.
- **GitHub publisher** — turns approved changes into branches, PRs,
  and releases without leaving the cockpit.

Invocation (from the CLI or any messaging gateway):

```text
/reload-skills
/aos-full-agent-team <goal>
/hermes-orchestration-pipeline <job-id>
/model-router <task-type>
/decision-quality-gate <decision-id>
/ai-improvement-radar
/github-publisher <branch>
```

Posture is **private and local-first** by default — no telemetry,
no remote config, no third-party data sharing beyond the official AI
tools the user is already logged into. See
[`docs/hermes-local-orchestrator.md`](docs/hermes-local-orchestrator.md)
for the Android cockpit contract.

---

## Migrating from OpenClaw

If you're coming from OpenClaw, muse can automatically import your settings, memories, skills, and API keys.

**During first-time setup:** The setup wizard (`muse setup`) automatically detects `~/.openclaw` and offers to migrate before configuration begins.

**Anytime after install:**

```bash
muse claw migrate              # Interactive migration (full preset)
muse claw migrate --dry-run    # Preview what would be migrated
muse claw migrate --preset user-data   # Migrate without secrets
muse claw migrate --overwrite  # Overwrite existing conflicts
```

What gets imported:
- **SOUL.md** — persona file
- **Memories** — MEMORY.md and USER.md entries
- **Skills** — user-created skills → `~/.hermes/skills/openclaw-imports/`
- **Command allowlist** — approval patterns
- **Messaging settings** — platform configs, allowed users, working directory
- **API keys** — allowlisted secrets (Telegram, OpenRouter, OpenAI, Anthropic, ElevenLabs)
- **TTS assets** — workspace audio files
- **Workspace instructions** — AGENTS.md (with `--workspace-target`)

See `muse claw migrate --help` for all options, or use the `openclaw-migration` skill for an interactive agent-guided migration with dry-run previews.

---

## Contributing

We welcome contributions! See the [Contributing Guide](https://hermes-agent.nousresearch.com/docs/developer-guide/contributing) for development setup, code style, and PR process.

Quick start for contributors — clone and go with `setup-hermes.sh`:

```bash
git clone https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E
cd M.U.S.E
./setup-hermes.sh     # installs uv, creates venv, installs .[all], symlinks ~/.local/bin/muse
./hermes              # auto-detects the venv, no need to `source` first
```

Manual path (equivalent to the above):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

---

## Community

- 💬 [Discord](https://discord.gg/NousResearch)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/issues)
- 🔌 [computer-use-linux](https://github.com/avifenesh/computer-use-linux) — Linux desktop-control MCP server for muse and other MCP hosts, with AT-SPI accessibility trees, Wayland/X11 input, screenshots, and compositor window targeting.
- 🔌 [HermesClaw](https://github.com/AaronWong1999/hermesclaw) — Community WeChat bridge: Run muse and OpenClaw on the same WeChat account.

---

## License

MIT — see [LICENSE](LICENSE).

<sub>
<b>Heritage &amp; credits — with gratitude.</b> muse stands on the shoulders of open work. It grows from the Hermes agent base by <a href="https://nousresearch.com">Nous Research</a> (MIT) and is developed and maintained by <a href="https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT">A-C-I Software and Development</a>. Local-first voice/embodiment concepts are inspired by <a href="https://github.com/tinyhumansai/openhuman">OpenHuman</a> (concept only — no code copied). Capability comes from the open-weight model communities — DeepSeek, Z.ai/GLM, Moonshot/Kimi, MiniMax, Alibaba/Qwen, Google/Gemma, Mistral, BAAI and others — and the benchmark/leaderboard maintainers cited in <code>docs/ai-intelligence/</code>. Thank you. Full acknowledgements: <a href="CREDITS.md">CREDITS.md</a>.
</sub>
