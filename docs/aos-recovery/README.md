# AOS Recovery — `docs/aos-recovery/`

**Canonical home** of the 9 AOS recovery registries / reports
(formerly mirrored at the repo root; the root copies were removed in
the Wave-D root tidy and this directory is now the source of truth).

The registries-inside-the-Hermes-pack at
`skills/aos-enterprise-council/registry/` are a second, intentional
mirror, kept so the pack is self-contained when installed into
`~/.hermes/skills/`.

## Files in this directory

| File | What it is |
| --- | --- |
| `AOS_FULL_SOURCE_INVENTORY.md` | One row per file scanned across both source repos plus the snapshot. |
| `AOS_AGENT_REGISTRY_COMPLETE.md` | 233 distinct top-level agents × 18 categories × canonical/aliases/mentioned buckets. |
| `AOS_SUBAGENT_REGISTRY_COMPLETE.md` | 108 sub-agents (79 division specialists + 4 worker templates + 13 Python runtime workers + 7 R-personas + 5 product roles). |
| `AOS_PROMPT_LIBRARY_COMPLETE.md` | Every prompt template across both repos. |
| `AOS_WORKFLOW_LIBRARY_COMPLETE.md` | Every workflow + Council Mode 16-stage canonical sequence. |
| `AOS_MEMORY_AND_CONTEXT_RECOVERY.md` | Memory backends, namespace conventions, source-of-truth hierarchy. |
| `AOS_DUPLICATE_AND_CONFLICT_REPORT.md` | Every cross-source name duplicate + hazmat↔hermes role overlap map. |
| `AOS_AGENT_RECOVERY_REPORT.md` | Narrative: what was searched / found / created / missing. |
| `AOS_INSTALLATION_REPORT.md` | Termux install + verification commands. |

## Source canonical copies

- Repo root: `/AOS_*.md`
- Hermes pack: `/skills/aos-enterprise-council/registry/*.md`

## How to re-sync if these drift

```bash
cd $(git rev-parse --show-toplevel)
cp AOS_*.md docs/aos-recovery/
cp AOS_*.md skills/aos-enterprise-council/registry/
git diff --stat docs/aos-recovery/ skills/aos-enterprise-council/registry/
```
