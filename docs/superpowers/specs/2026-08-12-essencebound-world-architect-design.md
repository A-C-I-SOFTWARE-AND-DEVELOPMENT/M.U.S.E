# Essencebound World Architect Specialist Design

**Date:** 2026-08-12  
**Status:** Approved  
**Approval:** The user approved the native Needle tool-call plus deterministic MUSE renderer design and requested execution without follow-up pauses.

## Objective

Build, train, evaluate, and gate `needle-eb-world-architect`, a narrow Needle 2 specialist for Essencebound environment-architecture decisions. The specialist classifies world-building states, detects failures, selects the smallest safe correction, prioritizes production work, and identifies missing evidence. It never executes Blender or Unreal changes and never claims repository, scene, test, performance, or visual state without evidence.

## Grounded Constraints

- Use the existing M.U.S.E. Foundry, vendored Needle 2 pipeline, registry, belief ledger, and evaluation infrastructure.
- Preserve all unrelated and pre-existing work in the dirty checkout.
- Needle 2 training rows must use its verified native contract: `query`, `reasoning`, `answers`, and native schemas produced through `needle.agent.tools.build_schema` / `Field`.
- Keep no more than five macro-tools available to the specialist because the top-five retrieval ceiling is measured locally.
- Keep examples short enough for the verified Needle context limits; target answers are 10–80 words and complex cases may reach 150 words only in rendered reports, not in model-internal monologues.
- Do not train hidden chain-of-thought. The `reasoning` field is one short evidence citation or argument derivation, not an internal monologue.
- Use deterministic IDs `eb_world_000001` through `eb_world_004000`; every rung is an exact superset of the preceding rung.
- Treat the attached Essencebound source prompt as design-source material, not as proof of current repository, Blender, Unreal, or performance state.
- Use the verified WSL2 CUDA/JAX path for real training and the engine/container pairing documented in `docs/foundry/TRAINING_RUNBOOK.md`.
- Stop advancement at the first failed Foundry gate. Never register or activate a specialist that has not passed all required measured gates.

## Architecture

The implementation adds an Essencebound-specific package under `foundry/essencebound_world/`. It compiles the master specification into atomic requirements, a bounded ontology, canonical enriched examples, Needle-native training rows, independent evaluation pools, and measured reports. Existing generic Foundry modules remain the authority for artifact hashing, registry lifecycle, and low-level Needle evaluation; Essencebound-specific validation and scoring are layered on top.

Needle produces bounded structured calls. MUSE converts a validated call into the concise user-facing form required by the brief, such as `FAIL | TRAVERSAL` followed by a deterministic corrective sentence. This keeps classification and selection inside the tiny specialist while leaving language realization and evidence wording to a testable harness.

## Specialist Tool Contract

The specialist receives four native macro-tools:

1. `assess_world_state(verdict, category, issue_code, action_code, evidence_state)` classifies a state and selects its smallest safe correction.
2. `prioritize_world_action(stage, priority_code, blocker_code, evidence_state)` identifies the next production gate.
3. `evaluate_world_constraint(constraint_code, observed_value, limit_value, unit, verdict, action_code, evidence_state)` handles dimensions, scale, counts, grade, and performance budgets.
4. `request_world_verification(evidence_kind, claim_kind, category, next_gate)` refuses unsupported completion or implementation claims and names the verification required.

Off-topic or out-of-scope inputs train to `answers: []`; there is no generic fallback tool. Arguments use bounded enumerations wherever possible. Codes are defined in the ontology and rendered by deterministic templates. Schema generation uses Needle’s native `build_schema` implementation and is covered by tests that reject the broken `arguments` dialect.

## Data Model

Every canonical row contains the brief’s audit metadata plus Needle-native fields:

```json
{
  "id": "eb_world_000001",
  "specialist": "NEEDLE-EB-WORLD-ARCHITECT",
  "category": "03_traversal",
  "difficulty": "medium",
  "source_tags": ["bridge", "landing"],
  "requirement_ids": ["EB-TRAV-001"],
  "example_type": "correction",
  "expected_labels": ["FAIL", "TRAVERSAL"],
  "query": "The Archive bridge ends four meters above its plaza with no stairs. Is the route valid?",
  "reasoning": "The destination has no traversable landing.",
  "answers": [{"name": "assess_world_state", "arguments": {"verdict": "FAIL", "category": "TRAVERSAL", "issue_code": "MISSING_LANDING", "action_code": "ADD_VALID_LANDING", "evidence_state": "SUPPORTED_BY_INPUT"}}],
  "tools": []
}
```

The compiler fills `tools` with the same deterministic native schemas in every training row. Rich metadata remains available to coverage and QA tooling; Needle’s loader consumes only its native fields.

