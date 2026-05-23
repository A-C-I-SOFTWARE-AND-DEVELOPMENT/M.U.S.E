# Phase 1 Status Report — Claude Agents → Hermes Skills

> **Audit performed on branch `claude/agents-to-hermes-skills-8G17D`.**
> Phase 1's substantive work (skill creation, alias, skill-map doc)
> landed earlier via commit `ef22e2c` ("feat(skills): port AoS
> council agents to Hermes-native skills"). This report verifies the
> result against the Phase 1 brief and records the remaining
> documentation deltas applied on this branch.

## 1. Brief recap

Phase 1 mission: turn every useful `.claude/agents/*.md` agent into an
invokable Hermes skill so the full agent team can be run from inside
Hermes via `/skill-name`, without duplicating any skill already
present and without inventing source agents that do not exist.

## 2. `.claude/agents/` — missing source

Per the [Phase 0 evidence audit](phase-0-evidence-audit.md), this
repository has **no `.claude/` directory at all** — no `agents/`, no
`commands/`. The Phase 1 brief's literal premise ("convert each
`.claude/agents/*.md`") therefore has no source files to convert.

This report records that absence rather than inventing source files
to satisfy the literal phrasing of the brief. The Phase 1 work
proceeded on the alternate path approved by the audit
([§ 9.1](phase-0-evidence-audit.md#9-1-the-premise-mismatch)):
**create the council skills directly under `skills/` with no
`.claude/agents` intermediate layer**.

## 3. Skill inventory — required vs. present

All 16 council specialists, the master orchestrator, and the legacy
alias are present as `SKILL.md` files with valid frontmatter (`name`,
`description`, `version`, `platforms`, `metadata.hermes.tags`,
`metadata.hermes.related_skills`).

| Role | Hermes skill path | Slash command | Status |
|---|---|---|---|
| Master orchestrator | `skills/aos-full-agent-team/SKILL.md` | `/aos-full-agent-team` | Present |
| Director | `skills/aos-council-director/SKILL.md` | `/aos-council-director` | Present |
| Evidence | `skills/evidence-architect/SKILL.md` | `/evidence-architect` | Present |
| Architecture | `skills/principal-systems-architect/SKILL.md` | `/principal-systems-architect` | Present |
| Product | `skills/product-experience-architect/SKILL.md` | `/product-experience-architect` | Present |
| Commercial | `skills/commercial-strategist/SKILL.md` | `/commercial-strategist` | Present |
| Risk | `skills/assurance-risk-director/SKILL.md` | `/assurance-risk-director` | Present |
| Delivery | `skills/delivery-scope-controller/SKILL.md` | `/delivery-scope-controller` | Present |
| Contrarian | `skills/contrarian-reviewer/SKILL.md` | `/contrarian-reviewer` | Present |
| Contrarian (alias) | `skills/contrarian-red-flag-analyst/SKILL.md` | `/contrarian-red-flag-analyst` | Present (alias-only) |
| Dispatch | `skills/codex-dispatch-governor/SKILL.md` | `/codex-dispatch-governor` | Present |
| Routing | `skills/model-router/SKILL.md` | `/model-router` | Present |
| Publishing | `skills/github-publisher/SKILL.md` | `/github-publisher` | Present |
| DX | `skills/developer-ux-command-center/SKILL.md` | `/developer-ux-command-center` | Present |
| Gate | `skills/decision-quality-gate/SKILL.md` | `/decision-quality-gate` | Present |
| Validation | `skills/research-validator/SKILL.md` | `/research-validator` | Present |
| Retro | `skills/self-improvement-loop/SKILL.md` | `/self-improvement-loop` | Present |
| Radar | `skills/ai-improvement-radar/SKILL.md` | `/ai-improvement-radar` | Present |

No duplicate skills were created on this branch.

## 4. Slash-command exposure

`agent/skill_commands.py:scan_skill_commands()` walks
`~/.hermes/skills/` (seeded from `skills/`) and registers a
`/<name>` slash command per SKILL.md `name:` field. Every council
skill above has a `name:` field that matches its directory, so all
18 slash commands above are picked up automatically by both the
CLI (`cli.py`) and the gateway (`gateway/run.py`) — no core code
change required, and no behavior is hardcoded into Hermes core.

## 5. Master skill — orchestration coverage

`skills/aos-full-agent-team/SKILL.md` enumerates and sequences all
16 specialists plus the alias in its `metadata.hermes.related_skills`
list and in the canonical-sequence table. The wrapper:

1. Reads the user's goal verbatim
2. Persists the brief under `aos/council/<slug>` in `memory`
3. Installs the council `todo` list
4. Invokes `aos-council-director` via `delegate_task`
5. The Director then fans out to the rest via `delegate_task`

This matches the Phase 1 brief's "should orchestrate" list one-for-one.

## 6. Naming-drift fix — Phase 1 brief vs. reality

The Phase 1 brief instructs:

> If CLAUDE.md references `contrarian-red-flag-analyst` but the repo
> has `contrarian-reviewer.md`, update CLAUDE.md to use
> `contrarian-reviewer`.

Verified on this branch: **`CLAUDE.md` does not reference either
name**. `grep -n "contrarian" CLAUDE.md` returns no matches. No
CLAUDE.md edit is therefore needed.

The brief also says:

> Optionally add alias skill: `skills/contrarian-red-flag-analyst/SKILL.md`

The alias skill exists. It carries `name: contrarian-red-flag-analyst`,
forwards to `contrarian-reviewer` via a `read_file` redirect, and
explicitly tells implementations to persist findings under the
canonical memory key (`aos/council/<slug>/contrarian`) so the audit
trail is not split.

## 7. Skill-map doc — present

`docs/orchestration/hermes-agent-skill-map.md` contains the canonical
mapping (`Claude agent → Hermes skill path → slash command name →
purpose`) for the master and all 16 specialists + alias. It also
documents the memory layout (`aos/council/<slug>/...`) and the
Hermes-native tools each specialist uses.

## 8. AGENTS.md alignment — applied on this branch

`AGENTS.md` previously described `aos-full-agent-team` as "spawns
the standard planner / builder / reviewer / architect roles", which
is the Phase 02 orchestration-pipeline description, not the Phase 03
AoS-council reality. This branch updates the AGENTS.md
"Orchestration pipeline skills" table to:

- Correct the `aos-full-agent-team` row to reflect the 16-specialist council
- Add rows for the 9 council-specific specialists not previously listed (`aos-council-director`, `evidence-architect`, `principal-systems-architect`, `product-experience-architect`, `commercial-strategist`, `assurance-risk-director`, `delivery-scope-controller`, `contrarian-reviewer`, `codex-dispatch-governor`)
- Point to `docs/orchestration/hermes-agent-skill-map.md` from the companion-docs list
- Add new slash invocations (`/aos-council-director`, `/research-validator`, `/contrarian-reviewer`, `/self-improvement-loop`) to the invocation summary

## 9. What this branch does NOT change

- No SKILL.md files were rewritten on this branch — every existing
  council skill already satisfies the Phase 1 quality bar (name,
  description, when-to-use, workflow, tool list, output contract,
  quality criteria, "don't" list).
- No new aliases were invented beyond the existing
  `contrarian-red-flag-analyst` legacy alias.
- No `.claude/agents/*.md` files were created — Phase 0 already
  established that the alternate path (skills-only) is the chosen
  Hermes way and the Phase 1 brief explicitly says "If a
  `.claude/agents` file is missing, record that instead of inventing
  it."

## 10. Result

Phase 1 — Convert all Claude agents into Hermes skills: **complete**.

- 16 council specialists ✓
- Master orchestrator (`aos-full-agent-team`) ✓
- Legacy alias (`contrarian-red-flag-analyst`) ✓
- Skill-map doc (`docs/orchestration/hermes-agent-skill-map.md`) ✓
- AGENTS.md aligned with the skill-map ✓
- No CLAUDE.md drift to fix ✓
- No duplicate skills created ✓
