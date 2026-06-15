# Fleet Hierarchy — mapping the naval metaphor onto MUSE's real primitives

**Date:** 2026-06-14 · **Status:** decision pending (owner picks an approach) ·
Companion to `docs/synapse/NERO_FLEET_STATIC_ANALYSIS.md`

The "Nero‑Fleet" vision asks for a naval command structure. MUSE already has the
substance; this doc maps the metaphor onto the existing primitives and lays out **both
implementation approaches with their pros and cons** so the owner can choose. No code is
changed by this document.

## 1. The metaphor ↔ what already exists

| Fleet term | Real subsystem (today) | Where |
|---|---|---|
| **Admiralty** (the mind/registry the fleet reports to) | Orchestrator job store + AOS council registry | `hermes_cli/orchestrator_models.py`, `skills/aos-enterprise-council/registry/` |
| **Flagship** (command / mode switching) | jarvis_prime mode layer — Operator / Strategy / Builder / Critic / Companion / Mobile Voice | `hermes_cli/jarvis_prime/` |
| **TacticalVessel** (execution shell) | Hermes agent loop + worker execution | `run_agent.py`, worker dispatch in the orchestrator |
| **IntelligenceFleet** (multi‑perspective judgment, audits) | AOS Council | `skills/aos-enterprise-council/` |
| **FleetShip / FleetNode** (a unit reporting telemetry) | `WorkerSpec` + `Job` state + ledger events | `hermes_cli/orchestrator_models.py`, decision ledger |

The orchestration spine is five primitives — Job, Worker (profile), Model routing,
Validation gate, Decision ledger (`CLAUDE.md`). The Fleet metaphor is a **vocabulary over
those**, not a sixth primitive.

## 2. Two ways to implement it

### Approach A — additive `FleetNode` overlay  *(recommended)*
A new, read‑only module (e.g. `hermes_cli/jarvis_prime/fleet.py`) defining a `FleetNode`
base and `Admiralty` / `Flagship` / `TacticalVessel` / `IntelligenceFleet` façades that
*wrap and read* the existing `Job` / `WorkerSpec` / council registry and emit telemetry.
Nothing in the orchestrator core changes.

- **Pros**
  - Default code paths stay **byte‑for‑byte unchanged**; no regression risk to the
    orchestrator, the tamper‑evident ledger, or `job.json` on‑disk keys.
  - Honors `CLAUDE.md`'s "don't reinvent the five primitives" and "don't change default
    behavior" rules.
  - Reversible and shippable in one small PR; can be put behind a flag/view.
  - Gives the cockpit a "Fleet view" telemetry surface without touching execution.
- **Cons**
  - Two vocabularies coexist (Job/Worker **and** Fleet) — potential for confusion.
  - The metaphor is a *view/façade*, not the literal spine; some will read it as cosmetic.
  - Telemetry mapping must be kept in sync if the underlying models change.

### Approach B — rename the core classes into the Fleet hierarchy
Refactor the live orchestrator classes (`Job`, `WorkerSpec`, `JobState`, …) so the Fleet
names *are* the spine.

- **Pros**
  - One unified vocabulary end‑to‑end; the metaphor is "real" in the code, not a skin.
  - No dual‑naming to keep in sync.
- **Cons**
  - **Large blast radius:** `orchestrator_models.py`, `job_controller.py`,
    `orchestrator_api.py` (~55 KB), `orchestrator_events.py`, the **tamper‑evident ledger /
    `job.json` on‑disk keys**, the Android `TaskType` mirror, and many tests.
  - **Backward‑incompatible serialization** unless every renamed key is aliased — risks
    breaking replay of existing job folders and the contract‑freeze tests.
  - Violates "default code paths unchanged"; high regression risk; hard to do as one safe PR.
  - Owner‑gated and best sequenced as its own refactor, after a freeze.

## 3. Recommendation

**Approach A (additive overlay).** It delivers the Fleet command surface and telemetry the
vision wants with zero behavior change and no ledger churn, and it can ship immediately.
Reserve **Approach B** for a deliberately scoped, owner‑gated refactor only if a single
vocabulary later proves worth the migration cost. The final call is the owner's.
