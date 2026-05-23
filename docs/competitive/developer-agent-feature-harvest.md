# Developer-Agent Competitive Feature Harvest

Master table of verified features across competing AI agents, mapped to Hermes.
Maintained by the `competitive-feature-harvester` skill.
Last verified: 2026-05-23.

**Read this first.** Every row links to a primary source (official repo, docs, release notes, or first-party blog). Third-party reviews are not citable. If a row's confidence is `unverified`, it is informational only and **must not** drive implementation. See `skills/competitive-feature-harvester/SKILL.md` for the methodology and confidence ladder.

Hermes-side cross-checks were made against `README.md`, `skills/`, `plugins/`, `cli.py`, `gateway/`, `cron/`, and `mcp_serve.py` as of branch `claude/competitive-feature-harvest-ngFbb`.

---

## Master feature table

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| OpenHuman | Local-first Memory Tree (SQLite + Obsidian vault) | [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | Privacy + reuses existing note workflow | Partial: Hermes has persistent memory but no Obsidian-vault export | `hermes_state.py`, new `plugins/obsidian_vault` | high |
| OpenHuman | 118+ one-click OAuth connectors with auto-fetch every ~20 min | [openhuman.dev](https://www.openhuman.dev/) | "Tomorrow's context this morning" — no manual sync | Yes | `gateway/` connectors + `cron/` poller; consider Composio-style adapter under `plugins/` | high |
| OpenHuman | TokenJuice context compression (≤3k-token chunks, summary tree) | [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | Lower cost, longer effective context | Partial: Hermes has `trajectory_compressor.py` but no hierarchical summary tree | extend `trajectory_compressor.py` | high |
| OpenHuman | Model routing across reasoning/fast/vision profiles | [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | Right model per turn without manual switching | Partial: Hermes has `/model` and `model_tools.py` but no per-task routing | `model_tools.py`, new policy in `agent/` | high |
| OpenHuman | Optional local models via Ollama | [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | Offline / private inference | Yes, already supported via OpenAI-compatible endpoints | `providers/` | high |
| OpenHuman | Native voice in / voice out (STT + TTS) | [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | Hands-free use | Partial: Hermes does voice memo transcription on gateway, no first-class TTS reply | `gateway/` voice path, new `plugins/tts` | high |
| OpenHuman | Desktop UI shell, no terminal required | [openhuman.dev](https://www.openhuman.dev/) | Lower setup friction for non-CLI users | No (Hermes is intentionally TUI-first; web dashboard exists) | n/a — keep `ui-tui/` + `web/` as is | high |
| OpenHuman | Desktop mascot that joins Google Meets | [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | (no user testimony found) | No | n/a | medium |
| OpenHuman | "Memory scales to 1B tokens" | [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | (no user testimony found) | No (claim not architecturally explained) | n/a | low |
| Paperclip | Bring-Your-Own-Agent heartbeat protocol (Hermes is listed runtime) | [paperclip.ing](https://paperclip.ing/) | One control plane for many agents | Yes — integration, not feature parity | new `acp_adapter/paperclip.py` shim | high |
| Paperclip | Per-agent monthly budgets with hard stops | [paperclip.ing](https://paperclip.ing/) | Prevents runaway spend | Yes | new `hermes_state.py` budget table + enforcement in `run_agent.py` | high |
| Paperclip | Ticket system with immutable audit log of every tool call | [paperclip.ing](https://paperclip.ing/) | Auditability for shared deployments | Partial: trajectories exist but are not addressable as tickets | `hermes_state.py` ticket schema + CLI surface | high |
| Paperclip | Board approval workflows (hire/pause/terminate agents) | [paperclip.ing](https://paperclip.ing/) | Human-in-the-loop control for autonomous fleets | Partial: command approval exists per-tool, not per-agent | extend `agent/` approval system | high |
| Paperclip | Goal alignment — task→mission ancestry carried in every task | [paperclip.ing](https://paperclip.ing/) | Agents stay on-mission without re-prompting | No direct equivalent in Hermes | new `agent/goals.py` | high |
| Paperclip | Org chart with roles, titles, reporting lines | [paperclip.ing](https://paperclip.ing/) | Manage many agents like staff | No | new `enterprise/orgchart/` (parallel to existing `enterprise/`) | high |
| Paperclip | Recurring tasks via cron, webhook, API | [github.com/paperclipai/paperclip](https://github.com/paperclipai/paperclip) | No manual kick-offs | Yes, already shipped | existing `cron/` | high |
| Paperclip | Company portability — export/import org with secret scrubbing | [github.com/paperclipai/paperclip](https://github.com/paperclipai/paperclip) | Move deployments cleanly | Partial: Hermes config is portable, but no scrub/export bundle | `scripts/` export tool | high |
| Paperclip | Plugins as out-of-process workers with capability gating | [github.com/paperclipai/paperclip](https://github.com/paperclipai/paperclip) | Safe extension without forking | Partial: Hermes plugins exist (`plugins/`) but lack capability gating | extend `plugins/` loader | high |
| Paperclip | Multi-company tenancy in a single deployment | [github.com/paperclipai/paperclip](https://github.com/paperclipai/paperclip) | Shared infra for teams | Partial: Hermes is single-user by default | `enterprise/` tenancy layer | high |
| OpenHands | Saved LLM profiles + `/model` switcher mid-conversation | [openhands.dev May 2026 update](https://www.openhands.dev/blog/openhands-product-update---may-2026) | Less reconfiguration between tasks | Partial: Hermes has `/model` but no named profiles | extend `hermes_cli/` and `cli-config.yaml.example` | high |
| OpenHands | Sub-Agent Delegation via TaskToolSet | [openhands.dev May 2026 update](https://www.openhands.dev/blog/openhands-product-update---may-2026) | Cleaner context on multi-step jobs | Yes, already shipped (subagent toolset) | existing `toolsets.py` | high |
| OpenHands | Critic Result Display (inline verification UI) | [openhands.dev May 2026 update](https://www.openhands.dev/blog/openhands-product-update---may-2026) | Quality feedback where users already look | Partial: Hermes has self-critique paths but no inline UI surface | `ui-tui/` and `web/` | high |
| OpenHands | Sandbox grouping strategy exposed to all users | [openhands.dev May 2026 update](https://www.openhands.dev/blog/openhands-product-update---may-2026) | Predictable isolation | Yes, already shipped (terminal backends: local/Docker/SSH/Singularity/Modal/Daytona/Vercel Sandbox) | existing terminal backends | high |
| OpenHands | SDK that scales from laptop to "1000s of agents in the cloud" | [docs.openhands.dev](https://docs.openhands.dev/) | One mental model from dev to prod | Partial: Hermes has `batch_runner.py` but no formal cloud SDK | new `apps/sdk/` | high |
| Aider | Codebase repo map for large projects | [aider.chat](https://aider.chat/) | Better suggestions in big repos | Yes | new `agent/repo_map.py` (similar to Aider's) | high |
| Aider | Auto-commits with sensible messages | [aider.chat](https://aider.chat/) | Undo via `git diff`, low fear of agent edits | Partial: Hermes commits when asked, not by default | `tools/` git wrapper | high |
| Aider | Voice-to-code | [aider.chat](https://aider.chat/) | Hands-free authoring | Yes (transcription) | extend `gateway/` voice path | high |
| Aider | Image and webpage attachments in chat | [aider.chat](https://aider.chat/) | Visual context (screenshots, design refs) | Yes, already shipped | existing `tools/` | high |
| Aider | Auto-lint and auto-test after every change | [aider.chat](https://aider.chat/) | Catches regressions immediately | Partial: Hermes runs tools when asked | new post-edit hook in `agent/` |  high |
| Aider | Browser-based version (`--browser`) | [aider.chat](https://aider.chat/) | Web UI without separate app | Yes, already shipped (browser dashboard in `web/`) | existing `web/` | high |
| Continue | AI checks on every PR as markdown files in `.continue/checks/` | [docs.continue.dev](https://docs.continue.dev/) | Reviewable, version-controlled review policies | Yes — Hermes already has GitHub plugin | extend `plugins/github_assistant` with checks dir | high |
| Continue | Custom rules as repo-local markdown | [docs.continue.dev](https://docs.continue.dev/) | Team standards live with the code | Yes | reuse `skills/` + `optional-skills/` | high |
| Continue | Multi-IDE deployment (VS Code + JetBrains) | [continue.dev](https://www.continue.dev/) | Meets developers where they are | No (Hermes is TUI-first; explicit non-goal) | n/a | high |
| Goose | 70+ MCP extensions for databases, APIs, browsers, drives | [goose-docs.ai](https://goose-docs.ai/) | Plug in any external system | Yes, already shipped (Hermes is MCP-native, plugin marketplace) | existing `mcp_serve.py` + `plugins/` | high |
| Goose | Recipes — portable YAML automations sharable across teams/CI | [goose-docs.ai](https://goose-docs.ai/) | Reproducible agent workflows | Partial: Hermes has skills and cron, no single YAML recipe format | new `recipes/` directory + loader in `cli.py` | high |
| Goose | MCP Apps — interactive UIs rendered inside the desktop app | [goose-docs.ai](https://goose-docs.ai/) | Rich, app-specific UX | Partial: Hermes has dashboards but no MCP-server-rendered UI | extend `web/` + MCP UI protocol | high |
| Goose | Agent Client Protocol (ACP) for editor connectivity | [goose-docs.ai](https://goose-docs.ai/) | Works inside any ACP-aware editor | Yes, already shipped | existing `acp_adapter/` + `acp_registry/` | high |
| Goose | Apache-2.0 license under Linux Foundation Agentic AI Foundation | [block.xyz/inside](https://block.xyz/inside/block-open-source-introduces-codename-goose) | Neutral governance | No (Hermes is MIT under Nous Research) | n/a | high |
| Claude Code | Hooks (PreToolUse / PostToolUse) for deterministic policy | [code.claude.com docs](https://code.claude.com/docs/en/agent-sdk/slash-commands) | Policy that "cannot hallucinate" | Partial: Hermes has approval, not full hook lifecycle | new `agent/hooks.py` | high |
| Claude Code | Skills (`SKILL.md`) with frontmatter and helper files | [code.claude.com docs](https://code.claude.com/docs/en/agent-sdk/) | Reusable domain logic | Yes, already shipped (`skills/`) | existing `skills/` | high |
| Claude Code | Plugin bundles (skills + commands + hooks + MCP, versioned) | [code.claude.com docs](https://code.claude.com/docs/en/agent-sdk/) | One installable unit per capability | Partial: Hermes has `plugins/` but no version manifest format | extend `plugins/__init__.py` | high |
| Claude Code | Custom slash commands in `.claude/commands/` | [code.claude.com docs](https://code.claude.com/docs/en/agent-sdk/slash-commands) | Team-specific shortcuts | Yes, already shipped (slash commands + `/<skill-name>`) | existing `cli.py` | high |
| Codex | Approval modes: Auto / Read-only / Full Access | [developers.openai.com/codex/cli/features](https://developers.openai.com/codex/cli/features) | Predictable autonomy level | Partial: Hermes has command approval but not three named modes | extend `agent/` approval system | high |
| Codex | `/review` against branches or uncommitted changes | [developers.openai.com/codex/cli/features](https://developers.openai.com/codex/cli/features) | Local PR review without leaving terminal | Yes — adjacent to `plugins/github_assistant` | new `/review` command + `plugins/github_assistant` | high |
| Codex | Cloud task triage from terminal (launch / browse / apply diffs) | [developers.openai.com/codex/cli/features](https://developers.openai.com/codex/cli/features) | Long-running cloud work, fast local apply | Partial: Hermes has Modal/Daytona/Vercel Sandbox but no `cloud` triage subcommand | new `hermes cloud` command | high |
| Codex | Resumable conversations from stored transcripts | [developers.openai.com/codex/cli/features](https://developers.openai.com/codex/cli/features) | Don't lose context overnight | Yes, already shipped (session history, FTS5 search) | existing `hermes_state.py` | high |
| Codex | Image inputs (screenshots, design specs) | [developers.openai.com/codex/cli/features](https://developers.openai.com/codex/cli/features) | Visual context for UI work | Yes, already shipped | existing `tools/` | high |
| Codex | Shell completions (bash, zsh, fish) | [developers.openai.com/codex/cli/features](https://developers.openai.com/codex/cli/features) | Discoverability of commands | Partial: Hermes has CLI but no published completions | new `packaging/completions/` | high |
| OpenClaw | Multi-channel inbox (22+ platforms: WhatsApp, Telegram, iMessage, Slack, Discord, Signal, …) | [openclaw.ai](https://openclaw.ai/) | One agent reachable everywhere | Partial: Hermes ships Telegram, Discord, Slack, WhatsApp, Signal, Email | extend `gateway/` with iMessage / Matrix / Google Chat / Teams adapters | high |
| OpenClaw | Voice Wake + Talk Mode (wake words on macOS/iOS, continuous voice on Android) | [openclaw.ai](https://openclaw.ai/) | Always-on voice assistant feel | Partial: Hermes has voice memos, no wake word | new `apps/android` wake-word path | high |
| OpenClaw | Live Canvas — agent-driven visual workspace (A2UI) | [openclaw.ai](https://openclaw.ai/) | Visual collaboration with the agent | No direct equivalent | new `web/canvas/` | medium |
| OpenClaw | Skill registry via ClawHub with bundled / managed / workspace tiers | [openclaw.ai](https://openclaw.ai/) | Easy skill install + isolation | Partial: Hermes has skills and `agentskills.io` standard compat | extend `skills/` loader with tiered scopes | high |
| OpenClaw | `~/.openclaw/workspace/skills/<skill>/SKILL.md` layout | [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw) | Familiar layout for OpenClaw migrants | Yes, already shipped (`hermes claw migrate`) | existing `cli.py` migration | high |

---

## Recommended for Hermes

Only `high` / `medium` confidence rows that apply to Hermes, grouped by surface. Each entry references its row above for the source.

### Memory & context

- **Hierarchical summary tree** on top of `trajectory_compressor.py` so long histories collapse to per-topic / per-day summaries instead of one flat compressed buffer (OpenHuman).
- **Obsidian-compatible vault export** as a memory mirror, for users who want their notes editable outside Hermes (OpenHuman).

### Gateway & integrations

- **OAuth connector framework with periodic pull** — generalise the platform connectors so non-messaging sources (Gmail, Drive, Linear, Jira, Stripe, Notion) feed a memory inbox on a cron (OpenHuman).
- **Additional messaging adapters**: iMessage, Matrix, Google Chat, Microsoft Teams, Feishu (OpenClaw parity).
- **Wake-word voice mode** in the Android companion app at `apps/android/` (OpenClaw).

### Governance, budgets, audit

- **Per-agent monthly budget table** with hard-stop enforcement in `run_agent.py`. This is the largest opportunity — Hermes has no current budget surface (Paperclip).
- **Ticket model** layered over the existing trajectory store so every tool call is addressable, queryable, and exportable as an audit log (Paperclip).
- **Three named approval modes** (Auto / Read-only / Full Access) replacing ad-hoc per-tool prompts (Codex).
- **Capability-gated plugin loader** so plugins declare and are restricted to specific host capabilities (Paperclip + Claude Code plugin model).

### Orchestration

- **Heartbeat-protocol adapter** under `acp_adapter/paperclip.py` so Hermes registers as a Paperclip runtime (Paperclip lists Hermes already; integration is bidirectional).
- **Mission/goal ancestry** carried on every task so multi-step jobs trace back to a top-level objective (Paperclip).
- **Saved LLM profiles** addressable from `/model <profile>` (OpenHands).

### Developer ergonomics

- **Auto-commit-after-edit** mode (opt-in) with Aider-style commit messages (Aider).
- **Post-edit lint+test hook** that runs once per agent turn, surfacing failures back into context (Aider).
- **Repo map** generator for the software-development skills (Aider).
- **`/review` slash command** that diffs the current branch and runs the Codex-style review pass via the GitHub assistant plugin (Codex).
- **Cloud task triage** subcommand (`hermes cloud`) for the Modal / Daytona / Vercel Sandbox backends (Codex).
- **Recipes** as portable YAML files combining tools+skills+model+cron into one shareable artefact (Goose).
- **Shell completions** for bash/zsh/fish under `packaging/completions/` (Codex).

### Review automation

- **`.hermes/checks/` directory** of markdown-defined PR review prompts, posted as GitHub status checks by the GitHub assistant plugin (Continue).

---

## Explicitly out of scope for Hermes

These were verified as competitor features but should **not** be adopted, with reason:

- **Desktop mascot / Google Meet avatar** (OpenHuman) — not aligned with Hermes' TUI/messaging-first identity.
- **VS Code / JetBrains extensions** (Continue) — Hermes commits to terminal + messaging gateways; an ACP adapter already covers editor integration when needed.
- **Apache-2.0 / Linux Foundation governance** (Goose) — license/governance decisions are owned by Nous Research, not the harvester.
- **"Zero-human company" framing** (Paperclip) — positioning claim, not a feature.

---

## Master sources

OpenHuman:

- <https://github.com/tinyhumansai/openhuman>
- <https://www.openhuman.dev/>
- <https://tinyhumans.gitbook.io/openhuman>

Paperclip:

- <https://github.com/paperclipai/paperclip>
- <https://paperclip.ing/>

OpenHands:

- <https://docs.openhands.dev/>
- <https://www.openhands.dev/blog/openhands-product-update---may-2026>

Aider:

- <https://aider.chat/>
- <https://aider.chat/docs/>

Continue:

- <https://www.continue.dev/>
- <https://docs.continue.dev/>
- <https://github.com/continuedev/continue>

Goose:

- <https://goose-docs.ai/>
- <https://block.xyz/inside/block-open-source-introduces-codename-goose>

Claude Code:

- <https://code.claude.com/docs/en/agent-sdk/slash-commands>
- <https://code.claude.com/docs/en/agent-sdk/>

Codex:

- <https://developers.openai.com/codex/cli>
- <https://developers.openai.com/codex/cli/features>

OpenClaw:

- <https://openclaw.ai/>
- <https://github.com/openclaw/openclaw>
- <https://docs.openclaw.ai/>
