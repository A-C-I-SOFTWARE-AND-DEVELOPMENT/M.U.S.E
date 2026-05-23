---
name: research-validator
description: "Score and flag the evidence cited in a decision ledger; surface assumptions, weak sources, and unreproducible claims."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, validation, evidence, decision, ledger, audit, citations, reproducibility]
    related_skills:
      - decision-quality-gate
      - enterprise-orchestrator
      - enterprise-judge
      - enterprise-monitor
      - spike
      - plan
---

# Research Validator

Use this skill to **score the evidence quality** of a decision ledger
and to **flag individual citations** that are weak, undated,
unreachable, or assumption-shaped. The output is consumed by
[`decision-quality-gate`](../decision-quality-gate/SKILL.md), which
uses the score and flags to decide whether the ledger can advance to
`proposed` or `accepted`.

The full system this validator belongs to is described in
[`docs/orchestration/decision-quality-system.md`](../../docs/orchestration/decision-quality-system.md).
The ledger spec is in
[`docs/orchestration/decision-ledger.md`](../../docs/orchestration/decision-ledger.md).
The canonical template is at
[`templates/orchestration/decision-ledger-template.md`](../../templates/orchestration/decision-ledger-template.md).

## Load this skill when

* The user (or the orchestrator) asks to **validate**, **double-check**,
  or **score** a decision ledger.
* You are about to invoke `decision-quality-gate` and the ledger has
  not yet been validated this iteration.
* You want to **audit an old ledger** (e.g. while reviewing why a
  rollback fired). The same scoring applies.

Do **not** load this skill to:

* Critique implementation code — that is `requesting-code-review` or
  `code-review`.
* Re-do the actual research itself — that is `spike`, `web_search`, or
  the relevant domain leaf.
* Override the risk classification — that lives in
  `enterprise.policy.classify`.

## Scoring rubric (0–100)

The validator scores four axes, each out of 25. The total is reported
to one decimal place; the gate uses the integer floor.

### Coverage (0–25) — breadth of evidence

* **25** — Every option cites ≥2 evidence items spanning at least two
  *kinds* (file + command, command + doc, file + web, etc.).
* **20** — Every option cites ≥1 evidence item; ≥1 option cites two
  kinds.
* **15** — Every option cites ≥1 evidence item, single kind.
* **10** — At least half the options cite evidence; the rest are
  un-cited.
* **5** — Evidence section is non-empty but options do not cross-
  reference it.
* **0** — Evidence section is empty or absent.

### Reproducibility (0–25) — could a reader re-run it

* **25** — Every command has a path/selector and an expected
  outcome; every file ref includes line numbers; every web source has
  an access date.
* **20** — Most items reproducible; ≤1 weak item.
* **15** — Half the items reproducible; the other half need
  guesswork.
* **10** — Items are named but not actionable ("ran the tests",
  "checked the docs").
* **5** — Items are gestured at ("did some research").
* **0** — No reproducible references.

### Independence (0–25) — corroboration vs single source

* **25** — Each option's key claims are corroborated by ≥2
  independent sources (different authors, different vendors, or
  primary + secondary).
* **20** — ≥1 option has corroborated claims; the rest rest on a
  single trusted source.
* **15** — Single trusted source per claim, but the source is
  primary / authoritative (official docs, repo source, instrumented
  measurement).
* **10** — Single source per claim, secondary / derivative (blog
  post, third-party summary).
* **5** — Single source, unclear authority.
* **0** — No source named; pure recall.

### Honesty (0–25) — assumptions called as assumptions

* **25** — Open risks block lists every meaningful assumption;
  confidence rating includes the one-sentence "what would have to be
  true for this to be wrong" rationale; no hidden chain-of-thought
  pasted in.
* **20** — Assumptions named; confidence rationale present but
  shallow.
* **15** — Some assumptions named; confidence asserted without
  rationale.
* **10** — Assumptions presented as facts; confidence `high` with no
  rationale.
* **5** — Internal monologue pasted into the body of a section.
* **0** — Body of any section is unsummarised chain-of-thought.

## Per-item flags

For each citation in the Evidence Reviewed list (and each inline
citation in Options), assign at most one *flag*:

| Flag | Meaning | Triggers |
|---|---|---|
| `ok` | Reproducible, dated, authoritative. | All checks pass. |
| `weak_file_ref` | File cited without line numbers. | `path/to/file.py` with no `:L…` or section anchor. |
| `weak_cmd` | Command cited without path/selector or expected outcome. | `pytest`, `npm test`, `grep foo`. |
| `untrusted_unknown_age` | Web source has no access date. | URL without `accessed YYYY-MM-DD`. |
| `unreachable_web` | URL appears wrong / dead / placeholder. | `example.com/…`, obvious typos, 404 patterns. |
| `single_source` | Claim rests on this one item with no corroboration. | Only one citation supports the option. |
| `assumption` | Phrased as evidence but is actually a guess. | "I assume…", "probably…", no source ref. |
| `cot_leak` | Chain-of-thought pasted in. | "Let me think… first I consider…" style prose. |
| `secret_suspect` | Token-shaped string present. | High-entropy hex, `sk-`, `gh[oprsu]_`, JWT-shaped. |
| `unverified_claim` | Specific factual claim with no citation. | Numbers, version constraints, latencies without a source. |

Web access depends on the worker's permitted toolset. When web is not
available, treat missing web sources as `single_source` rather than
`untrusted_unknown_age`, and call out in the report that the ledger
should be revisited from a web-enabled worker if the claim is load-
bearing.

## What you produce

A single structured report. Do **not** edit the ledger; only report.
The orchestrator (or the author) makes edits.

