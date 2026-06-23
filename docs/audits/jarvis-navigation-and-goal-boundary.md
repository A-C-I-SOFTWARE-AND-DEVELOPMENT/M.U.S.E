# muse — Navigation Layer & Goal Boundary (build report)

Branch: `claude/jarvis-prime-architecture-RmmXr`
Date: 2026-05-29

This report covers the slice of the "muse apex" mission delivered on
this branch, and — per the hard-truth rules — an honest account of what was
**deliberately not duplicated** because it is already in flight elsewhere.

## What shipped here (with tests)

### Phase 3 — HyperAgent-style Navigator (`hermes_cli/jarvis_prime/navigation/`)

A first-class, deterministic repository navigation layer. **No LLM is used for
localization** — every ranking fuses lexical, path, symbol, test, and
git-history signals, and every decision is explainable and auditable.

| File | Responsibility |
|---|---|
| `repo_index.py` | Walks a repo once, classifies files (source/test/config/doc/other), language, size, line count. Prunes vendored dirs. |
| `symbol_graph.py` | AST-parses Python (regex for JS/TS) → symbol→file map + import edges + reverse-import lookup. |
| `code_map.py` | Compact, token-bounded "repo map" artifact for workers/owner. |
| `dependency_trace.py` | For a source file: ranked likely tests (naming/mirrored-path/symbol-ref/import-edge) + dependents (blast radius). |
| `issue_localizer.py` | Ranks files for a natural-language request via 5 weighted signals; returns per-signal breakdown. |
| `edit_site_ranker.py` | Turns localizations into worker-ready edit-site packets (symbols, tests to run, dependents, rationale). |
| `navigator.py` | Facade: `localize` / `trace_tests` / `edit_sites` / `navigate`; emits a **worker packet** and a **decision-ledger record**. |

Tests (all passing): `tests/test_navigation_repo_index.py`,
`tests/test_issue_localizer.py`, `tests/test_edit_site_ranker.py`.

Example:

```python
from hermes_cli.jarvis_prime.navigation import Navigator

nav = Navigator.for_repo(".")
result = nav.navigate("fix the timeout in the issue localizer")
packet = result.worker_packet()          # hand to Claude Code / Codex / Aider / Goose / local model
ledger = result.to_ledger_record(job_id="job-123")  # append to ~/.hermes/jobs/<id>/ledger
```

### Phase 4 — Goal Boundary Layer (`hermes_cli/jarvis_prime/goal_boundary.py`)

Paperclip governance: an autonomous loop **must** declare an objective,
allowed/forbidden actions, stop conditions, iteration/cost ceilings, an
owner-approval threshold, and a rollback plan. A loop with *no* stop
conditions is refused (`BoundaryError`). `LoopController.tick()` returns a
`CONTINUE` / `STOP` / `NEEDS_OWNER_APPROVAL` verdict each iteration, composes
with the existing `OWNER_GATED_ACTIONS` + exact authorization phrase, and
records an auditable history (`ledger_records()`).

Tests (all passing): `tests/test_goal_boundary.py`.

## Capability table (honest)

