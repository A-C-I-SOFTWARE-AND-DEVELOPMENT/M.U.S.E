# Evidence Bundle — <short title>

**Date:** YYYY-MM-DD
**Author:** research-evidence-bureau
**Run folder:** `docs/aos/runs/YYYY-MM-DD-<slug>/`
**Artifact slot:** `01-evidence-bundle.md`
**Companion governance:** `docs/governance/05-research-dossier-standard.md`,
`docs/governance/16-deliberative-planning-and-council-mode.md`

> The Evidence Bundle assembles the facts the council planners and
> red-team will rely on. Citations must be a third party can verify
> per `governance/05`. Every claim used by a plan must trace back
> to an item here. Items go through one of three sections —
> internal, external, or metadata.

## Decision question

<one sentence — what decision this bundle supports>

## A. Internal evidence (T1 trusted-reference reads)

| Fact / state | Source path | Date checked | Notes |
|---|---|---|---|
| <e.g. baseline test count is 727/727> | `docs/releases/v1.0.0-enterprise-ready.md` | YYYY-MM-DD | |
| | | | |

Cross-references:

- Live code paths to read first:
- Tests covering the surface:
- ADRs that bind:
- Compliance evidence:
- Open PRs touching this surface:
- SKIPPED.md entries:
- Past retrospectives:
- Commercial source-of-truth:
- Claims-policy constraints (C1–C6 per `governance/11`):

## B. External evidence (T1 with date)

| Source | Citation | URL | Access date | Binding vs advisory |
|---|---|---|---|---|
| 49 CFR §___ | | | YYYY-MM-DD | binding |
| TDG ¶___ | | | YYYY-MM-DD | binding |
| NIST SP ___ | | | YYYY-MM-DD | advisory |
| OWASP ___ | | | YYYY-MM-DD | advisory |
| ISO/IEC ___ | | | YYYY-MM-DD | advisory |
| Vendor doc: ___ | | | YYYY-MM-DD | advisory |

Notes on the external set:

- Contradictions found (run `source-contradiction-analysis` skill
  if two sources disagree):
- Sources cited but not yet read in full:
- Sources where the cited section pre-dates the current revision:

## C. Evidence metadata

For each evidence item used by plans, capture:

| Item ID | Confidence (low/med/high) | Relevance to decision | Falsifiability |
|---|---|---|---|
| | | | |

## Practitioner friction (non-authoritative)

<only directional; not used to override binding evidence>

## What this bundle does NOT cover

- <gap 1>
- <gap 2>

If a gap blocks the council, escalate to the owner before generating
plans rather than letting a planner improvise.

## Linkage

- Mission Brief: `00-mission-brief.md`
- Research Dossier (if separate): `docs/research/____.md`
- Risk classification: `02-risk-classification.md`

## Verdict

**Sufficient / Sufficient-with-caveats / Insufficient** — <one
sentence why; if Insufficient, list what's missing and the gating
research>
