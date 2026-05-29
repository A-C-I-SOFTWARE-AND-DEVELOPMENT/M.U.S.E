# JARVIS Prime — Navigation Layer & Goal Boundary (build report)

Branch: `claude/jarvis-prime-architecture-RmmXr`
Date: 2026-05-29

This report covers the slice of the "JARVIS Prime apex" mission delivered on
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
| Worker actuators (Claude/Codex/Aider/Goose/local) | **scaffolded (pre-existing)** | `hermes_cli/workers/` |
| Worktree/sandbox isolation | **scaffolded (pre-existing)** | `hermes_cli/workers/isolation.py` |
| Local model bootstrap (`hermes models bootstrap`) | **missing** | (Phase 6 — `hermes_cli/models/` not created) |
| Orchestrator → navigator wiring before dispatch | **missing (documented)** | see "Next steps" |
| Repair loop / replay command | **missing** | (Phase 5) |

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

- **Open PRs found:** 1 — #177 (draft) "JARVIS Prime cognition plane".
- **Merged by me:** none. (Not my branch; merging it is owner-gated
  `main`-branch merge, and it is a draft.)
- **Skipped/closed PRs:** none ignored; only #177 is open.
- This branch opens its own draft PR; it does not merge anything.

## Next steps (not claimed as done)

1. Wire `Navigator.navigate()` into `hermes_cli/orchestrator.py` immediately
   before worker dispatch, appending `to_ledger_record()` to the job ledger.
2. Add a CLI lane (`hermes jarvis navigate "<issue>"`) — kept out of this
   branch to avoid touching the 666 KB `cli.py` without integration tests.
3. Phase 5 repair loop + `hermes orchestrate replay <job-id>`.
4. Phase 6 `hermes_cli/models/` bootstrap + `config/model-catalog.yaml`
   expansion (a root `hermes_model_catalog.py` and `config/model-catalog.yaml`
   already exist; extend, don't replace).
