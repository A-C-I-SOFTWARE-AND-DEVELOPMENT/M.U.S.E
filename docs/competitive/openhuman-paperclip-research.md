# OpenHuman, Paperclip & OpenClaw — Identification Research

**Status:** Three products identified. None of them is directly a
Claude-Code-class coding agent, but each occupies a different adjacent
space worth Hermes' attention:

- **OpenHuman** — personal-AI runtime that bundles coding tools
- **Paperclip** — orchestrator that sits **above** other coding agents
- **OpenClaw** — local-first multi-channel personal assistant; the
  closest architectural analog to Hermes that currently exists

This document records the disambiguation work so the next person doesn't
repeat it.

**Date:** 2026-05-23
**Researcher:** Hermes Agent (general-purpose subagent, with verification
pass on the same date)
**Method:** Web search + WebFetch against candidate URLs and the
official Mintlify / GitBook documentation sites

---

## 1. OpenHuman

### Verdict

Found, **medium-high confidence**. The product is `tinyhumansai/openhuman`
on GitHub, an open-source local-first "personal AI" desktop runtime.

It is **not** a direct competitor to Claude Code / Cursor / Aider / OpenHands
/ Continue / Goose. It bundles a coder toolset (fs/git/lint/test/grep) as
one of many capabilities, but its positioning is "personal AI assistant,"
closer to a privacy-first Rewind or Personal.ai than a software-engineering
agent.

### Identity

- **Name:** OpenHuman
- **Repo:** https://github.com/tinyhumansai/openhuman
- **Docs:** https://tinyhumans.gitbook.io/openhuman/overview/getting-started
- **Product Hunt:** https://www.producthunt.com/products/openhuman
- **Launched:** ~2026-05-12
- **License:** Open source (per README; specific license not confirmed in
  this pass)

### Distinctive features (medium confidence on the marketing claims)

| Feature | Source | Confidence |
|---|---|---|
| Single Rust binary, local-first runtime | github.com/tinyhumansai/openhuman README | High |
| "Memory Tree" — SQLite + Obsidian-compatible markdown vault | tinyhumans.gitbook.io/openhuman | High |
| 118+ OAuth integrations, periodic auto-fetch | github.com/tinyhumansai/openhuman README | Medium |
| TokenJuice compression (claims ~80% token reduction) | github.com/tinyhumansai/openhuman README | Medium — vendor claim |
| Voice + desktop mascot, can join Google Meets | github.com/tinyhumansai/openhuman README | Medium |
| Bundled coder tools (fs/git/lint/test/grep) | github.com/tinyhumansai/openhuman README | Medium |

### NOT to be confused with

- **OpenHands** (formerly OpenDevin) — `github.com/OpenHands/OpenHands`.
  Genuine coding agent. The user's hunch that OpenHuman might be a
  misspelling of OpenHands is wrong: they are distinct projects with
  different orgs, distinct positioning, and different shipping cadences.
- **Open Humans** — `openhumans.org` — citizen-science data-sharing
  community. Unrelated.
- **Aggregator listings** (e.g. `completeaitraining.com`, `topai.tools`) —
  these mirror the GitHub README, do not add independent verification.

### Relevance to Hermes

Two ideas worth borrowing if their efficacy is real:

1. **Obsidian-compatible markdown vault as memory store.** Hermes' memory
   is plugin-backed; an Obsidian-format provider would let users browse
   and edit memory in their own knowledge tool. Track as a possible
   memory plugin contribution, not a core change.
2. **TokenJuice-style compression.** Hermes already has
   `trajectory_compressor.py` and `agent/context_compressor.py`. Worth
   comparing against TokenJuice's approach if/when it's published as a
   paper or benchmark.

Everything else (Rust binary, 118 OAuth integrations, mascot, Google Meet
join) is orthogonal to Hermes' Python-first, gateway-driven design and
shouldn't be ported.

---

## 2. Paperclip

### Verdict

Found, **high confidence**. The product is `paperclipai/paperclip` on
GitHub: an open-source (MIT) Node.js + React self-hosted platform that
orchestrates teams of AI agents as if they were employees of a company.

Paperclip **does not compete with** Claude Code / Cursor / Aider / OpenHands
/ Continue / Goose. It **wraps** them via adapters and adds org-chart,
role, budget, governance, and ticket-based audit layers on top. Closer
competitors are CrewAI, AutoGen, and LangGraph.

The Paperclip docs themselves frame it this way:

> "If OpenClaw is an _employee_, Paperclip is the _company_."

### Identity

