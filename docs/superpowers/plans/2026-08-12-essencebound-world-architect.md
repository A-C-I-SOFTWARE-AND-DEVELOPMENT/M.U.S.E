# Essencebound World Architect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, validate, train, evaluate, gate, and conditionally register the `needle-eb-world-architect` Needle 2 specialist from the attached Essencebound master specification.

**Architecture:** Add a focused `foundry.essencebound_world` package that compiles the source prompt into auditable requirements, generates a deterministic enriched/native dataset ladder, validates isolation and quality, renders bounded tool calls into concise decisions, and scores real Needle artifacts. Reuse the existing generic Foundry registry, hashing, evaluation, Needle training, and WSL2 compute path.

**Tech Stack:** Python 3.11, pytest, Needle 2 native `build_schema`/`Field`, JSON/JSONL, JAX/LoRA through the vendored Needle CLI, WSL2 CUDA, existing `foundry` modules.

## Global Constraints

- Preserve unrelated dirty-worktree changes and stage only files owned by this implementation.
- Use at most four native macro-tools and train off-topic inputs to `answers: []`.
- Use deterministic IDs `eb_world_000001` through `eb_world_004000` and exact rung supersets 250/500/1000/2000/4000.
- Keep train/validation/test, QA, and holdout semantic families isolated.
- Require at least 30% failure examples and at least 15% adversarial or missing-evidence examples.
- Never train hidden chain-of-thought; `reasoning` is one brief evidence derivation.
- Stop at the first failed dataset, training, evaluation, QA, holdout, or Foundry gate.
- Register only an artifact backed by measured passing results.

---

### Task 1: Native schemas, ontology, and deterministic renderer

**Files:**
- Create: `foundry/essencebound_world/__init__.py`
- Create: `foundry/essencebound_world/schemas.py`
- Create: `foundry/essencebound_world/ontology.py`
- Create: `foundry/essencebound_world/renderer.py`
- Test: `tests/foundry/test_essencebound_world.py`

**Interfaces:**
- Produces: `tool_schemas() -> list[dict]`, `tool_names() -> set[str]`, `ontology_payload() -> dict`, and `render_decision(answer: dict) -> str`.
- Consumes: `needle.agent.tools.build_schema`, `Field`, and Python `Literal`/`Annotated` types.

- [ ] **Step 1: Write failing schema and renderer tests**

```python
def test_native_schema_contract_and_tool_ceiling():
    schemas = tool_schemas()
    assert 1 <= len(schemas) <= 4
    assert all("parameters" in schema and "arguments" not in schema for schema in schemas)

def test_renderer_is_concise_and_evidence_aware():
    answer = {"name": "request_world_verification", "arguments": {
        "evidence_kind": "PERFORMANCE_MEASUREMENT", "claim_kind": "PERFORMANCE_PASS",
        "category": "PERFORMANCE", "next_gate": "RUN_PERFORMANCE_GATE"}}
    text = render_decision(answer)
    assert text.startswith("UNVERIFIED | PERFORMANCE")
    assert "measurement" in text.lower()
```

- [ ] **Step 2: Run the focused test and confirm it fails because the package is absent**

Run: `.venv\Scripts\python.exe -m pytest tests/foundry/test_essencebound_world.py -q`  
Expected: FAIL during import of `foundry.essencebound_world`.

- [ ] **Step 3: Implement four native schemas, bounded ontology constants, and deterministic rendering**

Implement exactly these tool names: `assess_world_state`, `prioritize_world_action`, `evaluate_world_constraint`, and `request_world_verification`. Use bounded enum values from `ontology.py`; render every tool through templates and raise `ValueError` on unknown codes.

- [ ] **Step 4: Run focused tests**

Run: `.venv\Scripts\python.exe -m pytest tests/foundry/test_essencebound_world.py -q`  
Expected: PASS for schema and renderer tests.

- [ ] **Step 5: Commit the focused component**

```powershell
git add foundry/essencebound_world tests/foundry/test_essencebound_world.py
git commit -m "feat(foundry): add Essencebound specialist contract"
```

### Task 2: Master-spec requirements compiler

**Files:**
- Create: `foundry/essencebound_world/requirements.py`
- Modify: `tests/foundry/test_essencebound_world.py`

**Interfaces:**
- Consumes: the attached source prompt path supplied to `compile_requirements`.
- Produces: `parse_sections(text: str) -> list[SourceSection]`, `compile_requirements(text: str) -> list[dict]`, and `write_requirements(source: Path, output: Path) -> dict`.

- [ ] **Step 1: Add failing tests for section coverage and requirement fields**

