# AI Improvement Radar

The AI Improvement Radar keeps Hermes informed about the state of the
AI coding tool ecosystem - the peers, alternatives, and upstream
backends Hermes routes work to. The radar runs on a cadence and on
demand. Its output drives changes to the model registry and routing
policy.

## Why Hermes needs a radar

Hermes is a router and orchestrator first. If the underlying tool
landscape moves and Hermes does not notice, routing decisions stale
fast: jobs get sent to a worker that has lost ground, or a new
capability (longer context, cheaper tokens, better sandbox) is left on
the table.

The radar exists to make sure that does not happen quietly.

## Tracked products

The radar tracks - at minimum - the following families. Add new ones
as they emerge.

| Family | Examples |
|---|---|
| Hosted CLIs | OpenAI Codex CLI, Claude Code, Google Gemini CLI |
| Hosted agents | Anthropic Claude Agent SDK, OpenAI Responses API |
| Open-source agents | Aider, Goose (Block), OpenHands |
| IDE-bundled agents | Cursor, Windsurf, Zed agentic modes, Continue |
| Local-first | OpenClaw-like tools, llama.cpp-driven coders |
| Autonomous agents | Jules-style background workers |

For each tracked product the radar records:

- Latest stable version and release date.
- Default model and supported model families.
- New capabilities since the last report.
- Deprecated or removed capabilities.
- Pricing or quota changes that affect routing economics.
- Known regressions, especially anything that breaks tool use, sandbox
  isolation, or sub-agent dispatch.

## Provenance and verification

Every claim in a radar report must carry a verification tag:

- `verified` - confirmed against an official primary source (vendor
  docs, GitHub release page, official changelog) within the last 14
  days.
- `unverified` - heard or inferred, no primary source on hand.
- `stale` - was verified in the past but the source has not been
  re-checked within the freshness window.

Reports that are produced without network access are labeled
`offline-snapshot` and should be treated as a baseline, not a fresh
truth.

## How to run the radar

The radar has two entry points:

1. **Shell script** for the offline baseline:

   ```
   scripts/hermes-ai-radar.sh           # offline snapshot (default)
   scripts/hermes-ai-radar.sh --online  # request a refresh
   scripts/hermes-ai-radar.sh --dry-run # show what would be written
   ```

   The shell script never calls the network itself. Even with
   `--online`, the script only writes the report skeleton and marks
   the run as having requested fresh data; an agent with the
   `WebFetch` / `WebSearch` tools is responsible for filling in
   primary-source updates.

2. **Skill** for the full pipeline:

   The `ai-improvement-radar` skill (see
   `skills/ai-improvement-radar/SKILL.md`) is the procedure an agent
   loads when asked to refresh the radar. It coordinates source
   collection, comparison against the current model registry, and
   recommendations.

## Output contract

Each radar run produces:

- `docs/ai-intelligence/ai-improvement-radar.md` (this file's
  companion "latest" report - the shell script writes the skeleton
  here).
- `docs/ai-intelligence/history/YYYY-MM-DD-radar.md` - the dated
  archival copy.

Both files use the same template:

```
# AI Radar - <ISO date>
Mode: online | offline-snapshot
## Tracked products
## Per-product status
## Routing patches recommended
## Open questions
## Provenance
```

## What the radar may recommend

The radar can recommend - but never apply on its own:

- New rows in the model registry (`scripts/build_model_catalog.py`).
- Routing-policy edits (priority shifts, sandbox-required gates,
  budget-aware routes).
- New entries in the skill index when a worker now has a capability
  Hermes did not previously dispatch.
- Demotion or removal of a worker that has consistently lost
  retrospectives recorded by the `self-improvement-loop` skill.

All recommendations land in a PR. The operator approves before any
routing change ships.

## Hard rules

- ASCII only.
- Offline safe by default.
- No network calls without an explicit `--online` flag (script) or
  explicit tool availability (skill).
- No third-party telemetry of radar runs.

## Related docs

- `docs/orchestration/self-improvement-loop.md` - per-job retros that
  feed the radar.
- `docs/mission/best-coding-tool-mission.md` - the north star both
  loops serve.
