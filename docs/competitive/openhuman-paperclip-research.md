# OpenHuman & Paperclip — Identification Research

**Status:** Both products identified. Neither is directly a Claude-Code-class
coding agent. They are adjacent: OpenHuman is a personal-AI runtime that
bundles coding tools, Paperclip is an orchestrator that sits **above** other
coding agents. This document records the disambiguation work so the next
person doesn't repeat it.

**Date:** 2026-05-23
**Researcher:** Hermes Agent (general-purpose subagent)
**Method:** Web search + WebFetch against candidate URLs

## How this feeds the rest of the orchestration stack

This file is a **competitive feature harvester** output. It is one of
the inputs to:

- [`docs/ai-intelligence/ai-improvement-radar.md`](../ai-intelligence/ai-improvement-radar.md)
  and [`skills/ai-improvement-radar/SKILL.md`](../../skills/ai-improvement-radar/SKILL.md)
  — the radar reviews competitive findings each cycle and extracts
  only actionable features (Principle 9 of
  [`docs/mission/best-coding-tool-mission.md`](../mission/best-coding-tool-mission.md)).
- [`docs/ai-intelligence/model-registry.yaml`](../ai-intelligence/model-registry.yaml)
  and [`docs/ai-intelligence/model-routing-policy.md`](../ai-intelligence/model-routing-policy.md)
  — actionable findings may trigger registry / policy updates routed
  through [`skills/decision-quality-gate/SKILL.md`](../../skills/decision-quality-gate/SKILL.md)
  (ledger template: [`docs/orchestration/decision-ledger.md`](../orchestration/decision-ledger.md)).
- [`docs/orchestration/self-improvement-loop.md`](../orchestration/self-improvement-loop.md)
  and [`skills/self-improvement-loop/SKILL.md`](../../skills/self-improvement-loop/SKILL.md)
  — the loop may emit `routing_miss` proposals when this harvest
  reveals a tool Hermes should have routed to.

Discipline rule (same as the radar): only **shipped, documented**
features move policy. Marketing claims and unreproduced benchmarks
stay in the unverified column.

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
| Adapters for `claude_local`, `codex`, `cursor`, `gemini`, `opencode` + HTTP/webhook bots | github.com/paperclipai/paperclip/blob/master/docs/adapters/claude-local.md | High |
| Persists Claude Code session IDs across heartbeats; resumes with `--add-dir` skill symlinks | docs/adapters/claude-local.md | High |
| Org chart / roles / budgets / governance / ticket audit trail | github.com/paperclipai/paperclip; paperclip.ing | High |
| Multi-company isolation in a single deployment | github.com/paperclipai/paperclip | Medium |

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

- https://github.com/tinyhumansai/openhuman
- https://tinyhumans.gitbook.io/openhuman/overview/getting-started
- https://www.producthunt.com/products/openhuman
- https://knightli.com/en/2026/05/15/openhuman-open-source-personal-ai-agent/ (secondary)
- https://github.com/OpenHands/OpenHands (the unrelated project)
- https://github.com/paperclipai/paperclip
- https://github.com/paperclipai/paperclip/blob/master/docs/adapters/claude-local.md
- https://paperclip.ing/
- https://aws.amazon.com/marketplace/pp/prodview-bzyfsoqckclmy
- https://github.com/fredruss/agent-paperclip (separate small project)