```python
def test_requirements_cover_full_numbered_source(master_prompt_text):
    rows = compile_requirements(master_prompt_text)
    sections = {row["source_section_number"] for row in rows}
    assert set(range(83)).issubset(sections)
    assert all({"requirement_id", "requirement", "category", "severity",
                "testability", "required_evidence", "rule_kind"} <= row.keys() for row in rows)
```

- [ ] **Step 2: Run the test and verify the missing compiler failure**

Run: `.venv\Scripts\python.exe -m pytest tests/foundry/test_essencebound_world.py -q`  
Expected: FAIL because `compile_requirements` is not defined.

- [ ] **Step 3: Implement numbered-section parsing, atomic directive extraction, stable IDs, and classification**

Parse headings `# 0.` through `# 82.`, keep list items and imperative/declarative rule sentences, normalize whitespace, classify the 40 domain categories through ordered keyword rules, and mark sections 0–29 as domain/design or mutable-state rules and 30–82 as foundry/process rules. Preserve `source_excerpt_hash` instead of copying long passages into examples.

- [ ] **Step 4: Run focused tests and compile a temporary requirements artifact**

Run: `.venv\Scripts\python.exe -m pytest tests/foundry/test_essencebound_world.py -q`  
Expected: PASS, including all 83 numbered sections.

- [ ] **Step 5: Commit the compiler**

```powershell
git add foundry/essencebound_world/requirements.py tests/foundry/test_essencebound_world.py
git commit -m "feat(foundry): compile Essencebound requirements"
```

### Task 3: Capability-dense dataset and isolated ladder generator

**Files:**
- Create: `foundry/essencebound_world/scenarios.py`
- Create: `foundry/essencebound_world/generator.py`
- Modify: `tests/foundry/test_essencebound_world.py`

**Interfaces:**
- Consumes: requirement rows, `ontology_payload()`, and `tool_schemas()`.
- Produces: `generate_canonical(requirements: list[dict], count: int = 4000) -> list[dict]`, `build_ladder(rows: list[dict]) -> dict[int, dict[str, list[dict]]]`, `generate_qa(rows, sizes)`, and `generate_holdout(requirements, count)`.

- [ ] **Step 1: Add failing determinism, balance, superset, and isolation tests**

```python
def test_ladder_is_deterministic_balanced_and_superset(requirements):
    a = generate_canonical(requirements, 4000)
    b = generate_canonical(requirements, 4000)
    assert a == b
    assert [r["id"] for r in a] == [f"eb_world_{i:06d}" for i in range(1, 4001)]
    assert sum("FAIL" in r["expected_labels"] for r in a) / 4000 >= 0.30
    ladder = build_ladder(a)
    assert set(row["id"] for split in ladder[250].values() for row in split) <= \
           set(row["id"] for split in ladder[500].values() for row in split)
```

- [ ] **Step 2: Run the test and confirm generator imports fail**

Run: `.venv\Scripts\python.exe -m pytest tests/foundry/test_essencebound_world.py -q`  
Expected: FAIL because generator/scenario modules are absent.

- [ ] **Step 3: Implement scenario families and deterministic generation**

Create scenario families spanning all 40 categories and ten example types. Vary meaningful factors such as hero location, island function, object role, connection type, evidence availability, dimensions, instance counts, stage, and failure magnitude. Store `semantic_family` separately from surface wording so group-based splitting prevents leakage.

- [ ] **Step 4: Implement stable group partitioning, QA families, and holdout families**

Use a SHA-256 family bucket for 80/10/10 assignment while deterministically satisfying exact rung counts. QA IDs start `eb_world_qa_`; holdout IDs start `eb_world_holdout_`; neither source family can appear in canonical training rows.

- [ ] **Step 5: Run focused tests**

Run: `.venv\Scripts\python.exe -m pytest tests/foundry/test_essencebound_world.py -q`  
Expected: PASS for 4,000-row generation, all rungs, balances, and isolation.

- [ ] **Step 6: Commit the generator**

```powershell
git add foundry/essencebound_world/scenarios.py foundry/essencebound_world/generator.py tests/foundry/test_essencebound_world.py
git commit -m "feat(foundry): generate Essencebound dataset ladder"
```

### Task 4: Dataset validator and coverage reports

**Files:**
- Create: `foundry/essencebound_world/validator.py`
- Modify: `tests/foundry/test_essencebound_world.py`

**Interfaces:**
- Produces: `validate_example(row, ontology, schemas) -> list[str]`, `validate_artifacts(root: Path) -> dict`, and `coverage_matrix(rows_by_rung) -> dict`.

- [ ] **Step 1: Add planted-failure tests**

