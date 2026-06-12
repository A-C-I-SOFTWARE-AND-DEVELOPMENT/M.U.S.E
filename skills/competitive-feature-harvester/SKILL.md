---
name: competitive-feature-harvester
description: "Harvest competitor agent features into a Hermes backlog."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, competitive, product, harvest, backlog]
    category: research
    related_skills: [blogwatcher, research-paper-writing, requesting-code-review]
---

# Competitive Feature Harvester

Survey competing AI coding agents, extract the features users actually praise,
match them against what Hermes already ships, and emit a prioritized backlog
of things worth copying or beating. Verified sources only. No fabricated
features.

## When to Use

- A new agent or release is making noise and we need to know what to copy
- Quarterly: refresh the harvest so the backlog doesn't drift
- A feature request from a user echoes something a competitor ships — confirm
  what they actually do before committing to design
- A PR proposes adopting a competitor's pattern — verify the pattern before
  greenlighting

**Skip for:** general curiosity research with no decision attached, marketing
posts that are not engineering decisions, or comparisons where Hermes is
clearly out of category (image generation tools, web-only builders).

## Prerequisites

- `WebSearch` and `WebFetch` tools available
- The Agent / subagent tool (this skill parallelizes research)
- A clear list of competitors you want to cover
- Read access to the Hermes repo so you can mark "already ships" honestly
  (especially `AGENTS.md`, `README.md`, the `RELEASE_v*.md` files, the
  `skills/` tree, and `toolsets.py`)

## Inputs

The user provides:
1. **Competitor list** (e.g. "OpenHands, Aider, Codex, Continue, Goose")
2. **Scope** — features only, or features + a Hermes adoption backlog?
3. **Output directory** (defaults to `docs/competitive/` and `docs/product/`)

## Procedure

### Phase 1 — Inventory Hermes first

Run a single `Explore` subagent against the repo with a checklist of
capability areas (core agent, dev/code, platforms, security, eval/training,
config/UX). For each capability, return one of:

- ✅ YES + file path
- ⚠️ PARTIAL + file path + what's missing
- ❌ NO

This anchors the harvest in reality — without it, you will recommend
features Hermes already has, which embarrasses everyone.

### Phase 2 — Spawn one research subagent per competitor

Use `Agent(subagent_type=general-purpose, run_in_background=true)` and
launch them **in parallel in a single message**. One subagent per
competitor keeps each report focused and reduces the risk of one bad
source bleeding into another. Brief each agent with:

- **Product URLs** (official docs, GitHub repo)
- **A specific feature area list** to investigate (don't leave it open-ended
  — name `repo map`, `hooks`, `sandbox modes`, `recipes`, etc.)
- **The Hermes context** (1 sentence so they can flag relevance)
- **The honesty rule:** unverified claims must be marked unverified; if
  a project is dormant, say so; if a feature can't be found in official
  docs, don't list it.

Required output format per agent:

```
| # | Feature | What it does | Source | Why users love it | Confidence |
```

Plus a short "What stands out" paragraph and a sources block. Cap each
report at 1500 words to keep your context manageable.

### Phase 3 — Disambiguate the obscure ones

If a name is ambiguous (e.g. "OpenHuman" could be the citizen-science
project, OpenHands, or a real new tool), spawn a **dedicated investigation
subagent** whose job is to disambiguate, not to harvest features. Brief it
to:

- Try multiple candidate URLs and search queries
- Distinguish lookalikes by URL, org, and category
- Report **"insufficient evidence"** if it can't find a high-confidence
  match, instead of guessing

Document the disambiguation in `docs/competitive/<name>-research.md` so
future researchers don't repeat the same wild goose chase.

### Phase 4 — Cross-reference with Hermes inventory

For each harvested feature, fill out the master row:

```markdown
| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
```

`Applies to Hermes?` options:
- **Already ships** — cite the Hermes file/skill that covers it
- **Partial** — cite what's missing
- **Gap — high value** — fits Hermes architecture and would beat or match
- **Gap — low value** — fits but not differentiated
- **Out of scope** — Hermes deliberately doesn't go here (e.g. proprietary
  cloud SaaS, IDE plugin)
- **Unverified** — needs follow-up before scoring

### Phase 5 — Emit deliverables

Three files (paths are fixed so the docs system can find them):

1. `docs/competitive/developer-agent-feature-harvest.md` — the full table
   plus per-product "what stands out" notes.
2. `docs/competitive/<name>-research.md` — disambiguation notes for any
   obscure name (one file per name, or one combined file).
3. `docs/product/muse-feature-backlog.md` — only the rows marked
   "Gap — high value", grouped by theme, with proposed implementation
   targets and a one-line rationale.

Update existing files in place — do not create v2 or v3 copies.

## Verification

Before declaring the harvest done:

- [ ] Every row in the master table has a source URL
- [ ] No feature is claimed as "copied to Hermes" unless verified as
      shipped (check git log / `RELEASE_v*.md`)
- [ ] Obscure names (anything not on the top-10 leaderboard) have a
      disambiguation paragraph
- [ ] The backlog is sorted by `(value × leverage) / cost`, not by
      vendor or alphabetic order
- [ ] Anything marked "Already ships" cites the Hermes file or skill
      that proves it
- [ ] At least one row is marked "Out of scope" — if everything looks
      adoptable, you're not being honest about Hermes' deliberate
      choices

## Pitfalls

- **Don't trust the marketing site.** Engineering docs (`docs.*`,
  `github.com/<org>/<repo>/README.md`) beat blog posts. Blog posts beat
  Twitter threads. Twitter threads beat YouTube reviews.
- **A 404'd doc page is not a dead feature.** Many vendor doc sites
  reorganize quarterly. Cross-reference with `llms.txt`, the GitHub
  README, and the release notes before concluding a feature is gone.
- **"Loved" is verifiable too.** Quote the docs' own framing or a
  reputable review. Don't invent user sentiment.
- **Beware lookalikes.** OpenHuman vs OpenHands. Paperclip-the-orchestrator
  vs Paperclip-the-Rails-gem vs paperclip-cli-the-ML-tool. The disambiguation
  phase exists for a reason — skipping it produces wrong recommendations.
- **Don't recommend features Hermes already has.** Phase 1 is non-optional.
  If the inventory subagent missed something, the backlog inherits the
  error.
- **Confidence ratings are load-bearing.** If you mark something `high`
  because the docs say so, the reader will trust it. Reserve `high` for
  features documented on a canonical docs page or in the source code.
- **The harvest is for Hermes.** Features that don't fit Hermes'
  architecture (single-IDE plugins, proprietary SaaS-only flows) belong
  in "Out of scope," not in the backlog.

## Related Skills

- `blogwatcher` — useful for the ongoing "what just shipped?" feed
- `research-paper-writing` — when a competitor releases a paper alongside
  the tool (OpenHands has one), this skill cites it properly
- `requesting-code-review` — when the harvest motivates a PR, this skill
  verifies it before landing
