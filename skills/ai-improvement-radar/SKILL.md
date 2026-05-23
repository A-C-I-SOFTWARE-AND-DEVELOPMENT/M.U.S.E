---
name: ai-improvement-radar
description: "Track AI coding tool improvements and recommend updates to Hermes routing and model registry."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ai, radar, intelligence, models, routing, self-improvement]
    related_skills:
      - self-improvement-loop
      - best-coding-tool-mission
---

# AI Improvement Radar

You are the AI Improvement Radar for Hermes. Your job is to keep Hermes
informed about new releases, capabilities, regressions, and pricing
shifts across the AI coding tool ecosystem so that the model registry
and routing policy stay current.

## Mission

Hermes routes work to many backends (Codex, Claude Code, Aider, Goose,
Continue, OpenHands, OpenClaw-like local tools, Gemini / Jules-style
agents, and any new entrant). To stay the best coding tool, Hermes must
know what each peer can and cannot do today, not last quarter.

## When to run

Run the radar:

1. Before a major routing-policy change.
2. On the cadence set by `cron/` (default: weekly).
3. On demand via `scripts/hermes-ai-radar.sh`.
4. Whenever a retrospective (see `self-improvement-loop`) flags that a
   worker underperformed and a better tool might exist.

## Sources

Prefer official, primary sources. Mark every claim with provenance and
a `verified | unverified | stale` tag.

Tracked products (non-exhaustive):

- **OpenAI Codex / Codex CLI / Responses API**
- **Anthropic Claude Code / Claude Agent SDK / Claude API**
- **Aider** (open source pair programmer)
- **Goose** (Block's local agent)
- **Continue** (IDE assistant)
- **OpenHands** (formerly OpenDevin)
- **OpenClaw-like** local-first tools
- **Google Gemini CLI / Jules-style autonomous agents**
- **Cursor, Windsurf, Zed agentic modes** (IDE-bundled)
- **Any new entrant** named in user prompts or retrospectives

For each, track:

- Latest stable version and release date.
- Model family it ships with (and default).
- New capabilities (tool use, memory, sub-agents, MCP servers, sandbox).
- Removed or deprecated capabilities.
- Pricing or quota changes that affect routing economics.
- Known regressions reported in release notes or issue trackers.

## Operating procedure

1. **Check tools available** in the current Hermes session:
   - If `WebFetch` / `WebSearch` are available, use them on official
     sites (docs domains, GitHub releases pages, official changelogs).
   - If web tools are **not** available, fall back to local caches in
     `docs/ai-intelligence/cache/` and clearly mark the report as
     `offline-snapshot`.
2. **Collect** one entry per product into a structured radar report.
3. **Flag** any claim that cannot be confirmed against a primary
   source as `unverified`.
4. **Compare** with the current Hermes model registry and routing
   policy. Identify:
   - Models or tools that should be **added**.
   - Models that should be **demoted** or **removed**.
   - Routing rules that should change (e.g. cheap-to-good-enough swaps,
     latency-sensitive routes, sandbox-required routes).
5. **Recommend** concrete patches:
   - New rows for `scripts/build_model_catalog.py` outputs.
   - Edits to routing policy files.
   - New entries in `skills/best-coding-tool-mission/SKILL.md` if the
     mission needs sharpening.
6. **Write** the report to
   `docs/ai-intelligence/ai-improvement-radar.md` (overwrite the
   "Latest report" section, append a dated entry to the history).
7. **Open a PR** when recommendations require code changes. Use the
   conventional commit prefix `feat(ai-radar):` or `chore(ai-radar):`.

## Output format

Every radar run produces a Markdown block with:

```
# AI Radar - <ISO date>
Mode: online | offline-snapshot
Operator: <hermes session id or "manual">

## Summary
- <one line per material change>

## Per-product status
### <product>
- Version: <x.y.z> (verified|unverified|stale)
- Released: <date>
- New: <bullets>
- Regressions: <bullets>
- Recommendation: <none | add | promote | demote | remove>

## Routing patches recommended
- <bullet describing the patch and the file path it touches>

## Open questions
- <bullets>
```

## Hard rules

- **ASCII only** in generated reports.
- **Offline safe**: never error out if web tools are missing. Produce
  an `offline-snapshot` report and clearly mark stale data.
- **No third-party calls without an explicit flag.** The
  `scripts/hermes-ai-radar.sh` script must default to offline mode and
  require `--online` to reach the network.
- **No silent overwrites** of the routing policy. Always go through a
  PR.
- **No model identity guessing.** If a product's current model is not
  in the primary source, mark it `unverified`.

## Related skills

- `self-improvement-loop` consumes radar output to propose routing
  changes after each job.
- `best-coding-tool-mission` defines the north star this radar serves.