| Capability | Status | Where |
|---|---|---|
| HyperAgent-style navigator | **shipped (tested)** | `navigation/` (this branch) |
| Goal Boundary / runaway-loop governance | **shipped (tested)** | `goal_boundary.py` (this branch) |
| Memory Tree store (layers, provenance, contradictions) | **in open PR #177** — not duplicated | `jarvis_prime/memory_tree.py` (other branch) |
| TokenJuice context compiler | **in open PR #177** — not duplicated | `jarvis_prime/tokenjuice.py` (other branch) |
| Research Vault | **in open PR #177** — not duplicated | `jarvis_prime/research_vault.py` (other branch) |
| Model scorecards | **in open PR #177** — not duplicated | `jarvis_prime/model_scorecard.py` (other branch) |
| Monitors + daily owner brief | **in open PR #177** — not duplicated | `jarvis_prime/monitors.py`, `owner_brief.py` (other branch) |
| Worker actuators (Claude/Codex/Aider/Goose/local) | **scaffolded (pre-existing)**; real git diffs via `collect_git_artifacts` | `hermes_cli/workers/` |
| Worktree/sandbox isolation | **scaffolded (pre-existing)** | `hermes_cli/workers/isolation.py` |
| Hardware probe + open-weight catalog | **shipped (tested)** | `hermes_cli/local_models/{hardware_probe,catalog}.py` (this branch) |
| Local model download layer (consent-gated) | **shipped (tested)** | `hermes_cli/local_models/bootstrap.py` + `server_adapters.py` (note: the `muse models bootstrap` CLI command is the free-first router in `jarvis_prime/model_bootstrap.py`) |
| Model scorecards (local selection by composite) | **shipped (tested)** | `hermes_cli/local_models/scorecards.py` (this branch; distinct from PR #177's worker scorecard) |
| Orchestrator → navigator wiring before dispatch | **shipped (tested)** | `orchestrator.navigate_job()` (this branch) |
| Repair loop (test→localize→patch→rerun→stop) | **shipped (tested)** | `hermes_cli/workers/repair_loop.py` (this branch) |
| Job replay (`muse orchestrate replay <job-id>`) | **shipped (tested)** | `hermes_cli/orchestrator_replay.py` (this branch) |

## What was deliberately NOT done (and why)

- **Phases 1, 2, 7, 8 and part of 6** (Memory Forest, TokenJuice, Research
  Vault, scorecards, monitors/brief) are already implemented in **open draft
  PR #177** (`claude/jarvis-hermes-enhancements-eWOBs`). The hard-truth rule
  *"do not duplicate features that already exist"* applies — rebuilding them on
  this branch would create conflicting parallel implementations. This branch
  delivers the **complementary, missing** pieces instead.
- No owner-gated action was executed. Owner gates and the exact authorization
  phrase are preserved and the new Goal Boundary layer *composes* with them.
- No model downloads, no network calls, no secrets touched. Navigation and
  goal-boundary are stdlib-only.

## PR validation report (Phase 9)

- **Open PRs found:** 1 — #177 (draft) "muse cognition plane".
- **Merged by me:** none. (Not my branch; merging it is owner-gated
  `main`-branch merge, and it is a draft.)
- **Skipped/closed PRs:** none ignored; only #177 is open.
- This branch opens its own draft PR; it does not merge anything.

## Closed-loop flow (now wired, end-to-end testable)

```
submit_job(prompt)                       # orchestrator records "submit"
  → navigate_job(job_id, repo_root)      # Navigator localizes → ledger "navigation_decision"
      → worker packet (candidate files + tests to run)
  → run_repair_loop(boundary, runner, patcher, localizer)
      # GoalBoundary-governed: test → localize → patch → rerun → STOP at limit
  → JobReplay.load(job_id).render()      # read-only audit of every decision
```

This is exercised by `tests/test_orchestrator_navigation.py` (submit → navigate
→ ledger → replay) and `tests/test_repair_loop.py`.

## Phase 6 — local model bootstrap (this branch)

- `config/model-catalog.yaml` gained an `open_weight_candidates:` section
  (Qwen / DeepSeek / Kimi / GLM coding+reasoning, plus local embeddings +
  reranker), each with **license**, runtime, min RAM/VRAM, context, lanes, and
  checksum/source `verify` guidance. The existing provider catalog is untouched.
- `muse models bootstrap --tier <t> [--accept-downloads]` plans against
  detected hardware and **never downloads without `--accept-downloads`**.
- Docs: `docs/ai-intelligence/oss-model-catalog.md` (extended, not replaced) +
  `model-routing-policy.md` (pre-existing).

## Still deferred (honest)

- Phases 1/2/7/8 remain in PR #177 (not duplicated here).
- A `muse jarvis navigate "<issue>"` interactive CLI lane is intentionally not
  wired into the 666 KB `cli.py` without integration tests; the orchestrator
  `navigate_job()` hook is the programmatic integration point and is tested.
- Repair-loop ledger persistence (`ledger_records()`) is provided but the
  orchestrator does not yet auto-run the repair loop on a real worker dispatch —
  that requires a live worker and is out of scope for a hermetic test run.

## One-command demo

```bash
muse orchestrate "make a tiny safe code change, test it, and open a draft PR"
```

The navigator localizes the change, the goal boundary bounds the loop, the
repair loop verifies via tests, and the decision trail is replayable with
`muse orchestrate replay <job-id>`.
