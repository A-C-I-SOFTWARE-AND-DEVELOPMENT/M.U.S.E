---
name: ai-improvement-radar
description: "Track AI coding-agent improvements (Codex, Claude Code, Aider, Goose, Continue, OpenHands, Gemini/Jules/Antigravity, OpenClaw-style personal agents) and recommend updates to Hermes' routing policy, model registry, and tool capability matrix."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ai-intelligence, radar, routing, coding-agents, evaluation, policy]
    related_skills: [claude-code, codex, hermes-agent, opencode]
    docs:
      - docs/ai-intelligence/ai-improvement-radar.md
    related_docs:
      - docs/ai-intelligence/model-registry.yaml
      - docs/ai-intelligence/model-routing-policy.md
      - docs/ai-intelligence/tool-capability-matrix.md
---

# AI Improvement Radar — Hermes Routing Intelligence

Hermes delegates real work to external AI coding tools (Claude Code, Codex,
Aider, Goose, Continue, OpenHands, Gemini/Jules/Antigravity, OpenClaw-style
personal agents, and others). Those tools ship new capabilities, deprecate old
flags, change pricing, change context windows, and introduce new agent
primitives on their own cadence — sometimes weekly.

This skill is how Hermes **keeps up with that change without acting on hype**.
It is a documentation-and-evidence skill, not a scraper.

## What this skill does

When invoked (via `/ai-improvement-radar` inside Hermes, or via
`scripts/hermes-ai-radar.sh` from a terminal), Hermes:

1. **Reviews official sources** for each tracked coding agent (see
   "Tracked tools" below).
2. **Extracts only actionable features** — features Hermes can use,
   recommend, or route around. Skips marketing claims.
3. **Marks unverified claims as `unverified`** and keeps them out of
   routing decisions until corroborated.
4. **Produces a radar report** under
   `.hermes-orchestrator/ai-radar/<timestamp>-radar.md` with a fixed
   structure (see "Radar report format").
5. **Recommends updates** to the three policy artifacts:
   - `docs/ai-intelligence/model-registry.yaml`
   - `docs/ai-intelligence/model-routing-policy.md`
   - `docs/ai-intelligence/tool-capability-matrix.md`

The skill **does not** edit policy artifacts directly. It writes a
recommendation file and lets the user (or a Hermes orchestrator) decide
whether to apply.

## Tracked tools

Hermes maintains a watchlist for the following coding-agent tools. For each
tool, the radar checks official docs, official GitHub repos, official
changelogs/release notes, and reputable engineering blogs.

| Tool | Vendor | Primary sources |
|---|---|---|
| **Codex** | OpenAI | `github.com/openai/codex`, OpenAI platform docs, OpenAI changelog |
| **Claude Code** | Anthropic | `code.claude.com/docs`, Anthropic engineering blog, Anthropic release notes |
| **Aider** | Paul Gauthier / community | `github.com/Aider-AI/aider`, `aider.chat` docs |
| **Goose** | Block | `github.com/block/goose`, `block.github.io/goose` docs |
| **Continue** | Continue Dev | `github.com/continuedev/continue`, `docs.continue.dev` |
| **OpenHands** | All-Hands-AI | `github.com/All-Hands-AI/OpenHands`, `docs.all-hands.dev` |
| **OpenClaw-like personal agents** | various | Project READMEs, official release notes only |
| **Gemini coding agents** | Google | `github.com/google-gemini`, Google AI / DeepMind official blog |
| **Jules** | Google Labs | Google Labs official site, Google Labs blog posts |
| **Antigravity-style coding agents** | various | Official project sites + release notes only |
| **Other relevant coding-agent tools** | various | Must be added with at least one official source before being tracked |

Adding a new tracked tool requires (a) an official source URL and (b) a
one-line justification of why Hermes might route to it. Speculative entries
do not belong here.

## Source quality rules

The radar must obey these rules. They are non-negotiable.

1. **Prefer official docs, official repos, release notes, and changelogs.**
2. **Reputable engineering sources** (vendor engineering blogs, vendor
   conference talks) are acceptable corroboration.
3. **Social media, forum posts, and "leaks"** are not actionable. They may
   be cited as `unverified` color but never as the sole basis for a
   recommendation.
4. **Mark unverified claims as `unverified`.** A radar report may contain
   unverified rows; the recommendation column for those rows must read
   `wait for official confirmation`.
5. **Do not update routing policy based on hype.** Benchmarks that haven't
   been independently reproduced, "X is now SOTA" claims, and viral
   threads do not move policy. Only shipped, documented features do.
6. **Extract only actionable features.** "Now smarter" is not actionable.
   "Adds `--json-schema` for structured output" is actionable.
7. **Respect official restrictions.** Do not scrape subscription-only
   apps, do not bypass auth, do not use unofficial proxies. If a vendor
   gates information behind a login, the radar records "gated; awaiting
   public source" and moves on.

## Invocation

### Inside Hermes

```text
/ai-improvement-radar
```

The slash command loads this skill. Hermes then walks the tracked-tools
list, fetches official sources it has access to, and writes a radar
report to `.hermes-orchestrator/ai-radar/<timestamp>-radar.md`.

