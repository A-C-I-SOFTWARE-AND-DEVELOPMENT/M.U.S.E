# AI Improvement Radar

The AI improvement radar is Hermes' mechanism for tracking — and acting
deliberately on — improvements to the external AI coding tools Hermes
delegates work to. It is a **policy artifact and a workflow**, not a
benchmark or a leaderboard.

This document is the narrative companion to
`skills/ai-improvement-radar/SKILL.md` (the operational skill that
produces radar reports) and to `scripts/hermes-ai-radar.sh` (the local
review hook).

## Why Hermes needs a radar

Hermes is a routing layer. It hands real work off to:

- **Claude Code** (Anthropic) — long-horizon agentic coding
- **Codex** (OpenAI) — autonomous coding CLI
- **Aider** — terminal-based pair programmer
- **Goose** (Block) — local-first agent runner
- **Continue** — IDE-integrated coding assistant
- **OpenHands** — open-source software agent
- **Gemini / Jules / Antigravity-style coding agents** (Google) — emerging
  coding-agent surfaces from Google
- **OpenClaw-style personal agents** — community-built personal coding agents
- Other relevant coding-agent tools as they emerge

Each of these ships independently and frequently. New flags, new
context windows, new pricing, new sandboxing modes, new sub-agent
primitives, new MCP / tool-use semantics. **If Hermes' routing policy
doesn't track those changes, Hermes silently routes work to the wrong
tool** — or misses cheaper, faster, safer options that already exist.

The radar exists so this drift gets surfaced on a regular cadence, with
evidence, instead of as ad-hoc tribal knowledge.

## What the radar tracks

For each tracked tool, the radar watches:

1. **Official release notes / changelogs.** Source of truth for shipped
   behavior.
2. **Official documentation.** Source of truth for supported flags,
   environment variables, output formats, and integration patterns.
3. **Official repositories.** Tags, releases, and commits referenced by
   the changelog. Useful for verifying that a documented feature
   actually shipped.
4. **Reputable engineering sources.** Vendor engineering blogs and
   vendor conference talks count as corroborating evidence, not as
   primary sources.

Things the radar **does not** track:

- Social-media threads, "leaks", or unconfirmed rumors.
- Benchmarks that have not been independently reproduced.
- Subscription-only content that requires bypassing auth.
- Closed-beta features the vendor has asked not to be publicized.

## Cadence

The radar is **on-demand, not scheduled**. Reasonable triggers:

- A user notices that one of the tracked tools has shipped a release.
- Hermes maintainers prepare a routing-policy review.
- A Hermes user files an issue noting that routing decisions seem stale.
- Quarterly hygiene pass, at most.

The radar is deliberately not a cron job. Auto-fetching every day is
how routing drifts toward whatever the noisiest vendor shipped most
recently. Human triggering keeps the cadence aligned with real decision
points.

## Audience

The radar report is written for three readers, in priority order:

1. **A Hermes maintainer doing a routing-policy review.** Needs: the
   actionable features, the evidence, and a recommendation that is
   short enough to act on.
2. **A Hermes user evaluating whether to update their personal
   routing.** Needs: confidence levels, official source URLs, and a
   clear note on what's still unverified.
