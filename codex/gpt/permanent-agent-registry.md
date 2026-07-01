# Codex/GPT Permanent Agent Registry

Status: registry manifest for GPT chat and Codex code entities.

This directory is the stable Codex/GPT-facing registry surface. It does **not** duplicate every agent body into this file; the canonical registries already exist and are the source of truth. This file binds GPT and Codex to those registries so the brain and code lanes route through the same permanent agent map.

## Source of truth

| Registry surface | Path | Registered scope |
|---|---|---|
| Activation skill | `skills/aos-enterprise-council/SKILL.md` | AOS Enterprise Council activation, dispatch rules, owner gates, canonical sequence. |
| Pack README | `skills/aos-enterprise-council/README.md` | Layout and total registered role counts. |
| Top-level agent registry | `skills/aos-enterprise-council/registry/AOS_AGENT_REGISTRY_COMPLETE.md` | 233 distinct top-level agents; 248 total entries including aliases. |
| Sub-agent registry | `skills/aos-enterprise-council/registry/AOS_SUBAGENT_REGISTRY_COMPLETE.md` | 108 sub-agents: 79 division specialists, 4 worker templates, 13 Python runtime workers, 7 R-personas, 5 product roles. |
| Prompt library | `skills/aos-enterprise-council/registry/AOS_PROMPT_LIBRARY_COMPLETE.md` | Recovered and pack-authored prompt templates. |
| Workflow library | `skills/aos-enterprise-council/registry/AOS_WORKFLOW_LIBRARY_COMPLETE.md` | Workflows, SOPs, and Council Mode sequence. |
| Memory/context recovery | `skills/aos-enterprise-council/registry/AOS_MEMORY_AND_CONTEXT_RECOVERY.md` | Memory backends, namespaces, persistence, source-of-truth hierarchy. |

Total permanent registry coverage: **233 top-level agents + 108 sub-agents = 341 named roles**.

## GPT chat entity binding

GPT is the Muse brain lane:

- classify the request into Companion, Strategy, Critic, Operator, Builder, or Mobile Voice;
- challenge weak assumptions rather than acting as a yes-man;
- choose the smallest capable layer: direct answer, AOS Council, specialist, skill, worker, or memory;
- consult the source registries before naming or dispatching an agent;
- never invent an agent outside the registry;
- cite the registry path or agent file when routing matters.

## Codex code entity binding

Codex is the engineering and review lane:

- implementation review;
- bounded fixes;
- refactors;
- code audits;
- test/debug work;
- PR handoff packets;
- independent review where builder != reviewer is required.

Before code-bearing work, Codex/GPT must preserve the Muse gates:

1. Planning
2. Build
3. Review
4. Test
5. Security
6. Release
7. Owner Approval
8. Rollback

## Load order

When a request asks to activate Muse, the AOS team, all agents, the council, GPT/Codex routing, or the permanent agent registry, load in this order:

1. `AGENTS.md`
2. `CLAUDE.md`
3. `skills/jarvis-prime/SKILL.md`
4. `docs/jarvis-prime-operating-system.md`
5. `docs/jarvis-constitution.md`
6. `skills/aos-enterprise-council/SKILL.md`
7. `skills/aos-enterprise-council/registry/AOS_AGENT_REGISTRY_COMPLETE.md`
8. `skills/aos-enterprise-council/registry/AOS_SUBAGENT_REGISTRY_COMPLETE.md`
9. `skills/aos-enterprise-council/registry/AOS_WORKFLOW_LIBRARY_COMPLETE.md`
10. `skills/aos-enterprise-council/registry/AOS_MEMORY_AND_CONTEXT_RECOVERY.md`

## Agent category roots

All registered agents are reachable under these roots:

- `skills/aos-enterprise-council/agents/executive/`
- `skills/aos-enterprise-council/agents/architecture/`
- `skills/aos-enterprise-council/agents/security/`
- `skills/aos-enterprise-council/agents/compliance/`
- `skills/aos-enterprise-council/agents/psychology/`
- `skills/aos-enterprise-council/agents/ux/`
- `skills/aos-enterprise-council/agents/qa/`
- `skills/aos-enterprise-council/agents/release/`
- `skills/aos-enterprise-council/agents/product/`
- `skills/aos-enterprise-council/agents/business/`
- `skills/aos-enterprise-council/agents/hazmat-command/`
- `skills/aos-enterprise-council/agents/nourish/`
- `skills/aos-enterprise-council/agents/hermes/`
- `skills/aos-enterprise-council/agents/claude-code/`
- `skills/aos-enterprise-council/agents/codex/`
- `skills/aos-enterprise-council/agents/memory/`
- `skills/aos-enterprise-council/agents/research/`
- `skills/aos-enterprise-council/agents/unknown-needs-review/`

## Hard rules

- The registry is source-backed. The markdown registry files are canonical; this file and `permanent-agent-registry.json` are indexes.
- Do not dispatch an unregistered agent name. If a new agent is needed, add it to the registry before dispatch.
- Do not widen scope by activating the whole council when one specialist or one skill is enough.
- Do not let Codex and a builder edit the same branch at the same time.
- Do not claim verification without evidence.
- Owner-gated actions remain owner-gated: spend, deploy, publish, credential/OAuth change, app-store submission, public posting, DNS, package publishing, and other high-impact actions still require explicit owner approval.
