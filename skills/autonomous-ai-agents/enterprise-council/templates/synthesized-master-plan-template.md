# Synthesized Master Plan — <short title>

**Date:** YYYY-MM-DD
**Author (synthesizer):** <agent / session>
**Run folder:** `docs/aos/runs/YYYY-MM-DD-<slug>/`
**Artifact slot:** `04-synthesized-plan.md`
**Companion governance:** `docs/governance/16-deliberative-planning-and-council-mode.md`,
`docs/governance/06-maker-checker-independent-review.md`

> The Synthesizer does not average plans. It produces a curated
> single master plan that adopts the strongest surviving ideas from
> the multi-plan set, names rejected ideas with rationale, and
> surfaces unresolved owner choices rather than silently deciding
> them. The synthesizer must not also red-team this plan.

## Final strategic thesis (one paragraph)

<the single sentence the rest of the plan supports, expanded to one
paragraph of why-this-and-not-that>

## Decisions adopted

| Decision | Source plan(s) | Evidence supporting | Why this beat alternatives |
|---|---|---|---|
| | | | |

## Decisions rejected (preserve as warnings)

| Decision | Source plan(s) | Why rejected | What signal would change this |
|---|---|---|---|
| | | | |

## Unresolved owner choices (surface, do not decide)

| Choice | Options | Implication of each | Owner decision required by |
|---|---|---|---|
| | | | |

## Implementation order (waves)

1. **Wave 1:** <scope> — gating acceptance: <observable>
2. **Wave 2:** <scope> — gating acceptance: <observable>
3. <...>

For each wave, name:

- Builder subagent / division.
- Reviewer subagent / division (must be different from builder).
- Verifier subagent / division (RC3 only; must be different from
  reviewer).

## Artifacts to create

For each wave, the templated artifacts:

- Research dossier extension (if any): `docs/research/____.md`
- ADR (if any): `docs/architecture/adr-____.md`
- Threat model (if any): `docs/security/threat-model.md` update
- Compliance evidence matrix (if any): `docs/iso27001/____.md`
- Pricing study / GTM brief / claims memo (if any): under
  `docs/____` per the appropriate template
- Codex Task Packet (if any): `07-codex-task-package.md`
- Run-folder artifacts (always): 08–13 per `docs/aos/README.md`

## Test gates

Per wave, the validators and tests that must remain green or
become green:

- `npm run lint`
- `npm run typecheck`
- `npm test` — current/baseline + named new negative-path tests
- `npm run build`
- `npm run governance:check`
- `npm run agentos:check`
- `npm run council-codex:check`
- `npm run readiness:check`
- `npm run i18n:check` (if i18n changed)
- `npm run test:e2e` (if e2e-covered path changed)
- Hook tests under `tests/claude-os/`

## Definition of done (master)

- [ ] Every wave's acceptance criteria met.
- [ ] Every required artifact present in the run folder.
- [ ] Red-team revision applied (single pass).
- [ ] Owner approval recorded.
- [ ] PR(s) opened as draft per `AGENTS.md`.
- [ ] No owner-only wall touched without surfacing for owner action.

## Commercial / readiness implications

- Claims introduced (cite C1–C6 class per `governance/11`):
- Legal text introduced (counsel-review banner per `governance/12`):
- Pricing / packaging implications:
- Pilot / procurement implications:
- Compliance evidence changes:

## Synthesizer attestation

- [ ] I am not also the red-team reviewer for this plan.
- [ ] Every adopted decision cites an evidence item.
- [ ] No rejected idea was silently re-introduced.
- [ ] Every unresolved owner choice is surfaced (none silently
  decided).
- [ ] The plan does not authorize any owner-only wall action.

## Revision log (after red-team)

| Date | Reason | Change |
|---|---|---|
| YYYY-MM-DD (initial) | — | initial synthesis |
| YYYY-MM-DD (post-red-team) | <red-team finding ID> | <change> |

Council Mode allows **one** revision pass after red-team. Further
changes require returning to plan generation or escalating to the
owner.

## Anti-patterns rejected on sight

- Averaging plans rather than curating.
- Silently re-introducing a rejected idea.
- Silently deciding an owner choice.
- Adopting a plan wholesale without naming the rejected
  alternatives.
- A "synthesis" that adds new scope not present in any plan.
- A synthesizer who is also the red-team reviewer.
