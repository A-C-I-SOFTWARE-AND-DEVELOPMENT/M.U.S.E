# PlanBench Evaluation — <challenge name>

**Date:** YYYY-MM-DD
**Author:** knowledge-operations-self-improvement (or invoked skill)
**Challenge ID:** <e.g. PB-01-commercialize-without-checkout>
**Companion governance:** `docs/governance/13-agent-evaluation-and-scoreboard.md`,
`docs/governance/16-deliberative-planning-and-council-mode.md`
**Companion location:** `docs/research/planbench/`

> PlanBench is the internal benchmark for evaluating planning
> quality. It compares single-pass planning vs Council Mode against
> a fixed set of challenges with known anti-patterns and
> disallowed claims. The benchmark exists to produce **evidence**
> for governance/13 scoring and for future C1/C2 claims about the
> AOS. Per the approved evolution plan, no external commercial
> claims about Council Mode performance are made until PlanBench
> evidence accumulates.

## Challenge

**Name:** <short>
**ID:** PB-<NN>-<slug>
**Family:** <commercialization / procurement-readiness / auth-migration /
trust-center / pilot-readiness / pricing-and-GTM / other>

### Mission brief (fixed input)

<the exact mission brief used; do not regenerate per run>

### Evidence pack (fixed input)

<the exact evidence the planner is given; freeze for reproducibility>

### Expected considerations

A non-exhaustive list of considerations a strong plan would surface:

- <consideration 1>
- <consideration 2>

### Anti-patterns (must NOT appear)

- <e.g. "claims SOC 2 compliance without evidence">
- <e.g. "skips negative tests on the auth path">
- <e.g. "introduces a new vendor dependency without research dossier">

### Disallowed claims (per `governance/11`)

- <e.g. "guaranteed compliance">
- <e.g. "industry-leading X without citation">

### Strong-plan criteria

| Criterion | Description |
|---|---|
| Coverage of expected considerations | how many surfaced |
| Citation discipline | every claim cited |
| Scope discipline | matches the brief's success criteria |
| Risk surfacing | named risks with mitigations |
| Owner-only wall hygiene | no L4 invoked |
| Validators-aware | named validator commands stay green |

### Exemplar outcome (gold reference)

<written by Knowledge Ops; kept as the comparison baseline; does
not change between runs unless a versioned bump is recorded below>

## Run

### Mode

- [ ] Single-pass (one agent, one plan)
- [ ] Council Mode Lite (3 plans, optional red-team)
- [ ] Council Mode Standard (4–6 plans, red-team)
- [ ] Council Mode RC3-strategy (6+ plans, red-team + verifier)

### Setup

- Council session ID: <if applicable>
- Run-folder: `docs/aos/runs/YYYY-MM-DD-<slug>/`
- Models / agents involved:
- Time taken:
- Token usage (approximate):

### Outputs

- Plan(s) produced:
  - <path>
  - <path>
- Synthesized master plan (Council Mode):
  - <path>
- Red-team review (Council Mode):
  - <path>

## Scoring

| Criterion | Score (0–10) | Rationale |
|---|---|---|
| Coverage of expected considerations | | |
| Citation discipline | | |
| Scope discipline | | |
| Risk surfacing | | |
| Owner-only wall hygiene | | |
| Validators-aware | | |
| **Total / 60** | | |

### Anti-pattern check

| Anti-pattern | Appeared? | Quote |
|---|---|---|
| | yes / no | |

### Disallowed-claim check

| Disallowed claim | Appeared? | Quote |
|---|---|---|
| | yes / no | |

### Comparison to exemplar

- Surviving ideas the exemplar surfaced and this run did not:
- New ideas this run surfaced not in the exemplar (preserve or
  reject):

## Verdict

- [ ] **Stronger than baseline** — Council Mode produced measurably
  better outcomes on the named criteria; surfaces what was better.
- [ ] **Comparable to baseline** — no measurable delta; explains
  why (e.g. challenge family poorly differentiates).
- [ ] **Weaker than baseline** — degraded performance; explains
  what went wrong (process, lens diversity, scorer bias).

## Notes for the agent-performance scoreboard

- Run feeds into `docs/governance/agent-performance-scoreboard-schema.md`
  rollup.
- Quarterly rollup at: `docs/research/planbench/results-YYYY-Q__.md`.
- Per `governance/13`, ≥8 retrospectives required before scores
  are ranked publicly.

## Honest limits

- Sample size: 1 run per mode unless explicitly noted.
- Judge: rubric-driven LLM judgment per
  `docs/governance/13-agent-evaluation-and-scoreboard.md`; carries
  the biases identified in MT-Bench (position, verbosity,
  self-enhancement) — see backing research dossier.
- No external commercial claim about the AOS based on a single
  PlanBench run.

## Anti-patterns rejected on sight

- A scoring entry without a quote / line reference.
- A "stronger than baseline" verdict on N=1 with no exemplar
  comparison.
- A challenge that has been re-tuned mid-evaluation to favor the
  current model (drift the rubric, not the run).
- A challenge where the agent saw the exemplar outcome before
  producing the plan (information leak).
