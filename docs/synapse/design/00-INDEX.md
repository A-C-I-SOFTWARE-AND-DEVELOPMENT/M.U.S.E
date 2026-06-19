# SYNAPSE Design & Planning Package — INDEX

**Project:** SYNAPSE — A muse Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10
**Owner:** Jeremiah Echerd, A-C-I Software & Development
**Design authority:** [`../../plans/2026-06-10-project-synapse-master-plan.md`](../../plans/2026-06-10-project-synapse-master-plan.md)

This folder is the complete, launch-ready design and planning bible for
PROJECT SYNAPSE — produced as a full design sprint by parallel discipline
pods (Combat & Systems, World & Narrative, Player Experience, Technical
Direction, Production & Release), each owning disjoint documents per the
repo's parallel-execution contract. Every document is **decision-final**:
numbers are locked, options are chosen, and anything not in these
documents is post-launch by definition.

## The documents

| # | Document | Discipline | Covers |
|---|---|---|---|
| 01 | [Game Design Document](01-game-design-document.md) | Creative direction | Vision, pillars, core loop, modes, accessibility, options, rating, scope contract |
| 02 | [Negotiation System](02-negotiation-system.md) | Systems | Capture-by-conversation: parley state machine, LLM integration, choice-wheel fallback, guardrails |
| 03 | [Combat & GAS Design](03-combat-gas-design.md) | Systems | Attributes, 8×8 type chart, abilities, Command Mode, Pipelines, bosses, difficulty, GAS mapping |
| 04 | [Roster — 24 Agents](04-roster-24-agents.md) | Character | Full sheets: personality cards, negotiation profiles, abilities, promotions, muse-bridge skills |
| 05 | [World Design](05-world-design.md) | World | 5 zones, encounter tables, 8 Gauntlets + boss designs, side content, pacing map |
| 06 | [Narrative & Campaign](06-narrative-campaign.md) | Narrative | 3-act beat sheet, the Deadlock, quest list, side arcs, post-game muse reveal, VO/loc scope |
| 07 | [Progression & Neural Network](07-progression-neural-network.md) | Systems | Network-as-character-sheet, wiring synergies, promotions, economy, real-muse bridge |
| 08 | [Avatar, Den & Onboarding](08-avatar-den-onboarding.md) | Player experience | First hour, muse creator (= persona setup), 5 personality questions, starter choice, Den loop |
| 09 | [Foundry Spec](09-foundry-spec.md) | Live systems | Struggle telemetry, candidate generation, validation harness, verdict cards, compliance |
| 10 | [Observatory Spec](10-observatory-spec.md) | Live systems | `/v1/observatory/*` route family, metrics collector, heat math, recommendation engine, owner-gated edits |
| 11 | [Technical Design](11-technical-design.md) | Engineering | Modules, SynapseNet client, local-LLM bridge, saves, perf budgets, CI, platform plan |
| 12 | [UI/UX Spec](12-ui-ux-spec.md) | UX | Screen inventory, HUD, parley UI, Command Mode, network screen shared with Observatory, input |
| 13 | [Audio Design](13-audio-design.md) | Audio | Sonic identity, interactive music, domain SFX palettes, VO plan, MetaSounds, mix targets |
| 14 | [Production Plan](14-production-plan.md) | Production | Team model, 40-sprint schedule, content pipelines, budget tracker, scope ladder, P1 lane |
| 15 | [QA & Test Plan](15-qa-test-plan.md) | QA | Test pyramid, LLM-layer tests, playtest program, compat matrix, RC criteria |
| 16 | [Steam Marketing & Launch Plan](16-steam-marketing-launch-plan.md) | Publishing | Store copy, AI disclosures, content calendar, festivals, wishlist model, launch runbook |
| 17 | [Launch Readiness Checklist](17-launch-readiness-checklist.md) | Release gate | Evidence-backed GO/NO-GO checklists across product, quality, legal, platform, ops |

## Shared canon (binding across all documents)

- **Fantasy:** the player is the **Architect**; their designed companion is the **muse**; the world is the **Substrate**; home is the **Den**. The antagonist is **THE DEADLOCK**, a corrupted ninth orchestrator whose **Fragmentation** shattered the great network — wild agents are its orphaned processes.
- **Economy:** currency **Cycles**; wiring resource **Synapse Thread**; rare material **Checksum Shards**. No microtransactions.
- **Domains & type chart:** 8 domains on a single advantage ring — Architecture > QA/Test > Build/Ops > Compliance > Behavior/Psych > Research > Security > Release > Architecture (strong vs next, weak vs previous; preserves the master plan's fixed edges Security>Release, QA>Build, Research>Security).
- **Roster:** 24 agents, 3 per domain, every one derived from a real role in `skills/aos-enterprise-council/` — AXIOM, LATTICE, FORGEMIND (Architecture); WARDEN, CIPHER, BREACH (Security); CONTRARIAN, NITPICK, REDFLAG (QA/Test); ORACLE, ARCHIVIST, RADAR (Research); FOREMAN, PIPELINE, PATCH (Build/Ops); EMPATH, MIRROR, NEURON (Behavior/Psych); HAZMAT, CLAUSE, AUDITRIX (Compliance); COMMANDER, VERDICT, POSTMORTEM (Release). Starters: AXIOM / CONTRARIAN / EMPATH. Commissioned heroes (§14 default): WARDEN, ORACLE, EMPATH.
- **World:** The Stacks (Gauntlets: Planning, Test) · The Foundry (Build, Rollback) · Gardens of Memory (Review) · The Vault (Security, Owner Approval) · The Gate Spire (Release + Council finale). Each Gauntlet boss enforces the verification gate it is named for.
- **The scope contract (from the master plan, restated, non-negotiable):** 5 zones · 24 agents · 8 Gauntlets · 0 multiplayer · 20–30h · RTwP on GAS · UE 5.6 · $24.99 · PC/Steam flagship, Android tier post-launch.
- **The coupling rule:** nothing from `hermes_cli/jarvis_prime/`, GraphRAG, the orchestrator, gates, or ledgers is ported to C++. All gateway capability arrives as additive route families through `scripts/generate_cockpit_contract.py`, frozen by `tests/gateway/test_cockpit_contract_freeze.py`.

## Status & next gate

Design and planning are **complete** as of this package. The next event in
the program is master plan **Phase 0, Week 1** (environment install, SYNAPSE
repo creation, trademark search, GPL re-audit) per
[14-production-plan.md](14-production-plan.md), exiting through the Phase 0
evidence gate. Changes to any LOCKED decision in this package require an
owner-authorized revision and a version bump of the affected document.
