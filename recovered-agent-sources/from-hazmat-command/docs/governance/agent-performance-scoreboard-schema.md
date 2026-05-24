# Agent Performance Scoreboard Schema

**Status:** Installed 2026-05-17
**Companion to:** `docs/governance/13-agent-evaluation-and-scoreboard.md`

This is the schema for agent run scoring. It is a framework; it
does not contain numerical results today (see
`governance/13` "No fabricated analytics").

## Per-run entry

| Field | Type | Source | Notes |
|---|---|---|---|
| Run ID | string | retrospective slug | `YYYY-MM-DD-<slug>` |
| Date | date | retro | |
| Division(s) | enum[] | retro | one or more of the 10 AEO divisions |
| Agent(s) | string[] | retro | named roles |
| Topology | enum | workflow router intake | single / chain / routed / parallel / orchestrator / loop / full |
| RC class | enum | PR | RC0–RC4 |
| Affected RC3 surfaces | string[] | PR | per `governance/03` |
| Research dossier present | bool | PR | required for RC3 |
| Maker-checker captured | bool | PR | required for RC3 |
| Verifier captured | bool | PR | required for security/compliance/legal/commercial RC3 |
| New tests added | int | git diff | |
| Negative tests included | bool | retro | |
| Existing tests still pass | bool | CI | required |
| Compliance evidence updated | bool | PR | only if applicable |
| Stub inventory updated | bool | PR | only if applicable |
| Doc freshness corrections | int | retro | how many stale references reconciled in this run |
| Defect escape (within 7 days) | bool | follow-on | filled in 7 days later |
| Rework within 7 days | bool | follow-on | revert / hotfix |
| Confidence at completion | enum | retro | High / Medium / Low |
| What worked | text | retro | |
| What didn't | text | retro | |
| Recommended improvements | text | retro | feed into Prompt Evolution Agent |

## Quarterly rollup

| Aggregate | How computed |
|---|---|
| Run count by division | count |
| Run count by topology | count |
| Run count by RC class | count |
| Median research-dossier presence rate for RC3 runs | mean(bool) |
| Median maker-checker capture rate for RC3 runs | mean(bool) |
| Median negative-test inclusion for new test additions | mean(bool) |
| Defect escape rate (RC3 runs) | sum(escape=true) / count |
| Rework rate (all runs) | sum(rework=true) / count |
| Doc freshness corrections per run | sum / count |
| Confidence vs. defect-escape calibration | crosstab |

## Patterns to watch for

- A division whose RC3 runs have **maker-checker capture rate
  < 90%** — likely shipping unsafe.
- A topology with **defect escape rate** materially higher than
  others — topology mismatch.
- **Negative-test inclusion < 50%** for security RC3 changes —
  Assurance Office discipline gap.
- **Doc freshness corrections per run = 0** consistently — Doc
  Freshness Auditor under-activated.
- High Confidence + frequent defect escape — overconfidence
  pattern; tighten Confidence rubric.

## Storage

- Per-run entries live in the retrospective itself
  (`docs/research/retros/<YYYY-MM-DD>-<slug>.md`).
- Quarterly rollups live in
  `docs/research/scoreboard/<YYYY-Q*>-rollup.md` once data
  exists.

## Anti-patterns

- Filling in metric fields with guesses to make the schema look
  populated.
- Treating any single run's score as a signal — these are
  aggregate patterns.
- Adding scoring fields without first observing the gap they're
  trying to measure.
