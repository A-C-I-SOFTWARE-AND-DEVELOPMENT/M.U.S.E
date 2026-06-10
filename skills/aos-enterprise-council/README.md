# aos-enterprise-council — Hermes skill pack (v2.0.0)

Complete AOS Enterprise Council, installable into Hermes. Built by
the **scope-corrected AOS Recovery pass** on 2026-05-24 (branch
`claude/aos-agent-recovery-hermes-jmocw`).

Combines:

- The **hazmat-command canonical AOS Council** — 11 division agents,
  22 skills, 7 rules, 19 governance docs, 12 workflows, 30 skill SOPs,
  22 templates, 3 historical council runs.
- The **Hermes 16-specialist AOS council** — aos-council-director,
  aos-full-agent-team + 14 specialists (principal-systems-architect,
  product-experience-architect, commercial-strategist,
  assurance-risk-director, delivery-scope-controller,
  contrarian-reviewer, contrarian-red-flag-analyst,
  codex-dispatch-governor, model-router, decision-quality-gate,
  research-validator, self-improvement-loop, ai-improvement-radar,
  developer-ux-command-center).
- The **enterprise-council 8 leaves** — orchestrator, judge, monitor,
  customer-service, finance, hr, operations, sales (Python-runtime).
- The **autonomous-ai-agents 5 adapters** — claude-code, codex,
  hermes-agent, opencode, kanban-codex-lane.
- The **Hermes orchestration worker-profile templates** — claude-code-worker,
  codex-worker, aider-worker, goose-worker.
- The **Hermes Python runtime workers** — 13 modules across
  `enterprise/` and `agent/` (council.py, judge.py, monitor.py,
  audit.py, policy.py, secrets.py, adapters/cs.py, adapters/finance.py,
  adapters/hr.py, adapters/ops.py, adapters/sales.py, codex_runtime.py,
  codex_responses_adapter.py).
- The **hazmat division sub-agents** — 79 named specialists extracted
  from `recovered-agent-sources/from-hazmat-command/docs/agents/0[0-9]-*.md`.
- The **R-code personas** — R1-D, R2-I, R3-O, R4-X, R5-T, R5-U, R5-V.
- The **HazMat product roles** — carrier_admin, safety_manager,
  dispatcher, driver, solo_driver.

**Total registered entries:** 233 distinct top-level agents + 108 sub-agents = **341 named roles**.

## Layout

```
skills/aos-enterprise-council/
├── SKILL.md                                ← Hermes activation entry point (load me first)
├── README.md                               ← this file
├── registry/                               ← THE 5 REGISTRY FILES (the heart of the pack)
│   ├── AOS_AGENT_REGISTRY_COMPLETE.md      ← 233 top-level agents × canonical/aliases/mentioned
│   ├── AOS_SUBAGENT_REGISTRY_COMPLETE.md   ← 108 sub-agents
│   ├── AOS_PROMPT_LIBRARY_COMPLETE.md      ← every recovered prompt template
│   ├── AOS_WORKFLOW_LIBRARY_COMPLETE.md    ← every recovered workflow + Council Mode sequence
│   └── AOS_MEMORY_AND_CONTEXT_RECOVERY.md  ← memory backends, namespaces, source-of-truth hierarchy
├── agents/                                 ← per-category agent files (one .md per registered agent)
│   ├── executive/        (chief-orchestrator, aos-council-director, ...)
│   ├── architecture/     (engineering-architecture-factory, principal-systems-architect, ...)
│   ├── security/         (assurance-security-compliance-office, ...)
│   ├── compliance/       (claims-substantiation-review, compliance-rule-change, ...)
│   ├── psychology/       (psychology-ux-agent, humanizer, ...)
│   ├── ux/               (product-pilot-experience-studio, product-experience-architect, ...)
│   ├── qa/               (principal-code-reviewer, decision-quality-gate, contrarian-reviewer, ...)
│   ├── release/          (pilot-readiness-judge, qa-release-commander, ...)
│   ├── product/          (product-strategy-agent, competitive-feature-harvester, ...)
│   ├── business/         (commercial-strategy-growth-office, legal-policy-contracts-trust-office, ...)
│   ├── hazmat-command/   (hazmat-command-specialist + division pointers)
│   ├── nourish/          (nourish-product-specialist — RECONSTRUCTED, NEEDS USER REVIEW)
│   ├── hermes/           (kanban-orchestrator, dogfood, model-router, github-publisher, ...)
│   ├── claude-code/      (claude-code agent spec, claude-code-worker template)
│   ├── codex/            (codex-implementation-fabric, codex-dispatch-governor, codex agent, codex-worker)
│   ├── memory/           (knowledge-operations-self-improvement, memory-knowledge-curator, ...)
│   ├── research/         (research-evidence-bureau, research-dossier-build, research-validator, ...)
│   └── unknown-needs-review/   (empty by default; new uncategorised agents land here)
├── prompts/                                ← copy-paste prompts (5)
│   ├── master-audit-prompt.md
│   ├── claude-code-build-prompt.md
│   ├── codex-implementation-prompt.md
│   ├── repo-recovery-prompt.md
│   └── launch-readiness-prompt.md
├── workflows/                              ← every hazmat workflow + pack-authored playbooks
├── rules/                                  ← 7 hazmat rules (verbatim copy)
├── templates/                              ← 22 hazmat templates (verbatim copy)
└── source-snapshots/MANIFEST.md            ← pointer into ../../recovered-agent-sources/
```