```python
@pytest.mark.parametrize("mutation,code", [
    (lambda r: r.update(id="eb_world_000002"), "duplicate_id"),
    (lambda r: r["answers"][0].update(name="unknown"), "unknown_tool"),
    (lambda r: r.update(reasoning="show hidden chain of thought"), "chain_of_thought"),
])
def test_validator_fails_closed(valid_rows, mutation, code):
    rows = copy.deepcopy(valid_rows)
    mutation(rows[0])
    assert code in json.dumps(validate_rows(rows, ontology_payload(), tool_schemas()))
```

- [ ] **Step 2: Run tests and confirm missing validator failure**

Run: `.venv\Scripts\python.exe -m pytest tests/foundry/test_essencebound_world.py -q`  
Expected: FAIL because validator functions are absent.

- [ ] **Step 3: Implement schema, ontology, balance, leakage, dedupe, Unicode, length, source-leakage, and rung-superset checks**

Treat every violation as an error unless explicitly classified as an informational statistic. Compute exact duplicate and normalized scenario duplicate rates. Require every one of the 40 categories at rung 250 and apply rare-requirement minimums from the ontology.

- [ ] **Step 4: Run focused tests**

Run: `.venv\Scripts\python.exe -m pytest tests/foundry/test_essencebound_world.py -q`  
Expected: PASS, including every planted failure.

- [ ] **Step 5: Commit validation**

```powershell
git add foundry/essencebound_world/validator.py tests/foundry/test_essencebound_world.py
git commit -m "feat(foundry): validate Essencebound specialist data"
```

### Task 5: Domain evaluation and fail-closed gate

**Files:**
- Create: `foundry/essencebound_world/evaluation.py`
- Modify: `tests/foundry/test_essencebound_world.py`

**Interfaces:**
- Consumes: gold/predicted native answer envelopes.
- Produces: `evaluate_domain(golds, predictions) -> dict`, `domain_gate(metrics, baseline=None) -> dict`, and `critical_failures(golds, predictions) -> list[dict]`.

- [ ] **Step 1: Add metric and critical-failure tests**

```python
def test_one_false_completion_blocks_gate(gold_predictions):
    golds, preds = gold_predictions
    preds[0] = completion_pass_prediction_without_evidence()
    metrics = evaluate_domain(golds, preds)
    gate = domain_gate(metrics)
    assert metrics["critical_failure_count"] == 1
    assert not gate["ALL_PASS"]
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/foundry/test_essencebound_world.py -q`  
Expected: FAIL because domain evaluation is absent.

- [ ] **Step 3: Implement verdict, category, action, evidence, priority, false-completion, constraint, schema, and critical-failure scoring**

Set gates from the approved design: schema validity 1.0, wrong-domain execution 0.0, critical failures 0, evidence discipline at least 0.95, and other accuracy thresholds recorded in the emitted gate file. Require tuned exact accuracy to exceed stock by a nonzero measured margin before promotion.

- [ ] **Step 4: Run focused and generic Foundry tests**