- **Name:** Paperclip
- **Repo:** https://github.com/paperclipai/paperclip
- **Marketing site:** https://paperclip.ing (note: TLS certificate
  reported "not yet valid" when fetched during research — consistent with
  a freshly issued cert on a new domain, but flagged here so future
  reviewers don't ignore the signal)
- **AWS Marketplace:** https://aws.amazon.com/marketplace/pp/prodview-bzyfsoqckclmy
- **Launched:** ~2026-03-04
- **License:** MIT (per repo)

### Distinctive features

| Feature | Source | Confidence |
|---|---|---|
| Node.js server + React UI, self-hosted, embedded Postgres | github.com/paperclipai/paperclip | High |
| Built-in adapters (V1): `claude_local` and `codex_local`. A "Generic Process" adapter for arbitrary CLI tools is documented but marked **"not yet implemented in V1"** | https://paperclipai-paperclip.mintlify.app/agents/process-adapter | High |
| Supported runtime logos on landing page: OpenClaw, Claude Code, Codex, Cursor, Bash, HTTP — interpret as messaging, not as a confirmed shipped-adapter list | https://paperclip.ing/ | Medium |
| Persists Claude Code session IDs across heartbeats; resumes with `--add-dir` skill symlinks | https://github.com/paperclipai/paperclip/blob/master/docs/adapters/claude-local.md | High |
| Org chart / roles / budgets / governance / ticket audit trail | github.com/paperclipai/paperclip; paperclip.ing | High |
| Multi-company isolation in a single deployment | github.com/paperclipai/paperclip | Medium |

> **Correction note (2026-05-23):** an earlier pass of this document
> listed five adapters (`claude_local`, `codex`, `cursor`, `gemini`,
> `opencode`) as high-confidence built-ins. The current Mintlify docs
> show only two are shipped in V1. Some of the "logos" on the marketing
> page may be roadmap items, community contributions, or live in
> branches/PRs. Treat the marketing list as aspirational until
> verified per-adapter from the repo.

### NOT to be confused with

- **Ruby on Rails `thoughtbot/paperclip` gem** — legacy file-upload library.
  Different category, different era.
- **`fredruss/agent-paperclip`** — a small separate "desktop companion for
  Claude Code and Codex," not the same product.
- **Karpathy's "paperclip maximizer"** — theoretical AI-safety reference,
  not a product.
- **Historical `paperclip-cli` ML tool** — unrelated.

### Relevance to Hermes

Paperclip's existence is a **direct validation of Hermes' multi-platform
gateway + delegate-task + cron + kanban story.** Hermes already does most
of what Paperclip exists to do — orchestrate multiple coding agents — but
through subagent delegation and the kanban board rather than as an explicit
"company" metaphor. Two specific ideas worth considering:

1. **Adapter contract for external coding agents.** Hermes can already
   delegate via `terminal(command="claude -p ...")` etc., but a formal
   adapter contract (start/stop, session-resume, heartbeat, results
   capture) would make multi-agent workflows tidier. The Paperclip
   `claude_local` adapter docs are a good starting reference for that
   contract.
2. **Persistent session-ID resume across heartbeats.** Hermes' cron jobs
   currently spawn a fresh session per run. For long-running delegated
   coding work, the Paperclip pattern of persisting the child agent's
   session ID and resuming on the next tick is worth evaluating against
   Hermes' kanban worker model.

Everything else (org chart, budgets, governance UI, AWS Marketplace
distribution) is product surface Hermes deliberately leaves to plugins
or to the kanban board's existing roles/assignment primitives.

---

---

## 3. OpenClaw

### Verdict

Found, **high confidence**. The product is `openclaw/openclaw` on GitHub:
an MIT-licensed local-first personal AI assistant ("Your own personal AI
assistant. Any OS. Any Platform. The lobster way. 🦞"). Reported >100k
stars within the first week of launch (late January 2026), with active
near-daily releases through 2026. Built by Peter Steinberger and
community.

OpenClaw is the **closest architectural analog to Hermes that currently
exists.** It is not a coding-agent-in-IDE; it is a local-first
multi-channel gateway + agent runtime with skills, cron, webhooks,
sandboxed sessions, voice, and companion apps. Treat it as the
primary competitive benchmark for the Hermes gateway and skill
surfaces.

### Identity

- **Name:** OpenClaw
- **Repo:** https://github.com/openclaw/openclaw
- **Marketing site:** https://openclaw.ai/
- **AGENTS.md (project rules):** https://github.com/openclaw/openclaw/blob/main/AGENTS.md
- **Community templates:** https://github.com/mergisi/awesome-openclaw-agents
  (162 SOUL.md templates across 19 categories — community-maintained)
- **Hosting platform:** https://www.oneclaw.net/ (third-party managed
  hosting, not first-party)
