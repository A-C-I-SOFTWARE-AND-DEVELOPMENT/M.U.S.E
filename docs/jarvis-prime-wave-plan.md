# muse Wave Build Plan

This document records the actual sequence in which muse has
been (and will be) built. It supersedes any earlier plan that assumed
Wave 1 was still ahead of us — the runtime has already landed.

## Wave 0 (this branch): foundation lock

Goal: declare the canonical repo, document the wave plan honestly,
and add the standard `WorkPacket` model so the already-shipped
runtime has a canonical work-descriptor schema.

Scope (additive only, does not touch any shipped runtime module):

* `CANONICAL_REPO.md` at the repo root.
* `docs/jarvis-prime-wave-plan.md` (this file).
* `hermes_cli/jarvis_prime/work_packet.py` with `WorkPacket`,
  `WorkPacketValidationFinding`, `validate()`, `to_dict()`,
  `from_dict()`. Stdlib-only; defaults
  `owner_authorization_phrase` to
  `hermes_cli.jarvis_prime.owner_auth.AUTHORIZATION_PHRASE` so the
  data layer and the gate layer share one source of truth.
* `tests/test_jarvis_prime_work_packet.py` matching the existing
  flat-layout convention.
* Additive edit to `hermes_cli/jarvis_prime/__init__.py` exposing
  `WorkPacket`, `WorkPacketValidationFinding`,
  `WORK_PACKET_REQUIRED_FIELDS`, `WORK_PACKET_RISK_CLASSES`.

Out of scope for this branch: rewriting any existing module, adding
runtime behavior, wiring `WorkPacket` into the router or gates.

## Wave 1: runtime v1.0.0 — already landed

Wave 1 shipped to `main` on 2026-05-25 as a single commit
(`45a11b0`, "feat(jarvis-prime): runtime v1.0.0 — 18 modules + 159
tests", 32 files, 5804 insertions). It is **historical, not
planned**.

Modules that landed:

* `persona.py` — `Persona` / `PersonaPrompt`, six mode prompts,
  default / operator / mobile-voice response formats, the
  anti-hallucination rule.
* `modes.py` — `Mode` enum, `ModeClassifier`, slash-command mapping.
* `router.py` — `Router`, `RouteDecision`, `RouteTarget` honoring
  the Jeremiah → muse → AOS Council → specialists → skills →
  workers hierarchy.
* `runtime.py` — `JarvisPrime` orchestrator (perceive → classify →
  decide → gate → delegate → speak).
* `awareness.py` — six parallel perception streams with per-stream
  timeouts and the never-raise contract.
* `memory.py` — multi-tier `MemoryStore` with `MemoryRecord`.
* `owner_auth.py` — `AUTHORIZATION_PHRASE = "Yes, with
  authorization."`, `OWNER_GATED_ACTIONS` frozenset, `OwnerAuth`,
  `OwnerGate`. Literal-phrase enforcement.
* `gates.py` — eight gates (Planning / Build / Review / Test /
  Security / Release / Owner Approval / Rollback), `GateOutcome`,
  `GateResult`, `GateSummary`, `run_gate_summary`.
* `reasoning.py` — `Reasoner`, `Premise`, `Inference`, `Rule`,
  `deduce`, `induce`, `should_research`.
* `research.py` and `social_research.py` — research escalation and
  public-API social-research surfaces.
* `epistemics.py` — `audit_response`, `AuditOutcome`, `AuditReport`
  for anti-hallucination auditing.
* `self_update.py` — `Proposal`, `ProposalBook`, `ProposalEvidence`,
  `ProposalKind`, `ProposalStatus`.
* `onboarding.py` — first-run onboarding flow.
* `tick.py` — proactive tick; cron entry point at
  `scripts/jarvis-prime-tick.sh`.
* `communication_style.py` — conversational pacing.
* `__main__.py` — CLI subcommands `perceive`, `classify`, `gate`,
  `handle`, `tick`.

Tests that landed: 14 flat-layout files at
`tests/test_jarvis_prime_*.py`, 159 tests, stdlib + pytest only.

## Wave 2 (integration branch): intentionally skipped

The original plan called for an `integration/jarvis-prime-runtime`
branch that aggregated multiple Wave 1 feature lanes. In practice
Wave 1 landed as a single commit on main, so no integration branch
was created. This wave is recorded as **N/A** rather than re-opened
retroactively. Any future runtime expansion (beyond Wave 0's
`WorkPacket` port) that requires multiple lanes should reinstate the
integration-branch pattern: `integration/<feature-cluster>`.

## Wave 3 (open): Codex independent review

Codex has not yet performed an independent review of the shipped
runtime. The open Wave 3 review must cover **both**:

1. The shipped runtime commit `45a11b0` end-to-end.
2. The Wave 0 `WorkPacket` port on this branch.

Codex brief:

* Confirm runtime correctness, owner-gate literal-phrase enforcement,
  hallucination-audit behaviour, and stdlib-only import-time policy.
* Confirm the Wave 0 port is additive only — no shipped runtime
  module is modified, the `__init__.py` edit preserves every
  existing export, the test naming follows the flat
  `tests/test_jarvis_prime_*.py` convention.
* Flag any place where the runtime and the new `WorkPacket` schema
  disagree on field names, risk classes, or owner-gated action
  strings.

Claude Code must not edit this branch while Codex is reviewing.

## Wave 4 (gated): owner-approved main merge

`main` merges happen only after the owner replies with the exact
phrase `Yes, with authorization.` Authorization is per-merge, not
standing.

## Rules

* Do not edit `main` directly.
* Cut feature branches from current `origin/main` HEAD, not from
  divergent fork history. Stale-base branches will conflict with the
  shipped runtime.
* Each feature lane gets its own branch.
* Shared runtime files (anything under `hermes_cli/jarvis_prime/`)
  require extra caution. The Wave 0 `__init__.py` edit is the only
  shared-file touch authorized for this branch, and it is purely
  additive.
* Claude Code and Codex must not edit the same branch at the same
  time.
* For multi-lane work, route through an integration branch first.
* Main merges require owner approval (`Yes, with authorization.`).
* No "done" claim without verification evidence (tests run, diff
  reviewed, rollback plan documented).
