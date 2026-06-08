# FU-18 — Restate AOS agent count as a routed catalog tally (honesty)

- **Task ID:** FU-18
- **Branch:** `claude/fu-18-aos-honesty`
- **Base commit:** `e1ac6eed95406e90ce8d656a45b767ab865e8a0b` (origin/main)
- **Type:** doc-only (no code, no behavior change)
- **Status:** in-review (draft PR)

## Intent

The AOS Enterprise Council pack advertised "233 registered top-level
agents + 108 sub-agents" in a way that reads as if 341 standalone agent
definition files exist on disk. That is misleading. The 233/108/341
figures are **registry / routed-catalog tallies** (distinct frontmatter
`name:` entries recovered across two source repos, including duplicates,
reconstructed-from-context names, judgement-lens personas, and product
roles), not a per-file count. This task reframes the claim honestly,
non-defensively, and concisely wherever it is stated as fact, without
deleting registries or over/under-claiming.

## Ground truth (verified this pass)

- `registry/AOS_AGENT_REGISTRY_COMPLETE.md` self-describes:
  **"Distinct names registered: 233"** and
  **"Total entries (incl. duplicates across sources): 248"**.
- `registry/AOS_SUBAGENT_REGISTRY_COMPLETE.md` self-describes:
  **"Total sub-agent entries: 108"** (division 79 · worker templates 4 ·
  Python runtime 13 · R-personas 7 · product roles 5).
- `find skills/aos-enterprise-council/agents -name '*.md' | wc -l` = **261**.
- `find skills/aos-enterprise-council/agents/hermes -name '*.md' | wc -l`
  = **177** — the **general Hermes skill library** (`1password.md`,
  `arxiv.md`, `blender-mcp.md`, …), NOT council agents.
- Non-`hermes` agent files = **84** across **16** category folders
  (architecture, business, claude-code, codex, compliance, executive,
  hazmat-command, memory, nourish, product, psychology, qa, release,
  research, security, ux). `hermes` is the 17th folder under `agents/`
  but is the general skill library, not a council category.
- `341` appears only in `AOS_AGENT_RECOVERY_REPORT.md` as the sum of
  registry entries (233 + 108), labeled "TOTAL registry entries".

## Owned (writable) files — touched

- `CLAUDE.md` — the "## AOS Enterprise Council pack" section: replaced
  the "233 registered top-level agents + 108 sub-agents, grouped into 18
  category folders under `agents/`" sentence with honest routed-catalog
  framing (233 roles + 108 sub-agent entries as registry tallies; 261
  files on disk of which 177 are the general `agents/hermes/` library;
  ~84 genuine council agents). Surrounding activation instructions and
  the "source of truth / never improvise" guidance preserved verbatim.
- `AOS_INSTALLATION_REPORT.md` — added a "What the agent counts mean
  (routed catalog, not file count)" note under the Totals table, and a
  clarifying comment on the `find ... agents -name "*.md" | wc -l`
  verification command (explains why it returns ~261, not 341). The
  numeric Totals rows were left unchanged (they are already labeled
  "recovered / distinct / incl. duplicates").
- `AOS_AGENT_RECOVERY_REPORT.md` — added a "Read this 341 as a
  routed-catalog tally, not a file count" note immediately after the
  "TOTAL registry entries = 341" row. The inventory table rows were left
  unchanged (already accurately labeled as registry/entry counts).
- `docs/launch/followups/fu-18-aos-honesty.md` — this snapshot.

## Files NOT touched (deliberately)

- No code files.
- No registry data files under `skills/aos-enterprise-council/registry/`
  (they are the source of truth and already self-describe accurately).
- `docs/launch/10_10_followups_ledger.md` — single-writer; orchestrator
  only.

## Validation

- `uv run ruff check .` — expected clean (no code touched).
- `git diff --stat` — expected to show only the four doc files above.
- CLAUDE.md re-read end-to-end for coherence after the edit.

## Residual risk

- Low. Doc-only, additive framing. The numeric claims now match the
  registries' own self-description and the on-disk file reality. Two
  pre-existing "18 category folders" mentions inside
  `AOS_AGENT_RECOVERY_REPORT.md` (describing the *registry document's*
  internal bucket grouping) were left as-is, since the new note already
  clarifies the on-disk file layout; revisit only if a reader still
  conflates registry buckets with `agents/` subfolders.