Optional arguments (free-form):

- `tools=<comma-separated>` — restrict the radar to a subset
  (e.g. `tools=claude-code,codex,aider`).
- `since=<YYYY-MM-DD>` — only consider changes after that date. Defaults
  to the timestamp of the most recent radar report.
- `effort=<low|medium|high>` — how aggressively to chase corroboration.

### From a terminal

```bash
scripts/hermes-ai-radar.sh
```

This script prepares a radar request file under
`.hermes-orchestrator/ai-radar/`, detects whether the `hermes` CLI is
installed, and prints instructions telling the user to run
`/ai-improvement-radar` from inside Hermes. The script never scrapes
subscription apps, never bypasses official restrictions, and never edits
policy artifacts on its own.

## Radar report format

Every radar report is a single markdown file with the following sections,
in this order. Skipping or reordering sections is a defect.

```markdown
# Hermes AI Improvement Radar — <ISO timestamp>

## Summary
<2-4 sentences. What moved this cycle. Highest-confidence recommendation.>

## Tools surveyed
<bulleted list of tracked tools that were checked this cycle>

## New features discovered
| Tool | Feature | Source | Confidence | Actionable? |
|---|---|---|---|---|
| ... | ... | <official URL> | high/medium/low/unverified | yes/no |

## Sources checked
- <tool>: <list of official URLs visited>
- ...

## Relevance to Hermes
<For each high/medium-confidence feature, one paragraph on whether and
how it changes how Hermes should route work. If "no change", say so
explicitly.>

## Implementation recommendation
<Concrete, ordered list of changes. Each item names the file to touch
and the rough nature of the change. No code yet.>

## Routing policy update needed
- model-registry.yaml: <yes/no — what would change>
- model-routing-policy.md: <yes/no — what would change>
- tool-capability-matrix.md: <yes/no — what would change>

## Confidence level
<Overall: high / medium / low. One sentence justification.>

## Unverified items (do not act on)
<bulleted list of claims this cycle that did not meet the source-quality
rules. Each item names what would need to corroborate it.>
```

The `Confidence` column in "New features discovered" uses this scale:

- **high** — Two or more official sources confirm; or one official source
  plus a reproducible test we can run locally.
- **medium** — Single official source, clearly documented but not yet
  field-tested by Hermes maintainers.
- **low** — Single official source, but the documentation is ambiguous,
  flagged "preview", or behind a feature flag.
- **unverified** — Source quality does not meet the bar. Do not act.

## Output: where reports live

```
.hermes-orchestrator/
└── ai-radar/
    ├── 2026-05-23T18-30-00Z-radar.md
    ├── 2026-05-23T18-30-00Z-request.json
    └── README.md            # auto-created on first run
```

`<timestamp>-request.json` is what `scripts/hermes-ai-radar.sh` writes;
`<timestamp>-radar.md` is what the slash command produces.

## What this skill does NOT do

- It does **not** edit `docs/ai-intelligence/*` files directly. Changes
  to policy artifacts are user-driven, with the radar report as input.
- It does **not** call non-official APIs, scrape subscription apps, or
  drive logged-in browser sessions. If a piece of information is behind
  auth, the radar records "gated" and waits for a public source.
- It does **not** benchmark or rank tools on its own. The radar reports
  features; ranking is the routing policy's job.
- It does **not** auto-promote features into the routing policy on a
  schedule. Every promotion is an explicit human decision after reading
  the report.

## Rules for Hermes agents running this skill

1. **Always write the report file before responding.** Even a "nothing
   moved this cycle" report should be written, so the timeline is
   complete.
2. **Cite sources inline.** Every feature row in "New features
   discovered" must carry an official URL.
3. **Refuse to fabricate.** If a source can't be reached, write "source
   unreachable this cycle" — do not invent a feature.
4. **Do not summarize hype.** Reddit/X/HN aren't sources. A reproducible
   official changelog entry is.
5. **Recommend, don't decide.** The "Implementation recommendation" and
   "Routing policy update needed" sections are inputs to a human review,
   not commit-ready diffs.
6. **Mark gated content as gated.** "Behind a login wall" → record it,
   don't try to bypass.
7. **Prefer narrow, citable claims.** "Codex `exec` now accepts `--foo`
   per <official URL> dated <date>" beats "Codex got better."
8. **Keep reports short.** A good radar report is two to four pages, not
   twenty. Long reports usually mean low signal-to-noise.

## See also

- `docs/ai-intelligence/ai-improvement-radar.md` — narrative companion
  to this skill (audience, cadence, governance).
- `docs/ai-intelligence/model-registry.yaml` — recommended target for
  model-level updates.
- `docs/ai-intelligence/model-routing-policy.md` — recommended target
  for routing-rule updates.
- `docs/ai-intelligence/tool-capability-matrix.md` — recommended target
  for per-tool capability updates.
- `skills/autonomous-ai-agents/claude-code/SKILL.md`
- `skills/autonomous-ai-agents/codex/SKILL.md`
- `skills/autonomous-ai-agents/hermes-agent/SKILL.md`