## Activation phrases

Saying any of these to Hermes loads this skill:

- "audit repo" / "audit this repo"
- "build the app"
- "enterprise hardening"
- "launch readiness"
- "improve the product"
- "use the AOS team" / "use the aos smart team"
- "activate the council" / "run the council"
- "psychology audit" / "ux audit"
- "Claude/Codex orchestration"
- "HazMat Command review" / "hazmat review"
- "Nourish review" / "nourish audit"

You can also load the skill explicitly:

```
/aos-enterprise-council <your goal>
```

## Install (Termux / Hermes on phone)

This skill pack lives in the `hermes-agent` GitHub repo. To install
it into your live Hermes runtime at `~/.hermes/skills/`:

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

# 5) Reload Hermes' skill index
muse skills list
muse doctor
hermes
# in the Hermes REPL:
#   /reload-skills
#   /aos-enterprise-council audit this repo
```

See `AOS_INSTALLATION_REPORT.md` at the repo root for verification commands.

## How the council runs

`SKILL.md` is the activation surface. When loaded, the skill:

1. Reads the user's goal verbatim.
2. Computes a goal slug and opens memory namespace `aos/council/<slug>`.
3. Classifies risk (RC0–RC4) using `rules/` + the change-risk matrix.
4. Picks a workflow from `workflows/`.
5. Installs a todo list, one entry per council member it will
   dispatch.
6. Dispatches each member via Hermes `delegate_task`, with the
   matching `agents/<category>/<agent>.md` as their system prompt.
7. Runs the red-team and owner-approval gates without skipping.
8. Persists the decision-of-record in memory.

## Source provenance

| Element | Source |
| --- | --- |
| Registry (5 files) | Generated by `awk`/`python3` over harvested frontmatter from every SKILL.md and agent.md in both repos. |
| Per-agent files (233 + 11 synthesized) | One file per registered name; frontmatter + canonical source path + recovery label. |
| Rules (7) | Verbatim copy of `recovered-agent-sources/from-hazmat-command/rules/`. |
| Templates (22) | Verbatim copy of `recovered-agent-sources/from-hazmat-command/docs/templates/`. |
| Workflows (12) | Verbatim copy of `recovered-agent-sources/from-hazmat-command/docs/workflows/` + pack-authored Hermes-runtime headers. |
| Prompts (5) | Newly authored for Hermes / Claude Code / Codex copy-paste use. |

See `../../recovered-agent-sources/MANIFEST.md` for the full source
inventory and `../../AOS_AGENT_RECOVERY_REPORT.md` for the narrative
recovery report.