- **Launched:** late January 2026
- **License:** MIT

### Distinctive features

| Feature | Source | Confidence |
|---|---|---|
| Local-first Gateway as "single control plane for sessions, channels, tools, and events" | github.com/openclaw/openclaw README | High |
| Multi-channel inbox supporting 24+ messaging platforms (WhatsApp, Telegram, Slack, Discord, Google Chat, Signal, iMessage, IRC, Teams, Matrix, Feishu, LINE, Mattermost, Nextcloud Talk, Nostr, Synology Chat, Tlon, Twitch, Zalo, Zalo Personal, WeChat, QQ, WebChat) | github.com/openclaw/openclaw README | High |
| Multi-agent routing — direct inbound channels/accounts to isolated agents | github.com/openclaw/openclaw README | High |
| Voice Wake + Talk Mode on macOS/iOS; continuous voice on Android | github.com/openclaw/openclaw README | High |
| Live Canvas — agent-driven visual workspace ("Render a live Canvas you control") | github.com/openclaw/openclaw README | High |
| SOUL.md — injected prompt file defining agent personality | github.com/openclaw/openclaw, awesome-openclaw-agents | High |
| AGENTS.md (scoped) — root rules plus per-subtree `AGENTS.md` ("Read scoped `AGENTS.md` before subtree work") | github.com/openclaw/openclaw/blob/main/AGENTS.md | High |
| Workspace skills under `~/.openclaw/workspace/skills/` | github.com/openclaw/openclaw README | High |
| Sandbox modes for non-main sessions (Docker, SSH, OpenShell backends) | github.com/openclaw/openclaw README | High |
| First-class tools: browser, canvas, nodes, cron, sessions | github.com/openclaw/openclaw README | High |
| Companion apps for macOS, iOS, Android | github.com/openclaw/openclaw README | High |
| DM pairing policies + explicit allowlisting for unknown senders (security default) | github.com/openclaw/openclaw README | High |
| Adapted by Paperclip as a supported runtime ("OpenClaw bots" listed in Paperclip docs) | paperclip.ing/, github.com/paperclipai/paperclip | High |

### NOT to be confused with

- **OpenHuman** (`tinyhumansai/openhuman`) — different product. Similar
  positioning ("personal AI"), different stack (Rust binary vs the
  OpenClaw gateway), different feature pillars (Memory Tree + Obsidian
  vs multi-channel gateway). See section 1.
- **OpenHands** (`All-Hands-AI/OpenHands`, formerly OpenDevin) — that one
  IS a coding agent. See `developer-agent-feature-harvest.md` for its
  features.
- **`Gen-Verse/OpenClaw-RL`** — separate research project about training
  agents via RL ("Train any agent simply by talking"). Different repo,
  different scope.
- **`mergisi/awesome-openclaw-agents`** — community SOUL.md template
  repository. Useful, but not the OpenClaw runtime itself.
- **`oneclaw.net`** — third-party managed-hosting service for OpenClaw.
  Branding overlap; not the upstream project.

### Relevance to Hermes

OpenClaw is **the most direct competitive comparison Hermes has.** Both
products are: local-first, multi-channel, skill-driven, sandboxed,
voice-enabled, cron-enabled, plugin-extensible, MIT-licensed. The honest
read on each axis:

| Axis | Hermes | OpenClaw |
|---|---|---|
| Messaging platforms shipped | ~10 | 24+ |
| Sandbox backends | 7 (local, Docker, SSH, Modal, Daytona, Singularity, Vercel) | 3 (Docker, SSH, OpenShell) |
| Model providers | 20+ via `plugins/model-providers/` | Fewer, less emphasized |
| Orchestration / multi-worker | Full Job/Worker/Validation/Ledger | Single-agent, no equivalent |
| Personality / persona system | YAML personalities | SOUL.md (single-file convention; community marketplace exists) |
| Visible canvas / non-text surface | Dashboard React (HTML/widgets) | Live Canvas (purpose-built) |
| Companion apps | Android only | macOS + iOS + Android |
| Voice | Push-to-talk, CLI | Wake-word + Talk Mode + continuous Android |
| AGENTS.md walk | Root only | Root + scoped per subtree |
| Marketplace | Skill hub (Hermes-side) | SOUL.md template marketplace (community) |
| GitHub stars at launch | n/a (no headline launch event yet) | 100k+ in first week |