3. **A future Hermes maintainer auditing why a routing decision was
   made.** Needs: timestamped, source-cited reports kept in
   `.hermes-orchestrator/ai-radar/`.

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  Trigger                                                        │
│    user runs `scripts/hermes-ai-radar.sh`                       │
│    or types `/ai-improvement-radar` inside Hermes               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Script (scripts/hermes-ai-radar.sh)                            │
│    - creates .hermes-orchestrator/ai-radar/ if needed           │
│    - writes <timestamp>-request.json                            │
│    - detects whether `hermes` CLI is on PATH                    │
│    - prints instruction: run `/ai-improvement-radar` in Hermes  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Hermes skill (skills/ai-improvement-radar/SKILL.md)            │
│    - reads request file                                         │
│    - walks tracked-tools list                                   │
│    - fetches official sources only                              │
│    - extracts actionable features                               │
│    - marks unverified claims                                    │
│    - writes <timestamp>-radar.md report                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Human review                                                   │
│    - read radar report                                          │
│    - decide whether to update:                                  │
│        docs/ai-intelligence/model-registry.yaml                 │
│        docs/ai-intelligence/model-routing-policy.md             │
│        docs/ai-intelligence/tool-capability-matrix.md           │
│    - commit changes with the radar report as justification     │
└─────────────────────────────────────────────────────────────────┘
```

## Source-quality rules (operational)

These are the rules the skill enforces. They are duplicated here so
human reviewers can hold the radar accountable to them.

1. **Official-first.** Vendor docs, vendor repos, vendor release notes,
   vendor changelogs.
2. **Reputable engineering blogs count as corroboration, not primary.**
3. **Unverified claims are labeled `unverified`** and parked in the
   "Unverified items (do not act on)" section. They never appear in
   "Implementation recommendation".
4. **Routing policy never changes based on hype.** No "ChatGPT is dead"
   energy. Shipped, documented features only.
5. **Actionable features only.** A radar item must answer the question
   "what would Hermes do differently?". If the answer is "nothing", the
   item doesn't belong in the report.
6. **Subscription apps and auth-gated content are off-limits.** "Gated;
   awaiting public source" is the correct entry.

## Confidence levels

The radar uses four confidence levels for each feature it reports.
Human reviewers should treat them as routing-decision gates.

| Level | Meaning | Routing-decision posture |
|---|---|---|
| **high** | 2+ official sources, or 1 official + Hermes-reproducible local test | Safe to update routing policy |
| **medium** | Single official source, clearly documented, not yet field-tested | Update tool-capability-matrix; defer routing-policy change |
| **low** | Single official source, ambiguous / preview / feature-flagged | Note in matrix as preview; do not change routing |
| **unverified** | Source quality below bar | Do not act; corroborate first |

## Outputs of the radar

The radar writes to three places, each with a different purpose.

### 1. Radar report (per-run, immutable)

`.hermes-orchestrator/ai-radar/<timestamp>-radar.md`

These are the audit trail. They are timestamped, source-cited, and kept
indefinitely. They are the "why" behind any routing change.

### 2. Recommendation queue (per-run, mutable)

`.hermes-orchestrator/ai-radar/<timestamp>-request.json`

What the local script writes when invoked. Includes the requesting
user, the tools requested, and any constraints (`since`, `effort`,
etc.). The skill reads this when it runs.

### 3. Routing policy artifacts (curated, version-controlled)

The radar recommends — but never directly edits — these three
artifacts:

- **`docs/ai-intelligence/model-registry.yaml`** — canonical list of
  models Hermes knows about, with version, context window, pricing
  bracket, and tier.
- **`docs/ai-intelligence/model-routing-policy.md`** — narrative policy
  for which task class routes to which model/tool, with rationale.
- **`docs/ai-intelligence/tool-capability-matrix.md`** — feature matrix
  per coding agent: sandboxing, MCP support, structured output, agent
  primitives, etc.

These three files are the **source of truth** that Hermes routing reads
from. Radar reports are the **evidence** that change them.

## Governance

Two principles govern updates that flow from the radar to the policy
artifacts:

1. **Evidence before action.** No change to the routing artifacts ships
   without a corresponding radar report committed alongside it. If a
   change can't be tied back to a citable radar entry, it's tribal
   knowledge — and tribal knowledge is what the radar exists to
   replace.

2. **Two-track review.** Changes to `model-routing-policy.md` are
   higher-stakes than changes to the capability matrix. Bump the matrix
   from a single-source `medium`-confidence radar entry; require
   `high`-confidence (or maintainer consensus) to bump the routing
   policy itself.

## Anti-patterns

The radar exists to prevent these failure modes, all of which Hermes
has been bitten by in spirit if not in fact:

- **"X just dropped — let's route to it."** No evidence, no test. Don't.
- **"The thread says Y is faster now."** A thread is not a source.
- **Silent drift.** Routing policy edited without a radar entry, so
  nobody six months later knows why.
- **Hype-induced thrash.** Routing policy rewritten every time a vendor
  ships a marketing splash.
- **"Just scrape the dashboard."** No. Subscription apps are off-limits.

## See also

- `skills/ai-improvement-radar/SKILL.md` — the operational skill.
- `scripts/hermes-ai-radar.sh` — the local review hook.
- `docs/ai-intelligence/model-registry.yaml` — *(target; created as
  part of a separate phase)*
- `docs/ai-intelligence/model-routing-policy.md` — *(target; created as
  part of a separate phase)*
- `docs/ai-intelligence/tool-capability-matrix.md` — *(target; created
  as part of a separate phase)*
- `skills/autonomous-ai-agents/claude-code/SKILL.md`
- `skills/autonomous-ai-agents/codex/SKILL.md`
- `skills/autonomous-ai-agents/hermes-agent/SKILL.md`