```json
{
  "ledger_id": "2026-05-23_143012-pick-judge-model",
  "scored_at": "2026-05-23T14:42:11Z",
  "scores": {
    "coverage": 22,
    "reproducibility": 21,
    "independence": 19,
    "honesty": 22,
    "total": 84
  },
  "flags": [
    {
      "section": "Evidence Reviewed",
      "item": "https://example.com/post",
      "flag": "untrusted_unknown_age",
      "note": "no access date — add `accessed YYYY-MM-DD`"
    },
    {
      "section": "Options Considered / Option B",
      "item": "claim that Sonnet is 2x faster",
      "flag": "unverified_claim",
      "note": "cite the measurement or downgrade to 'reported faster'"
    }
  ],
  "warnings": [
    "Option B's Cost/latency/quality block is qualitative only; consider noting an order-of-magnitude estimate"
  ],
  "blockers": [],
  "next_actions": [
    "Add an access date to the cited web source.",
    "Corroborate the Sonnet latency claim with a second source or downgrade the wording."
  ]
}
```

* `blockers` are issues that the **decision-quality-gate** will treat
  as hard rejections (any `cot_leak`, any `secret_suspect`, any
  `assumption` masquerading as evidence in an option's "Evidence
  supporting" list).
* `warnings` are soft issues. The gate may pass with `gate_warn`.
* `next_actions` is the actionable list the author needs to address.

## How to validate, step by step

1. **Parse the ledger sections.** Confirm Decision, Context, Evidence
   Reviewed, Options Considered, Selected Model / Worker, Validation
   Plan are present (Final Decision optional unless the author is
   targeting `accepted`).
2. **For each Evidence Reviewed item**, assign a flag.
3. **For each option**, check that every claim in Pros / Cons /
   Risks / Cost-Latency-Quality cites at least one Evidence item.
   Mark uncited claims `unverified_claim`.
4. **Check Selected Model / Worker** sub-fields. Missing sub-fields go
   to `blockers` (gate-fail).
5. **Check Validation Plan** for at least one observable success
   criterion and a named failure response.
6. **Scan for secrets and CoT leaks** across the whole ledger. Any
   hit → `blockers`.
7. **Compute the four axis scores** using the rubric above.
8. **Compose the report.** Surface blockers first, then warnings,
   then next actions.
9. **Hand off to `decision-quality-gate`** with the report. The gate
   compares the total against the risk-tier threshold and decides
   pass / warn / fail.

## What the validator must NOT do

* **Do not edit the ledger.** Report only.
* **Do not run** the commands in the Validation Plan. The validator
  only checks whether the plan *could* be run by an independent
  reader.
* **Do not fetch a secret** to "verify" it. Token-shaped strings are
  always `secret_suspect`, no exceptions.
* **Do not expand chain-of-thought** found in a ledger. Flag it as
  `cot_leak` and let the author summarise it back into structured
  fields.
* **Do not invent corroboration.** If only one source is cited, that
  is `single_source` — do not score independence higher by guessing
  what other sources "probably exist".
* **Do not raise the risk classification.** Risk is set by
  `enterprise.policy.classify`. If the classification looks wrong,
  add a warning suggesting a Monitor proposal — do not override.
* **Do not lower a flag because the conclusion seems plausible.**
  Plausibility is not a substitute for evidence; this validator
  exists precisely because confident-sounding wrong answers are the
  failure mode.

## Tooling

When you have read access (always) and search/web access (worker-
dependent), use:

* `read_file(<ledger path>)` — load the ledger.
* `read_file(<cited path>)` + look for the cited line numbers.
* `terminal(<cited command>)` — only to confirm the command *parses*
  and the path/selector exists, never to actually execute it as
  validation. Prefer a dry-run flag if available.
* `web_extract(urls=[…])` — only when checking that a cited URL is
  reachable and has the claimed content. Do **not** browse to gather
  *new* evidence; that is the spike's / leaf's job.

If the worker has no terminal or web tool, validate what you can and
mark the rest `single_source` with a note that re-validation from a
fuller-toolset worker is recommended.

## Integration

* **`decision-quality-gate`** consumes this report and compares the
  total score against the risk-tier threshold (LOW: 50/60, MEDIUM:
  70/75, HIGH: 85/90 for proposed/accepted).
* **`enterprise-judge`** can call this skill to validate a ledger
  before treating its Validation Plan as ground truth.
* **`enterprise-monitor`** reads the `decision_gate` audit rows and
  the per-ledger scores to detect systemic drift over time.

## Example flag set (illustrative)

```text
section            item                                   flag                      note
─────────────────  ─────────────────────────────────────  ────────────────────────  ─────────────────────────────────────────────
Evidence Reviewed  src/foo.py                             weak_file_ref             add line numbers (e.g. src/foo.py:L42-L88)
Evidence Reviewed  pytest                                 weak_cmd                  add a path/selector and the expected outcome
Evidence Reviewed  https://blog.example.com/llm-bench    untrusted_unknown_age     add `accessed 2026-05-23`
Options / B        "Sonnet is 2x faster than Opus"        unverified_claim          cite a measurement or rephrase
Options / A        "(no citations)"                       single_source             list at least one Evidence Reviewed ref
Final Decision     "we'd figure rollback out later"       (gate-level reject)       rollback must be concrete (trigger/action/owner)
anywhere           "sk-live-…"                            secret_suspect            never inline secrets in a ledger
```

## What the user sees

The validator output is meant to be machine-readable for the gate,
but Hermes should also surface a short human summary:

```
RESEARCH VALIDATOR: score 84/100 (coverage 22, reproducibility 21, independence 19, honesty 22)
  blockers: 0
  warnings: 1 — Option B cost/latency/quality is qualitative only
  next: add access date to cited web source; corroborate Sonnet latency claim
```

No internal monologue. Every line points at the section the author
needs to touch.