**Net:** Hermes wins on orchestration depth and model breadth. OpenClaw
wins on channel parity, companion-app coverage, voice ergonomics,
visible-reasoning surface (Live Canvas), and community marketplace
network effects. Closing the OpenClaw gap on channels + Live Canvas +
scoped AGENTS.md + SOUL.md compatibility is the cleanest near-term
move. Replicating OpenClaw's launch model (PR a big-name launch,
ecosystem template repo, hosting partner) is a separate strategic
question that does not belong in this doc.

---

## Confidence summary

| Question | Answer | Confidence |
|---|---|---|
| Does "OpenHuman" refer to `tinyhumansai/openhuman`? | Yes | High |
| Is OpenHuman a coding-agent competitor? | No — adjacent personal AI | High |
| Does "Paperclip" refer to `paperclipai/paperclip`? | Yes | High |
| Is Paperclip a coding-agent competitor? | No — orchestrator above them | High |
| Does Paperclip ship five built-in adapters (claude_local, codex, cursor, gemini, opencode)? | **No** — only `claude_local` + `codex_local` are V1; landing-page logos are aspirational | High |
| Does "OpenClaw" refer to `openclaw/openclaw`? | Yes | High |
| Is OpenClaw a coding-agent competitor? | No — multi-channel personal-assistant runtime; closest architectural analog to Hermes | High |
| Are the feature lists above complete? | No — only the loudest features | Medium |
| Should Hermes copy any of these features wholesale? | No — selectively, see relevance sections | High |

## Open questions / follow-up

- TokenJuice compression — has it been benchmarked outside vendor claims?
- Paperclip's `claude_local` adapter — does it survive Claude Code's
  evolving CLI flags, or does it require version-pinning? And which of
  the marketing-page logos (Cursor, Gemini, OpenCode) correspond to
  actual shipped adapters vs roadmap?
- OpenHuman's 118 OAuth integrations — what does the auth-rotation /
  refresh story look like? Hermes' credential pool would benefit from
  knowing.
- OpenClaw's Live Canvas — what's the protocol between agent and canvas
  surface? Is it a documented tool API, or is it bound to OpenClaw's
  internal UI? Worth fetching the `nodes` / `canvas` source to decide
  whether the Hermes dashboard can implement the same contract.
- OpenClaw's `~/.openclaw/workspace/skills/` — is the format
  SOUL.md-style or SKILL.md-style? If the latter, are the two formats
  interoperable enough that Hermes' skill loader can read OpenClaw
  workspaces?

## Sources

### OpenHuman
- https://github.com/tinyhumansai/openhuman
- https://github.com/tinyhumansai/openhuman/blob/main/README.md
- https://github.com/tinyhumansai/openhuman/blob/main/gitbooks/README.md
- https://github.com/tinyhumansai/openhuman/blob/main/gitbooks/features/token-compression.md
- https://tinyhumans.gitbook.io/openhuman/overview/getting-started
- https://www.producthunt.com/products/openhuman
- https://knightli.com/en/2026/05/15/openhuman-open-source-personal-ai-agent/ (secondary)
- https://pasqualepillitteri.it/en/news/2704/openhuman-open-source-ai-agent-local-memory (secondary)
- https://moge.ai/product/openhuman-by-tinyhumans (secondary)

### Paperclip
- https://github.com/paperclipai/paperclip
- https://github.com/paperclipai/paperclip/blob/master/docs/adapters/claude-local.md
- https://github.com/paperclipai/paperclip/blob/master/.agents/skills/create-agent-adapter/SKILL.md
- https://github.com/paperclipai/paperclip/blob/master/doc/PRODUCT.md
- https://paperclip.ing/
- https://paperclipai-paperclip.mintlify.app/agents/process-adapter (authoritative for built-in adapter list)
- https://aws.amazon.com/marketplace/pp/prodview-bzyfsoqckclmy
- https://github.com/fredruss/agent-paperclip (separate small project)

### OpenClaw
- https://github.com/openclaw/openclaw
- https://github.com/openclaw/openclaw/blob/main/AGENTS.md
- https://github.com/openclaw/openclaw/releases
- https://openclaw.ai/
- https://github.com/mergisi/awesome-openclaw-agents
- https://github.com/Gen-Verse/OpenClaw-RL (unrelated)
- https://www.oneclaw.net/blog/personal-ai-agent-github (third-party hosting platform)
- https://www.freecodecamp.org/news/how-to-build-and-secure-a-personal-ai-agent-with-openclaw/ (secondary)
- https://www.digitalocean.com/resources/articles/what-is-openclaw (secondary)

### Disambiguation references
- https://github.com/OpenHands/OpenHands (different — coding agent)
- https://openhumans.org (different — citizen-science data community)
