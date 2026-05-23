---
name: competitive-feature-harvester
description: "Research competing AI agents and harvest verified, user-loved features that could improve Hermes."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, competitive, planning, product, agents]
    related_skills: [research/blogwatcher, research/arxiv]
---

# Competitive Feature Harvester

A repeatable workflow for surveying competing agent products (OpenHuman, Paperclip, OpenHands, Aider, Continue, Goose, Claude Code, Codex, OpenClaw, and similar) and converting **verified** feature claims into Hermes-relevant proposals.

The rule that matters: **only record claims that are tied to a primary source.** If a fact cannot be sourced to an official repo, doc site, release note, or first-party blog post, mark it `unverified` and stop using it as a recommendation.

## When to use

- A new agent product is making noise and you want to know what it actually ships, separated from marketing.
- You're planning a Hermes release and want a structured "what should we steal" list.
- You're updating `docs/competitive/` so reviewers can audit feature decisions later.

## Inputs

1. A list of products to study (default set is below — extend per request).
2. Optional focus area (e.g. "memory", "messaging gateways", "skill systems"). When empty, do a full harvest.
3. Output directory (default: `docs/competitive/`).

Default target set: `OpenHuman`, `Paperclip`, `OpenHands`, `Aider`, `Continue`, `Goose`, `Claude Code`, `Codex`, `OpenClaw`. Add comparable developer/local-agent tools whenever they are plausibly relevant.

## Workflow

### Phase 1 — Source discovery

For every product, hunt for these primary sources in order:

1. **GitHub repository README** (`github.com/<org>/<repo>`).
2. **Official documentation site** (linked from README).
3. **Official product/landing page**.
4. **Release notes / changelog / blog**.
5. **App store / package registry listing** when applicable.

Use `WebSearch` to locate, then `WebFetch` to read. Capture the canonical URL — not aggregator/review/SEO pages.

```text
WebSearch  "<product> features site:<official-domain>"
WebSearch  "<product> github"
WebSearch  "<product> release notes <current-year>"
WebFetch   <discovered-url>  "list every shipped feature, quote verbatim, note license + last release date"
```

Treat aggregator reviews, "Top 10 AI agents" articles, and AI-generated blog posts as **leads, not sources**. They frequently hallucinate features that the official docs do not back up.

### Phase 2 — Verify each claim

For each candidate feature, before recording it:

1. Find at least one primary source that asserts the feature (README, docs, release notes, or first-party blog).
2. Note the **exact URL** and the **quoted phrase** that supports the claim.
3. If only secondary sources mention it, mark `confidence: unverified` and do not recommend implementing it.
4. If the feature is described inconsistently across sources, record the disagreement.

Confidence ladder:

| Confidence | Meaning |
|---|---|
| `high` | Documented in official repo/docs/release notes with a direct quote. |
| `medium` | Mentioned consistently across official sources but with weaker specifics, or only in a blog post by the maintainers. |
| `low` | Plausible from official sources but partly inferred. |
| `unverified` | Only found in third-party reviews, AI-generated articles, or hearsay. **Do not recommend.** |

### Phase 3 — Map to Hermes

For each verified feature, decide:

- **Already in Hermes?** Cross-check `README.md`, `skills/`, `plugins/`, `cli.py`, `mcp_serve.py`, and `gateway/`. If yes, note the existing implementation and skip.
- **Applies to Hermes?** Yes / No / Partial — with one-line reason. A feature that requires a desktop mascot may not apply; a 20-minute OAuth poll loop probably does.
- **Implementation target.** Name the directory and approximate component (e.g. `plugins/google_meet`, `cron/`, new `gateway/budget.py`).

### Phase 4 — Write artefacts

Two files always, plus per-product deep dives when warranted:

1. `docs/competitive/<product>-research.md` (or `<a>-<b>-research.md` when paired) — primary-source notes for that product. Quote-heavy, URL-heavy.
2. `docs/competitive/developer-agent-feature-harvest.md` — the master table across all products. Append new rows; do not rewrite history.

The master table schema:

```markdown
| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
```

Rules for table rows:

- One row per feature, not per product.
- `Source` is a markdown link to the primary URL, not a search result.
- `User-loved reason` is the *why*. If you cannot find a why in a user's voice, write "(no user testimony found)" rather than inventing one.
- `Applies to Hermes?` is `Yes`, `No`, or `Partial: <reason>`.
- `Implementation target` names a real path in this repo or is `n/a` if the feature does not apply.
- `Confidence` uses the ladder above.

### Phase 5 — Recommend

At the bottom of `developer-agent-feature-harvest.md`, write a short "Recommended for Hermes" section listing only features with `confidence: high` or `medium` that have `Applies to Hermes? = Yes/Partial`. Group by implementation surface (gateway, skills, memory, scheduling, governance, UI).

Never recommend `unverified` features. Never recommend duplicates of things Hermes already ships.

## Output contract

Each research file must contain:

- A `## Sources` section listing every URL fetched.
- For each feature claimed, a verbatim quoted phrase or paraphrase tied to a URL.
- An honest gap list ("the docs do not say whether X works offline").

If after best effort a product has no primary sources you can fetch, the deliverable for that product is one line: `unverified / insufficient evidence` — and that's the answer. Do not pad.

## Anti-fabrication checklist

Before committing:

- [ ] Every feature row links to a primary source URL.
- [ ] No row uses a fabricated quote.
- [ ] No row infers a feature from product category alone.
- [ ] AI-generated review sites are not cited as sources.
- [ ] When two sources disagree, both are noted.
- [ ] Star counts, release dates, and licenses came from the repo itself, not a paraphrase.

## Refresh cadence

Re-run this skill when:

- A target product cuts a major release.
- A new comparable product gains traction (>10k GitHub stars in a quarter, or sustained discussion in developer-tools spaces).
- Hermes planning needs an updated competitive view (before each release-train kickoff).

Old rows stay; add a `Last verified: YYYY-MM-DD` column entry rather than silently mutating prior findings.
