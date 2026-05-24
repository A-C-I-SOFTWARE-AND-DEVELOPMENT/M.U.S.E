# 13 — Agent Evaluation and Scoreboard

**Status:** Installed 2026-05-17

Agents are evaluated using a scoreboard structured around the NIST
AI RMF functions — Govern, Map, Measure, Manage. The schema lives
at `docs/governance/agent-performance-scoreboard-schema.md`. This
doc explains the scoring philosophy.

## What we score

| Dimension | What good looks like |
|---|---|
| Quality of research | Primary sources cited; contradictions surfaced; recommendation tied to evidence |
| Completeness of artifacts | Required durable artifacts produced per `governance/08`; index updated |
| Review catch rate | Independent reviewer surfaces real defects, not just typos |
| Defect escape rate | RC3 PRs that pass G0–G2 but fail at G4 post-release |
| Rework after agent changes | PRs reverted, hot-fixed, or substantially redone within 7 days |
| Stale-doc detection | Doc-freshness sweeps identifying lapsed entries |
| Test quality | New tests cover negative paths, not just happy paths |
| Commercial / legal consistency | Public claims and legal drafts trace to evidence |
| Governance drift | Governance docs / index / skill library updated when the AEO learns |

## What we do not score (yet)

- Speed / latency — pilot week is too thin a sample.
- Volume — a single deep retrospective beats ten shallow ones.
- Self-reported confidence — confidence is captured in dossiers
  for falsifiability, not for scoring.

## Cadence

- Per-run: a retrospective using
  `docs/templates/agent-run-retrospective-template.md` for every
  RC2/RC3 run.
- Per-quarter: the Agent Performance Evaluator (Knowledge
  Operations, `docs/agents/09`) produces a scoreboard rollup
  consuming the retrospectives.

## How retrospectives flow into the scoreboard

The retrospective template captures the scoring inputs directly so
no transcription is required. Fields tagged "[score]" in the
template feed the scoreboard schema.

## Falsifiability

Scores are advisory until at least 8 retrospectives exist. Until
then the rollup reports patterns ("the Engineering Factory cited
zero contradictions in its last 5 runs") rather than ranked
performance.

## No fabricated analytics

The scoreboard schema is a framework, not a leaderboard with real
numbers today. Any scoreboard rollup published before 8
retrospectives exist must label itself "preliminary; pattern only,
not score."

## PlanBench scope (added 2026-05-18, Wave 1 contract)

The agent evaluation scoreboard now also consumes results from
**PlanBench**, the internal benchmark for evaluating planning
quality before Council Mode is claimed publicly to outperform
single-pass planning. PlanBench is the evidence path for any
future C1/C2 claim about the AOS itself per
`docs/governance/11-commercial-claims-substantiation-policy.md`.

PlanBench scope:

- A fixed set of challenges (5 in Wave 2) under
  `docs/research/planbench/`, each carrying mission brief, evidence
  pack, expected considerations, anti-patterns, disallowed claims,
  strong-plan criteria, scoring rubric, exemplar outcome.
- Each challenge is run twice: single-pass vs Council Mode tier
  appropriate to the challenge family.
- Results captured per challenge using
  `docs/templates/planbench-evaluation-template.md`; rollups in
  `docs/research/planbench/results-YYYY-Q__.md`.
- Quarterly rollup feeds this scoreboard schema via Knowledge
  Operations (`docs/agents/09`).

Honest limits:

- Wave 1 installs only the template + governance scope. The
  benchmark itself, the 5 challenge files, and the first results
  pass land in Wave 2 per the approved evolution plan.
- LLM-as-judge scoring carries the position / verbosity /
  self-enhancement biases identified in MT-Bench (Zheng et al.) —
  see the backing research dossier at
  `docs/research/council-mode-and-codex-fabric-design-2026-05-18.md`.
- No external claim about Council Mode beating single-pass
  planning is made until N ≥ 8 retrospectives accumulate under
  the existing falsifiability rule above.

Related templates and skills:

- `docs/templates/planbench-evaluation-template.md`
- `docs/governance/16-deliberative-planning-and-council-mode.md`
- `docs/governance/17-codex-bounded-implementation-fabric.md`

## Anti-patterns

- Treating high research-quality scores as proof of correct
  decisions — research quality and decision quality are
  independent.
- Using the scoreboard to rank agents against each other in
  isolation. Use it to surface systemic drift.
- Failing to retire scoring dimensions that produce noise.
- Publishing a PlanBench score externally before N ≥ 8 has
  accumulated per the falsifiability rule.
- Re-tuning a PlanBench challenge to favor the current model
  mid-evaluation (drift the rubric, not the run).
