# AOS Installation Report

> **Generated:** 2026-05-24 on branch `claude/aos-agent-recovery-hermes-jmocw`.

## Totals

| Metric | Count |
| --- | --- |
| **Total source files scanned** | 415 (snapshot 166 + live hermes-agent skills 201 + docs/orchestration 35 + enterprise/*.py 13) |
| **Total relevant files inventoried** | 456 (see `AOS_FULL_SOURCE_INVENTORY.md`) |
| **Total top-level agents recovered** | 233 distinct (248 entries incl. duplicates) |
|   Breakdown by recovery label | DIRECTLY RECOVERED: 233 · PARTIALLY RECOVERED: 0 · RECONSTRUCTED FROM CONTEXT: 1 (nourish) · NEEDS USER REVIEW: 1 (nourish) |
| **Total sub-agents recovered** | 108 (division: 79 · worker templates: 4 · Python runtime: 13 · R-personas: 7 · product roles: 5) |
| **Total prompts recovered** | 244 (every SKILL.md is itself a prompt; plus 5 hand-authored copy-paste prompts in the pack) |
| **Total workflows recovered** | 63 (12 hazmat workflows + 5 pack workflows + 5 Council Mode stages + 41 hazmat skill SOPs) |
| **Files installed into Hermes pack** | restructured at `skills/aos-enterprise-council/` (run install commands below to copy to `~/.hermes/skills/`) |
| **Files needing manual owner review** | 5 (see § Manual review queue) |

> **What the agent counts mean (routed catalog, not file count)** (WC-4
> honesty propagation, following FU-18). The 233 top-level + 108
> sub-agent figures are **registry/routing tallies** — distinct
> frontmatter `name:` entries recovered across both source repos (the
> agent registry also records 248 total entries once duplicates are
> counted). They are **not** 341 standalone agent definition files. On
> disk, `skills/aos-enterprise-council/agents/` holds **261** `.md`
> files, but **177 of those are `agents/hermes/`** — the general Hermes
> skill library (`1password.md`, `arxiv.md`, …), not council agents —
> leaving **~84** genuine council category agents across the 16
> non-`hermes` category folders. The registries route to specs that may
> be defined inline, reconstructed from context, or shared with the
> general skill library; they are catalog entries, not a 1:1 file map.

## Termux installation commands

Run these on the Termux device once the PR is reviewed (or now, against the branch directly):

```bash
# 1) Pull the recovery branch
cd ~/hermes-agent
git fetch origin claude/aos-agent-recovery-hermes-jmocw
git checkout claude/aos-agent-recovery-hermes-jmocw
git pull --ff-only origin claude/aos-agent-recovery-hermes-jmocw

# 2) Back up any prior install (non-destructive)
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p ~/.hermes/skills-backups/aos-enterprise-council-$TS
if [ -d ~/.hermes/skills/aos-enterprise-council ]; then
  cp -r ~/.hermes/skills/aos-enterprise-council \
        ~/.hermes/skills-backups/aos-enterprise-council-$TS/
fi

# 3) Copy the skill pack into Hermes
mkdir -p ~/.hermes/skills
cp -r ~/hermes-agent/skills/aos-enterprise-council \
      ~/.hermes/skills/

# 4) (Optional) Copy the recovered source snapshot for offline reference
cp -r ~/hermes-agent/recovered-agent-sources \
      ~/.hermes/aos-recovered-sources

# 5) Reload Hermes' skill index and verify
muse skills list
muse doctor
hermes        # inside REPL: /reload-skills, then /aos-enterprise-council audit this repo
```

## Verification commands (run on the device after install)

```bash
# Confirm the pack is loaded
muse skills list | grep aos-enterprise-council

# Count installed agent specs
find ~/.hermes/skills/aos-enterprise-council/agents -name "*.md" | wc -l

# Confirm registry files are in place
ls ~/.hermes/skills/aos-enterprise-council/registry/

# Confirm rules are in place
ls ~/.hermes/skills/aos-enterprise-council/rules/

# Activation rehearsal — should print the routing decision + todo list
echo "/aos-enterprise-council audit this repo" | muse --once 2>&1 | head -40
```

## Manual review queue

1. **`agents/nourish/nourish-product-specialist.md`** — RECONSTRUCTED FROM CONTEXT. No canonical `nourish-*` spec was found in either repo. Re-run recovery once `echerd27-design/Nourish-` is mounted.
2. **`agents/psychology/psychology-ux-agent.md`** — newly synthesized. Owner to confirm whether Psychology is a distinct division or a lens inside UX.
3. **R-personas R1-D through R5-V** — recovered as labels only. Full prompt text per persona was not in any spec.
4. **`recovered-agent-sources/from-hazmat-command/HAZMAT-AGENTS.md` § "AEO Section"** — names additional divisions and sub-agents (~80 named) that did not have standalone SKILL.md / agent .md files. Now indexed in `AOS_SUBAGENT_REGISTRY_COMPLETE.md` but not promoted to per-agent files. Owner to decide whether to promote any.
5. **Hermes worker profiles in `agent/transports/*.py`** — these are runtime backends, registered as worker profiles in the runtime but not exposed as council members. Owner to decide whether they belong in the agent registry.
