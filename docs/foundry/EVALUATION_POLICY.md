# EVALUATION POLICY

## Pools (§20)

| Pool | Purpose | Source |
|---|---|---|
| EVAL_STANDARD | held-out normal distribution | cluster-safe split via `foundry/dataset.py` |
| EVAL_HARD | rare combos, hard argument extraction | curated + teacher-generated |
| EVAL_ADVERSARIAL | off-topic / adjacent / conflicting / malformed / trick | mandatory ≥15% of every set |
| EVAL_RUNTIME_SHADOW | recent real requests, privacy-scrubbed, never trained on before that cycle | runtime capture |

## Gates (§22) — implemented in `foundry/evaluation.py:GATES`

exact_call_accuracy ≥ 0.90 (target 0.95) · argument_value_accuracy ≥ 0.95 ·
empty_call_recall ≥ 0.95 · optional_field_hallucination ≤ 0.02 ·
schema_validity_rate = 1.00 · wrong_domain_execution_rate = 0.00 ·
verification_escape_rate = 0.00 (release, non-negotiable).

## Baseline protocol (§25/§26)

Same engine, same schemas, same eval rows for stock vs tuned vs (optionally) local-general and
provider baselines. A tuned artifact that does not beat its stock baseline meaningfully does not ship.

## Current measured state (QA probe, n=10 held-out, native dialect, engine-matched)

| metric | stock | tuned(26ex/3ep) | gate |
|---|---|---|---|
| exact_call_accuracy | 0.50 | 0.50 | 0.90 ✗ |
| function_selection_accuracy | 0.70 | 0.70 | — |
| argument_value_accuracy | 1.00 | 1.00 | 0.95 ✓ |
| empty_call_recall | 0.60 | 0.60 | 0.95 ✗ |
| wrong_domain_execution_rate | 0.40 | 0.40 | 0.00 ✗ |
| schema_validity_rate | 1.00 | 1.00 | 1.00 ✓ |

**Verdict: NEEDLE-QA does NOT ship.** Dataset ladder + retrieval-aware schema design must rerun
before re-evaluation. The gate doing its job is a valid Foundry result (§107).

## Calibration (§24)

The confidence head currently fails separation (belief `needle.confidence_gates` = REFUTED).
Reliability curves must be produced per-specialist before any confidence threshold is used at runtime.

## NEEDLE-ERA (S6) probe verdict — 2026-08-12

Reference-fed extraction over supplied text: mechanically works on short references but
stock accuracy is below gate (field conflation era/region, degenerate array fills,
duplicate calls, empty call when reference + schema approach the 256-token window).
Per §13 S6 policy: **HIGH RISK / REFERENCE-FED ONLY, does not ship on stock.**
Options in order: (1) train a real ERA set with bounded excerpts (§84/§85), (2) kill ERA
and route period profiling to the provider layer. Decision deferred to the dataset-ladder run;
until then ERA is registry-blocked.
