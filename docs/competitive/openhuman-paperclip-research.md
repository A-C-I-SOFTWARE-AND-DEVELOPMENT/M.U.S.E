# OpenHuman & Paperclip — Identification Research

**Status:** Both products identified. Neither is directly a Claude-Code-class
coding agent. They are adjacent: OpenHuman is a personal-AI runtime that
bundles coding tools, Paperclip is an orchestrator that sits **above** other
coding agents. This document records the disambiguation work so the next
person doesn't repeat it.

**Date:** 2026-05-23 (Phase 23 refresh of Phase 21 work from 2026-05-16)
**Researcher:** Hermes Agent (general-purpose subagent, two-pass verification)
**Method:** Web search + WebFetch against candidate URLs
**Phase 23 verdict:** Both products still alive, growing fast, original
claims hold with two minor drifts on Paperclip (adapter list shift,
launch date correction). Detail in each section.

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
- **Repo:** https://github.com/tinyhumansai/openhuman (26.3k★ as of Phase 23)
- **Docs:** https://tinyhumans.gitbook.io/openhuman/overview/getting-started
- **Product Hunt:** https://www.producthunt.com/products/openhuman
- **Launched:** 2026-05-12
- **Latest release at Phase 23:** v0.54.0 (2026-05-19)
- **License:** GPL-3.0 (confirmed Phase 23, not stated in Phase 21)
- **Language mix:** Rust 63.7% + TypeScript 32.2% (Tauri v2 desktop app)
- **Status flag:** "Early Beta" per README

### Distinctive features (Phase 23 — all verified high-confidence unless noted)

| Feature | Source | Confidence |
|---|---|---|
| Single Rust binary, Tauri v2 desktop app (mac/Win/Linux) | github.com/tinyhumansai/openhuman README | High |
| "Memory Tree" — SQLite + Obsidian-compatible markdown vault, ~3k-token chunks with hierarchical summary tree | tinyhumans.gitbook.io/openhuman | High |
| 118+ OAuth integrations, auto-fetch every 20 minutes per active connection | github.com/tinyhumansai/openhuman README | High |
| TokenJuice compression: HTML→Markdown + dedupe, claims up to ~80% token reduction | github.com/tinyhumansai/openhuman README | Medium — vendor claim, no independent benchmark |
| Voice (ElevenLabs TTS + STT) + lip-synced desktop mascot + live Google Meet agent | github.com/tinyhumansai/openhuman README | High |
| Bundled coder tools (fs/git/lint/test/grep) | github.com/tinyhumansai/openhuman README | High |

### Phase 23 verification deltas

- All Phase 21 claims still hold.
- License confirmed as GPL-3.0 (Phase 21 had this as unconfirmed).
- Auto-fetch cadence ("every 20 minutes") added — present in current
  README, may have been there in Phase 21 but wasn't captured.
- Repo went from launch (~May 12) to 26.3k★ inside two weeks; treated as
  competitive signal but doesn't change Hermes-relevance assessment.

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
- **Repo:** https://github.com/paperclipai/paperclip (67.3k★ / 12.4k forks
  as of Phase 23)
- **Marketing site:** https://paperclip.ing (TLS cert now valid)
- **AWS Marketplace:** https://aws.amazon.com/marketplace/pp/prodview-bzyfsoqckclmy
  — Ubuntu 24.04 AMI, opens at `localhost:3100`, pre-bundles four runtimes
  (Claude Code, Codex, OpenCode, OpenClaw)
- **Launched:** 2026-03-02 (Phase 21 said 03-04; AWS + blog sources are
  the more authoritative 03-02)
- **Latest release at Phase 23:** v2026.517.0 (2026-05-17)
- **License:** MIT (per repo)
- **Language mix:** TypeScript 97.8%

### Distinctive features (Phase 23)

| Feature | Source | Confidence |
|---|---|---|
| Node.js 20+ server + React UI, embedded Postgres (or external) | github.com/paperclipai/paperclip | High |
| Adapters: OpenClaw, Claude Code, Codex, Bash, HTTP webhooks (headline list); AMI adds OpenCode, Cursor, OpenRouter models | github.com/paperclipai/paperclip README; AWS Marketplace listing | High |
| Persists Claude Code session IDs between heartbeats; cwd-aware resume; auto-retry on unknown-session; `maxTurnsPerRun` default 300 | docs/adapters/claude-local.md | High |
| Org chart / roles / budgets / governance / approval gates / ticket audit trail | github.com/paperclipai/paperclip; paperclip.ing | High |
| Multi-company isolation in a single deployment | github.com/paperclipai/paperclip | High |
| Task-based atomic execution + runtime skill injection + company export/import | README | Medium |

### Phase 23 verification deltas

- **Adapter list shift.** Phase 21 listed `claude_local, codex, cursor,
  gemini, opencode`. Current README headline list is **OpenClaw, Claude
  Code, Codex, Bash, HTTP webhooks**; AWS Marketplace page adds
  OpenCode, Cursor, OpenRouter. **Gemini is no longer in the headline
  enumeration** in either surface — searched the repo's README and
  adapter docs index. Whether it was removed or simply de-emphasized
  cannot be determined from public sources; flagged as INSUFFICIENT
  EVIDENCE for the "removed" interpretation.
- **OpenClaw is now first-class** as a Paperclip-native worker (was
  external in Phase 21).
- **AMI now bundles four runtimes** out of the box, which makes Paperclip
  more of a turnkey appliance than Phase 21's "self-host the Node app"
  framing implied.
- **Launch date corrected** 03-04 → 03-02 per AWS Marketplace + jimmysong.io.
- Tagline still verbatim in README: "If OpenClaw is an _employee_,
  Paperclip is the _company_."

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

## Confidence summary

| Question | Answer | Confidence |
|---|---|---|
| Does "OpenHuman" refer to `tinyhumansai/openhuman`? | Yes | High |
| Is OpenHuman a coding-agent competitor? | No — adjacent personal AI | High |
| Does "Paperclip" refer to `paperclipai/paperclip`? | Yes | High |
| Is Paperclip a coding-agent competitor? | No — orchestrator above them | High |
| Are the feature lists above complete? | No — only the loudest features | Medium |
| Should Hermes copy any of these features wholesale? | No — selectively, see relevance sections | High |

## Open questions / follow-up

- TokenJuice compression — has it been benchmarked outside vendor claims?
- Paperclip's `claude_local` adapter — does it survive Claude Code's
  evolving CLI flags, or does it require version-pinning?
- OpenHuman's 118 OAuth integrations — what does the auth-rotation /
  refresh story look like? Hermes' credential pool would benefit from
  knowing.

## Sources

- https://github.com/tinyhumansai/openhuman (Phase 21 + Phase 23)
- https://tinyhumans.gitbook.io/openhuman/overview/getting-started
- https://www.producthunt.com/products/openhuman
- https://knightli.com/en/2026/05/15/openhuman-open-source-personal-ai-agent/ (secondary)
- https://github.com/OpenHands/OpenHands (the unrelated project)
- https://github.com/paperclipai/paperclip (Phase 21 + Phase 23)
- https://github.com/paperclipai/paperclip/blob/master/docs/adapters/claude-local.md
- https://paperclip.ing/
- https://aws.amazon.com/marketplace/pp/prodview-bzyfsoqckclmy
- https://jimmysong.io/ai/paperclip/ (secondary — Phase 23 addition for
  launch-date cross-check)
- https://github.com/fredruss/agent-paperclip (separate small project)
