# AOS Agent Recovery Report

> **Pass:** branch `claude/aos-agent-recovery-hermes-jmocw` · 2026-05-24 · scope-corrected execution per `/root/.claude/plans/pause-and-correct-scope-cozy-wirth.md`.

## Goal

Discover, recover, organize, and install the entire AOS / AEO / Hermes / Claude / Codex / enterprise smart-team system. Original brief at the top of this session.

## What was searched

- `/home/user/hermes-agent/` — full Hermes Agent codebase (live repo).
- `/home/user/hazmat-command/` — full HazMat Command codebase (live repo).
- `/home/user/hermes-agent/recovered-agent-sources/` — the 186-file snapshot of hazmat AOS material + hermes AOS skills copied in the first pass.

Methods: direct file enumeration (`find`), grep across both repos for `subagent / sub-agent / council / orchestrator / specialist / persona / role: / agent: / worker_profile / delegate_task / AEO / AOS / psychology / claude-code / codex / hazmat / nourish / Hermes skill`, awk-based YAML frontmatter extraction across every SKILL.md and agent .md.

## What was found (counts)

| Surface | Count |
| --- | --- |
| Hermes-agent live `skills/**/SKILL.md` | 120 |
| Hermes-agent live `optional-skills/**/SKILL.md` | 81 |
| **Hermes-agent SKILL.md total** | **201** |
| Hermes-agent `docs/orchestration/**/*.md` | 35 |
| Hermes-agent `enterprise/**/*.py` | 13 |
| Hazmat (snapshot) `.claude/agents/` | 11 |
| Hazmat (snapshot) `.claude/skills/` | 21 |
| Hazmat (snapshot) `.claude/rules/` | 7 |
| Hazmat (snapshot) `docs/agents/` (division docs) | 11 |
| Hazmat (snapshot) `docs/governance/` | 19 |
| Hazmat (snapshot) `docs/workflows/` | 12 |
| Hazmat (snapshot) `docs/skills/` | 41 |
| Hazmat (snapshot) `docs/templates/` | 22 |
| Recovered hermes-side SKILL.md (snapshot) | 17 |
| **Snapshot total (all files)** | **166** |
| **Total SKILL.md / agent .md frontmatter entries** | **248** |
| **Distinct named agents** (frontmatter `name:`) | **233** |
| **Division sub-agents extracted from hazmat docs/agents** | **79** |
| Hermes orchestration worker-profile templates | 4 |
| Hermes Python runtime worker modules | 13 |
| R-code personas (judgement lenses) | 7 |
| HazMat product roles | 5 |
| **TOTAL registry entries (top-level agents + sub-agents)** | **341** |

> **Read this 341 as a routed-catalog tally, not a file count.** Every row
> above counts *registry entries* — distinct frontmatter `name:` entries
> recovered across both source repos, including duplicates (248 vs 233
> distinct top-level), reconstructed-from-context names, judgement-lens
> personas, and product roles. It is **not** 341 standalone agent
> definition files. On disk the installed pack's
> `skills/aos-enterprise-council/agents/` holds **261** `.md` files, of
> which **177 are the general `agents/hermes/` skill library**
> (`1password.md`, `arxiv.md`, …), not council agents — leaving **~84**
> genuine council category agents across the 16 non-`hermes` category
> folders. The registries route to specs that may be inline,
> reconstructed, or shared with the general skill library, so the catalog
> tally is intentionally larger than the per-agent file set.

## What was created

### Repo-root recovery artifacts
- `AOS_FULL_SOURCE_INVENTORY.md` — 456-row file index across every relevant source.
- `AOS_AGENT_REGISTRY_COMPLETE.md` — 233 distinct named top-level agents grouped into 18 category folders × canonical/aliases/mentioned buckets.
- `AOS_SUBAGENT_REGISTRY_COMPLETE.md` — 108 sub-agents (division: 79, worker templates: 4, Python runtime: 13, R-personas: 7, product roles: 5).
- `AOS_PROMPT_LIBRARY_COMPLETE.md` — every prompt template across both repos.
- `AOS_WORKFLOW_LIBRARY_COMPLETE.md` — every workflow / SOP / orchestration doc.
- `AOS_MEMORY_AND_CONTEXT_RECOVERY.md` — memory backends, namespaces, artifact persistence policy.
- `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` — every cross-source name duplicate + the hazmat↔hermes role overlap map.
- `AOS_AGENT_RECOVERY_REPORT.md` — this file.
- `AOS_INSTALLATION_REPORT.md` — exact Termux install + verification commands.

### Hermes skill pack at `skills/aos-enterprise-council/`
- `SKILL.md` — activation surface (rewritten to reference the registries).
- `README.md` — install + use.
- `registry/` — copies of the 5 registry files.
- `agents/<18 category folders>/` — per-category agent .md files (canonical synthesized layer over recovered specs).
- `prompts/` — copy-paste prompts.
- `workflows/` — Council Mode + audit + release workflows.
- `rules/` — 7 hazmat rules (copied).
- `templates/` — 22 hazmat templates (expanded from 7 to all).
- `source-snapshots/MANIFEST.md` — pointer into `recovered-agent-sources/`.

### Preserved sources (never deleted)
- `recovered-agent-sources/from-hazmat-command/` (146 files)
- `recovered-agent-sources/from-hermes-agent/` (20 files)
- `recovered-agent-sources/MANIFEST.md` — comprehensive manifest.

### Constitutional pointer additions
- `AGENTS.md` — ≤30-line "Recovered AOS Enterprise Council Pack" section appended at the end. Existing 1279-line content untouched.
- `CLAUDE.md` — ≤20-line companion pointer appended at the end. Existing content untouched.

## What is missing / needs manual review

- **Nourish division** — no canonical `nourish-*` spec found in either repo. The `nourish-product-specialist.md` in this pack is `RECONSTRUCTED FROM CONTEXT` and labeled `NEEDS USER REVIEW`. When the `echerd27-design/Nourish-` repo is mounted, re-run the recovery pass against it to refresh.
- **Psychology division** — only `psychology-ux-agent.md` exists (synthesized). The owner should clarify whether the Psychology division is a distinct branch or a lens inside the UX division.
- **R-personas (R1-D through R5-V)** — recovered as names + descriptions only. Full prompt text for each persona was not in any spec; they live as authorship labels on prior sprints.
- **`agent/worker_profiles/` directory** — referenced by the hermes inventory agent as "INFERRED — not enumerated in directory listing". Existence not confirmed; needs verification.
- **Two Explore subagents in the inventory phase tripped a hallucinated "CRITICAL no-tool" stop** mid-run, likely from reading hazmat constitutional language. The main session worked around this by doing the inventory directly. This is a pattern to watch in future recovery passes.

## Source recovery anomaly to note

The `.gitignore` line 23 (`hermes-*/*`) silently swallows everything under any `hermes-*` directory. The first-pass scaffold (which the owner correctly rejected) was placed at `hermes-skills/aos-enterprise-council/` — those files exist on disk but would never have committed. The corrected pack lives at `skills/aos-enterprise-council/` (the canonical tracked Hermes skill path, alongside the existing `aos-council-director`, `aos-full-agent-team`, `enterprise-council`, `autonomous-ai-agents` skill folders).
