# M.U.S.E. Skill Map — AoS Council

This doc maps every AoS (Architecture of Solutions) council role to its
M.U.S.E. skill on disk, its slash command, and its purpose. It is the
canonical index for the Phase 03 conversion that brought the council
into M.U.S.E. as native skills (no `.claude/agents/` dependency).

M.U.S.E. scans skills under `~/.hermes/skills/` (seeded from
`skills/` at install time). Slash commands are derived from each skill's
`name:` field via `agent/skill_commands.py` — `name: foo` becomes `/foo`.

## Master orchestrator

| Claude agent (upstream) | M.U.S.E. skill path | Slash command | Purpose |
|---|---|---|---|
| `aos-full-agent-team` | `skills/aos-full-agent-team/SKILL.md` | `/aos-full-agent-team` | Spin up the full 16-specialist council end-to-end against one goal. Wraps `aos-council-director` with the canonical sequence and the audit-trail root. |

## Council specialists (16)

| Claude agent (upstream) | M.U.S.E. skill path | Slash command | Purpose |
|---|---|---|---|
| `aos-council-director` | `skills/aos-council-director/SKILL.md` | `/aos-council-director` | Decomposes the goal, dispatches specialists, integrates findings, produces the decision-of-record. |
| `evidence-architect` | `skills/evidence-architect/SKILL.md` | `/evidence-architect` | Builds the evidence base — structured claims with file / session / external provenance. |
| `principal-systems-architect` | `skills/principal-systems-architect/SKILL.md` | `/principal-systems-architect` | Owns technical architecture: components, interfaces, data flow, trade-offs, non-goals. |
| `product-experience-architect` | `skills/product-experience-architect/SKILL.md` | `/product-experience-architect` | Owns product / UX: user segments, jobs-to-be-done, journey, breakage modes. |
| `commercial-strategist` | `skills/commercial-strategist/SKILL.md` | `/commercial-strategist` | Owns commercial axis: market, pricing, GTM, moat, commercial risks. |
| `assurance-risk-director` | `skills/assurance-risk-director/SKILL.md` | `/assurance-risk-director` | Owns risk: safety, security, privacy, legal, reputation. Holds a non-silent veto. |
| `delivery-scope-controller` | `skills/delivery-scope-controller/SKILL.md` | `/delivery-scope-controller` | Owns delivery shape: in/out of scope, slices, dependencies, critical path, slip signals. |
| `contrarian-reviewer` | `skills/contrarian-reviewer/SKILL.md` | `/contrarian-reviewer` | Devil's advocate; produces red-flag report with falsifiers. Always runs before the quality gate. |
| `contrarian-red-flag-analyst` *(alias)* | `skills/contrarian-red-flag-analyst/SKILL.md` | `/contrarian-red-flag-analyst` | Legacy alias that resolves to `contrarian-reviewer`. Same playbook, single canonical memory key. |
| `codex-dispatch-governor` | `skills/codex-dispatch-governor/SKILL.md` | `/codex-dispatch-governor` | Builds handoff packets for in-M.U.S.E. subagents, external coding agents (Codex/Claude Code/Cursor), or the Android manual workflow. |
| `model-router` | `skills/model-router/SKILL.md` | `/model-router` | Picks the inference model per task: primary, fallback chain, cost band, latency band, do-not-use list. |
| `github-publisher` | `skills/github-publisher/SKILL.md` | `/github-publisher` | Publishes the decision-of-record to GitHub: PRs, issues, review comments. Uses `plugins/github/` first; falls back to `gh`; finally to draft-only. |
| `developer-ux-command-center` | `skills/developer-ux-command-center/SKILL.md` | `/developer-ux-command-center` | Owns developer ergonomics: CLI / TUI / gateway / slash / docs / error messages / discoverability. |
| `decision-quality-gate` | `skills/decision-quality-gate/SKILL.md` | `/decision-quality-gate` | Final gate. Verifies completeness, coherence, traceability. Emits `pass | conditional | fail`. |
| `research-validator` | `skills/research-validator/SKILL.md` | `/research-validator` | Fact-checks claims against their cited sources. Verified / failed / unverifiable-from-this-seat. |
| `self-improvement-loop` | `skills/self-improvement-loop/SKILL.md` | `/self-improvement-loop` | Inward retro: proposes concrete diffs to the council's SKILL.md files from session outcomes. |
| `ai-improvement-radar` | `skills/ai-improvement-radar/SKILL.md` | `/ai-improvement-radar` | Outward scan: model / tool / framework / provider radar entries with stance and next action. |

## Memory layout

Every council session writes under a single deterministic memory root:

```
aos/council/<slug>/
    brief                                # the goal + working assumptions
    evidence                             # evidence pack from evidence-architect
    findings/
        principal-systems-architect
        product-experience-architect
        commercial-strategist
        developer-ux-command-center
        assurance-risk-director
        delivery-scope-controller
        model-router
    dispatch/
        <slice-id>                       # one handoff packet per slice
    validation                           # research-validator's report
    contrarian                           # contrarian-reviewer's red-flag report
    quality_gate                         # decision-quality-gate verdict
    decision                             # the decision-of-record
    publication                          # github-publisher receipt
```

Retrospectives live under `aos/retro/<slug>`. Radar entries under
`aos/radar/<yyyy-mm>/<slug>`. The `decision-quality-gate` refuses to
pass if the required keys under `aos/council/<slug>/` are missing.

## Hermes-native tools the council uses

The council only references tools that M.U.S.E. ships natively. No
Claude-Code-only assumptions remain.

| Tool | Used by | What for |
|---|---|---|
| `read_file` | Every specialist | Load brief, evidence, prior findings, source files |
| `search_files` | Every specialist | Locate files referenced obliquely in briefs |
| `terminal` | Architect / risk / publisher / DX | Read-only inspection (`git log`, `gh`, `muse --help`) |
| `process` | Architect | Inspect running processes (read-only) |
| `patch` | Director only (writing the final decision-of-record file when the user asks) | Surgical file edits |
| `write_file` | Director, publisher | Write decision-of-record or PR-body files when asked |
| `todo` | Director, full-team wrapper, delivery | Track council steps and slices |
| `memory` | Every specialist | Persist briefs, findings, gate results — single audit trail |
| `session_search` | Every specialist | Recall prior turns and prior council outcomes |
| `execute_code` | Architect (throwaway spikes only) | Disposable feasibility experiments |
| `delegate_task` | Director, full-team, codex-dispatch-governor | Dispatch specialists and external handoffs |

## Naming-drift notes

- Upstream documents (any `.claude/agents/` source you may merge in
  later) referred to the contrarian role as
  `contrarian-red-flag-analyst`. The canonical M.U.S.E. name is
  `contrarian-reviewer`. The alias skill
  `skills/contrarian-red-flag-analyst/SKILL.md` exists purely to keep
  references resolvable; it persists no findings of its own and points
  back to the canonical playbook.

## Where to add a new specialist

1. Create `skills/<name>/SKILL.md` with the standard frontmatter
   (`name`, `description ≤ 60 chars`, `version`, `author`, `license`,
   `platforms`, `metadata.hermes.tags`, `metadata.hermes.related_skills`).
2. Add the row to both tables above.
3. Add the slot to the canonical sequence in
   `skills/aos-full-agent-team/SKILL.md`.
4. Add the memory key under the layout above.
5. Update the `decision-quality-gate` checks if the new specialist is
   load-bearing for `pass`.
