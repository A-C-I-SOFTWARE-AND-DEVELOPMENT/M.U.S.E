# OpenHuman and Paperclip — Competitive Feature Research

Primary-source notes captured by the `competitive-feature-harvester` skill.
Last verified: 2026-05-23.

This file is the source of truth for OpenHuman- and Paperclip-specific claims that feed into `developer-agent-feature-harvest.md`. Every feature listed here is tied to a URL. Anything not tied to a URL is marked `unverified`.

---

## OpenHuman

> "Your Personal AI super intelligence: local memory, managed services where needed, simple and powerful."
> — [tinyhumansai/openhuman README](https://github.com/tinyhumansai/openhuman)

**Repo:** [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) · 26.2k stars · v0.54.0 (May 19, 2026) · GPL-3.0 · status "Early Beta"
**Site:** [openhuman.dev](https://www.openhuman.dev/)
**Docs:** [tinyhumans.gitbook.io/openhuman](https://tinyhumans.gitbook.io/openhuman)

### Verified features

| Feature | Primary source | Quoted phrase / evidence |
|---|---|---|
| Local-first **Memory Tree** stored in SQLite, with Markdown vault for Obsidian | [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | "Memory Tree + Obsidian Wiki — Local-first knowledge base stored in SQLite on your machine" |
| **118+ OAuth integrations** with one-click connect (Gmail, GitHub, Slack, Notion, Stripe, Calendar, Drive, Linear, Jira, …) | [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | "118+ third-party integrations with auto-fetch" |
| **Auto-fetch every ~20 minutes** from active connectors into the memory tree | [openhuman.dev](https://www.openhuman.dev/) | "Background pulls run on a steady cadence (about every 20 minutes)" |
| **TokenJuice** token compression, "up to 80%" reduction in cost/latency | [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | "Smart token compression (TokenJuice) reducing costs/latency up to 80%" |
| **Model routing** across reasoning / fast / vision profiles | [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | "Model routing for reasoning/fast/vision workloads" |
| Optional **local models via Ollama** | [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | "Optional local AI via Ollama support" |
| Native **voice (STT + ElevenLabs TTS)** | [github.com/tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | "Web search, web scraping, filesystem/git toolset, native voice (STT + ElevenLabs TTS)" |
| **Desktop-first UX**, no terminal required, short onboarding to a working agent | [openhuman.dev](https://www.openhuman.dev/) | "A UI-first shell with short paths to a working agent—no config-first or terminal-only gatekeeping" |
| Cross-platform desktop install (Windows / macOS / Linux) | [openhuman.dev](https://www.openhuman.dev/) | "install it on Windows, macOS, or Linux, then work inside a familiar window" |

### Marketing-only / partly verified

| Feature | Status | Why |
|---|---|---|
| Desktop **mascot** that "joins Google Meets as a real participant" | `medium` | Mentioned in the README and Product Hunt page but only briefly; behaviour and limits not specified in docs. |
| Memory "scales up to 1 billion tokens" | `low` | Number appears in third-party reviews and on the README; no architectural detail in docs explaining how. |
| "Encrypted locally" | `low` | Phrase used on landing page; algorithm and key management not documented. |

### Gaps in the official material

- No published benchmarks or latency numbers.
- No user testimonials carried on the README/site — "user-loved" reasons must be inferred from product-hunt comments (out of scope for verified harvest).
- No roadmap or pricing for managed services.

### Sources

- <https://github.com/tinyhumansai/openhuman>
- <https://www.openhuman.dev/>
- <https://tinyhumans.gitbook.io/openhuman>
- <https://www.producthunt.com/products/openhuman>

---

## Paperclip

> "Open-source orchestration for zero-human companies."
> — [paperclipai/paperclip README](https://github.com/paperclipai/paperclip)

**Repo:** [github.com/paperclipai/paperclip](https://github.com/paperclipai/paperclip) · 67.3k stars · v2026.517.0 (May 17, 2026) · MIT
**Site:** [paperclip.ing](https://paperclip.ing/)
**Quickstart:** `npx paperclipai onboard --yes`

Paperclip explicitly positions itself as the layer *above* agents: "if OpenClaw is an employee, Paperclip is the company." This is relevant to Hermes because Paperclip lists **Hermes** as one of the supported runtimes ([paperclip.ing](https://paperclip.ing/)) — so the relationship is integration first, competition second.

### Verified features

| Feature | Primary source | Quoted phrase / evidence |
|---|---|---|
| **Bring Your Own Agent** — any runtime that can receive a heartbeat (OpenClaw, Claude Code, Codex, Cursor, Bash, HTTP/webhook bots, **Hermes**, Pi, OpenCode) | [paperclip.ing](https://paperclip.ing/) / [github.com/paperclipai/paperclip](https://github.com/paperclipai/paperclip) | "If it can receive a heartbeat, it's hired." |
| **Heartbeat execution** — scheduled wakeups with persistent context across sessions | [github.com/paperclipai/paperclip](https://github.com/paperclipai/paperclip) | "Heartbeats — Scheduled agent wakeups with persistent context across sessions" |
| **Org chart** — roles, titles, reporting lines, permissions | [paperclip.ing](https://paperclip.ing/) | "Hierarchies, roles, reporting lines. Your agents have a boss, a title, and a job description." |
| **Goal alignment** — every task carries full goal ancestry back to the company mission | [paperclip.ing](https://paperclip.ing/) | "Every task traces back to the mission. Agents know what to do and why." |
| **Per-agent monthly budgets** with hard stops at 100% utilization | [paperclip.ing](https://paperclip.ing/) | "Monthly budgets per agent. When they hit the limit, they stop." |
| **Ticket system** — every conversation, tool call, and decision recorded as immutable audit log | [paperclip.ing](https://paperclip.ing/) | "Every conversation traced. Every decision explained." |
| **Governance / board approvals** — approve hires, override strategy, pause or terminate any agent | [paperclip.ing](https://paperclip.ing/) | "You're in charge. Approve hires, override strategy, pause or terminate any agent." |
| **Recurring tasks** via cron, webhook, and API triggers | [github.com/paperclipai/paperclip](https://github.com/paperclipai/paperclip) | "Recurring tasks with cron, webhook, and API triggers handle regular work automatically" |
| **Multi-company tenancy** — single deployment, data isolation per org | [github.com/paperclipai/paperclip](https://github.com/paperclipai/paperclip) | "Multi-Company — Single deployment, complete data isolation across organizations" |
| **Plugins** as out-of-process workers with capability-gated host services | [github.com/paperclipai/paperclip](https://github.com/paperclipai/paperclip) | "Plugins (out-of-process workers)" |
| **Company portability** — export/import entire organizations with secret scrubbing | [github.com/paperclipai/paperclip](https://github.com/paperclipai/paperclip) | "Export and import entire organizations — agents, skills, projects, routines, and issues — with secret scrubbing and collision handling" |
| Skill discovery via `SKILL.md` documents (same standard Hermes uses) | [paperclip.ing](https://paperclip.ing/) | "Skill Discovery: SKILL.md documentation enables agents to find contextual information" |
| **Mobile dashboard** | [github.com/paperclipai/paperclip](https://github.com/paperclipai/paperclip) | "Mobile Ready — Dashboard access from anywhere" |

### Marketing-only / partly verified

| Feature | Status | Why |
|---|---|---|
| "Zero-human company" framing | `medium` | Framing is consistent across site and README but is a positioning claim, not a feature. Treat as design philosophy. |
| Specific count of supported runtimes (`6` vs `8`) | `low` | README lists "OpenClaw, Claude Code, Codex, Cursor, Bash, HTTP/webhook"; site additionally lists Hermes, Pi, OpenCode. Treat the union as truth, but the exact count drifts between pages. |

### Gaps in the official material

- No published throughput / scale numbers (how many agents per deployment).
- No reference benchmarks for budget-enforcement latency.
- No public user testimonials on README; framing is "problem ❌ / solution ✅" pairs.

### Sources

- <https://github.com/paperclipai/paperclip>
- <https://paperclip.ing/>

---

## Why these two together

OpenHuman and Paperclip address opposite halves of the same problem:

- **OpenHuman** is the personal-agent layer — local memory, OAuth fan-in, desktop UX.
- **Paperclip** is the orchestration layer over many agents — budgets, tickets, governance.

Hermes already lives in OpenHuman's territory (messaging gateway, skills, memory, cron). Paperclip's territory — multi-agent governance with hard budgets and immutable audit logs — is mostly **unaddressed** in Hermes today, and is the larger harvest opportunity.

See `developer-agent-feature-harvest.md` for the per-feature mapping and recommendations.