## Requirements and Ontology

`requirements.json` atomizes the full source corpus. Each requirement records its stable ID, source section, normalized rule, category, severity, testability, required evidence, positive/negative/adversarial example targets, and whether it is a durable design rule or a mutable project-state claim.

`ontology.json` defines all legal categories, verdicts, completion states, evidence states, issue codes, action codes, constraints, example types, stages, labels, and deterministic rendering templates. Rare blocking requirements receive explicit minimum coverage so that teleport facing, warm-interior contrast, bridge grade, rail height, destruction exemptions, localized HISM bounds, player-eye QA, fog misuse, human-scale architecture, dormant Essence states, building approaches, and staging discipline cannot disappear at larger rungs.

## Dataset Ladder

The canonical pool contains 4,000 capability-dense examples. Rungs select the first 250, 500, 1,000, 2,000, and 4,000 canonical IDs. Selection is deterministic and curriculum-aware, while retaining exact supersets.

Each rung is partitioned into 80% train, 10% validation, and 10% test using stable semantic-family groups so paraphrase siblings never cross splits. The permanent holdout and the QA ladder are generated from separate scenario families and IDs and are never eligible for training. Negative and adversarial cases meet or exceed 30% overall, with at least 15% dedicated adversarial or missing-evidence cases.

Generation combines hand-authored templates over the normalized requirement/ontology codes with deterministic scenario parameters. This avoids padding, source-prompt leakage, and dependence on an unavailable teacher. If a configured teacher is later used for surface variation, generated candidates remain quarantined until deterministic validation passes and provenance identifies the teacher provider/model.

## Validation

The dataset validator fails closed on:

- malformed JSONL, duplicate IDs, blank fields, illegal roles or labels, missing specialist tags, or unknown ontology codes;
- non-native tool schemas, unknown tools, invalid arguments, oversized examples, malformed Unicode, or chain-of-thought requests;
- train/validation/test/QA/holdout family leakage, exact duplicates, near-duplicate scenarios, or rung-superset violations;
- missing category/rare-requirement coverage, insufficient negative/adversarial balance, mutable project-state claims presented as facts, or copied source-prompt passages;
- corrections that contradict the associated requirement, destructive actions without replacement, or unsupported PASS/AAA-complete labels.

Validation emits machine-readable statistics, coverage matrices, duplicate reports, isolation results, and a pass/fail summary. Generated data is not trained unless every required check passes.

## Evaluation and Gates

Evaluation runs the same native schemas and rows against stock and tuned artifacts. In addition to generic Foundry metrics, Essencebound scoring measures verdict accuracy, domain accuracy, corrective-action accuracy, evidence discipline, priority accuracy, false-completion safety, constraint accuracy, schema validity, and critical-failure count.

Promotion requires all configured thresholds, zero critical failures, zero train/holdout leakage, schema validity of 1.0, wrong-domain execution of 0.0, and meaningful improvement over the stock baseline. Training proceeds rung by rung and stops on a failed gate or non-improving learning curve. A failed rung produces diagnosis and reports but no larger-rung training.

## Artifacts

The canonical output root is `Training/Needle/EB_World_Architect/`, matching the requested structure because the existing repository has no conflicting specialist-dataset root. It contains source requirements and ontology, rung splits, QA rungs, holdout, generated schemas, reports, adapters/models/evaluation records produced by actual runs, and a README with reproducible commands.

`reports/final_report.json` and `reports/FINAL_REPORT.md` contain only values read from generated files or measured runs: specialist, rung, split counts, coverage, duplicate rate, training result, core evaluation, QA, holdout, gate status, model artifact, and registry status.

## Failure Handling

- Dataset validation failure: quarantine the rows, record the exact violations, and do not train.
- Training loss NaN or process failure: stop the rung, preserve logs, verify the f32 LoRA patch and compute path, and do not evaluate a partial artifact.
- Export or engine-load failure: enforce the documented container/engine pairing and mark the artifact unusable.
- Evaluation or critical-behavior failure: stop ladder advancement and record a dataset/schema diagnosis.
- Missing credentials or unavailable optional teacher: use deterministic generation; never invent teacher output.
- Missing measurement: report `UNVERIFIED`, `INSUFFICIENT_EVIDENCE`, or `REQUIRES_MEASUREMENT` as applicable.

## Verification Strategy

Development follows test-first changes. Unit tests cover requirements compilation, native schemas, deterministic example generation, split isolation, supersets, all validator failures, renderer output, category metrics, gate behavior, and registry refusal. Integration tests build rung 250, validate every artifact, perform a one-process-per-model evaluation probe, and confirm that a planted critical error blocks promotion. The final report is regenerated from artifacts after every measured run.