Run: `.venv\Scripts\python.exe -m pytest tests/foundry/test_essencebound_world.py tests/foundry/test_foundry.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit evaluation**

```powershell
git add foundry/essencebound_world/evaluation.py tests/foundry/test_essencebound_world.py
git commit -m "feat(foundry): gate Essencebound model behavior"
```

### Task 6: Artifact builder and measured-report pipeline

**Files:**
- Create: `foundry/essencebound_world/pipeline.py`
- Create: `foundry/essencebound_world/cli.py`
- Create: `tests/foundry/test_essencebound_pipeline.py`
- Generate: `Training/Needle/EB_World_Architect/**`

**Interfaces:**
- Produces CLI commands `build-data`, `validate`, `train-rung`, `evaluate-rung`, `report`, and `run`.
- Uses explicit paths and subprocess argument arrays; secrets never enter reports.

- [ ] **Step 1: Write failing end-to-end data-build tests**

```python
def test_build_data_writes_complete_valid_tree(tmp_path, master_prompt_path):
    result = build_data(master_prompt_path, tmp_path)
    assert result["validation"]["passed"]
    assert (tmp_path / "source" / "requirements.json").exists()
    assert sum(1 for _ in open(tmp_path / "rung_0250" / "train.jsonl", encoding="utf-8")) == 200
```

- [ ] **Step 2: Run the integration test and verify the pipeline is absent**

Run: `.venv\Scripts\python.exe -m pytest tests/foundry/test_essencebound_pipeline.py -q`  
Expected: FAIL during pipeline import.

- [ ] **Step 3: Implement atomic artifact writes, hashes, manifests, report generation, and CLI**

Write generated content to a sibling temporary directory, validate it, then replace only the named specialist output directory. Report every executed command, exit code, duration, input/output hash, and measurement status. Do not synthesize training or evaluation metrics.

- [ ] **Step 4: Run integration and full focused tests**

Run: `.venv\Scripts\python.exe -m pytest tests/foundry/test_essencebound_pipeline.py tests/foundry/test_essencebound_world.py tests/foundry/test_foundry.py -q`  
Expected: PASS.

- [ ] **Step 5: Build and validate the real 4,000-example artifact tree**

Run: `.venv\Scripts\python.exe -m foundry.essencebound_world.cli build-data --source "C:\Users\Echer\.codex\attachments\7ca63aae-5b7c-4e68-a6dd-a32ba7ce4f4d\pasted-text.txt" --output Training\Needle\EB_World_Architect`  
Expected: exit 0 and `reports/dataset_validation.json` with `passed: true`.

- [ ] **Step 6: Commit source, tests, and deterministic data artifacts**

```powershell
git add foundry/essencebound_world tests/foundry Training/Needle/EB_World_Architect
git commit -m "feat(foundry): build Essencebound training foundry"
```

### Task 7: Real rung training, inference evaluation, and stop gate

**Files:**
- Create when measured: `Training/Needle/EB_World_Architect/rung_*/runs/**`
- Modify when measured: `Training/Needle/EB_World_Architect/reports/gate_results.json`

**Interfaces:**
- Consumes validated native train/eval JSONL and vendored Needle checkpoint.
- Produces actual LoRA adapters, `.cact` models, inference predictions, metrics, logs, and gate decisions.

- [ ] **Step 1: Record and verify the WSL2 training preflight**

Run the CLI preflight to verify the pinned source/checkpoint/tokenizer hashes, f32-LoRA patch marker, WSL CUDA device, free disk space, and engine 2.0.0 availability.  
Expected: all mandatory checks pass; otherwise record `BLOCKED` and stop.

- [ ] **Step 2: Train rung 250 through the verified WSL2 GPU command**

Run: `.venv\Scripts\python.exe -m foundry.essencebound_world.cli train-rung --root Training\Needle\EB_World_Architect --rung 250 --epochs 1 --batch-size 8 --lora-rank 16 --lr 1e-4`  
Expected: finite losses, exit 0, adapter and engine-matched model hashes recorded.

- [ ] **Step 3: Evaluate stock and tuned artifacts in separate processes**

Run: `.venv\Scripts\python.exe -m foundry.essencebound_world.cli evaluate-rung --root Training\Needle\EB_World_Architect --rung 250`  
Expected: predictions and metrics from real engine calls; no model is loaded twice in one process.

- [ ] **Step 4: Apply core, QA, holdout, critical-failure, and baseline gates**

If any gate fails, write the diagnosis and stop. If all pass, repeat Steps 2–4 for rungs 500, 1000, 2000, and 4000 in order. Never schedule a larger rung before the previous rung gate file reports `ALL_PASS: true`.

- [ ] **Step 5: Commit measured artifacts and gate result**

```powershell
git add Training/Needle/EB_World_Architect
git commit -m "exp(foundry): measure Essencebound Needle ladder"
```

### Task 8: Conditional registration and final verification

**Files:**
- Generate: `Training/Needle/EB_World_Architect/reports/final_report.json`
- Generate: `Training/Needle/EB_World_Architect/reports/FINAL_REPORT.md`
- Generate only on pass: the existing Foundry registry record referenced by the report.

**Interfaces:**
- Consumes: generated manifests, hashes, measured training/evaluation results, and gate decisions.
- Produces: the required final report and either a measured registered candidate or an explicit unregistered failure diagnosis.

- [ ] **Step 1: Generate the final report strictly from artifacts**

Run: `.venv\Scripts\python.exe -m foundry.essencebound_world.cli report --root Training\Needle\EB_World_Architect`  
Expected: all required fields are populated from files; unavailable metrics are explicit `UNVERIFIED`, never numeric placeholders.

- [ ] **Step 2: Register only if every production gate passed**

Use `FoundryRegistry` and `SpecialistRecord` with identity `needle-eb-world-architect`, domain `essencebound-world`, role `environment_architecture_specialist`, full artifact hashes, measured metrics, and the actual winning rung. If the gate failed, leave registry status `UNREGISTERED_GATE_FAILED`.

- [ ] **Step 3: Run complete verification**

Run: `.venv\Scripts\python.exe -m pytest tests/foundry -q`  
Run: `.venv\Scripts\python.exe -m foundry.essencebound_world.cli validate --root Training\Needle\EB_World_Architect`  
Run: `git diff --check`  
Expected: all tests and artifact validators pass; final report agrees with manifests and registry state.

- [ ] **Step 4: Commit the final measured report and any permitted registry entry**

```powershell
git add Training/Needle/EB_World_Architect
git commit -m "docs(foundry): report Essencebound specialist result"
```
