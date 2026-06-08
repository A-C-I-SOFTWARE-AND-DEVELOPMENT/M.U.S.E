# FU-16 — Free/local benchmark scorecard producer

## Intent

Add a deterministic, fully-offline **benchmark scorecard producer** — a free
(no paid model, no network) reproducible proof-bar artifact for the 10/10
program. It does not invent a new scoring system; it *reuses* the repo's
existing scorecard/benchmark machinery and emits a `ModelScorecard`-compatible
artifact with a per-`TaskClass` pass-rate and an overall verifiable score.

## Reuse (read, not modified)

- `hermes_cli/jarvis_prime/research_fabric/benchmarks/__init__.py`
  (`BenchmarkTaskSpec`, `run_suite`, `SuiteResult`) — the offline benchmark
  harness that grades verifiable algorithm tasks by executing an embedded
  candidate against known cases in the research-fabric sandbox
  (`run_python_script`: `python -I -S` subprocess, scrubbed env, dead-proxy
  network). No model call.
- `hermes_cli/jarvis_prime/model_scorecard.py` (`ModelScorecard`) — the
  structured scorecard shape; each graded task becomes one card
  (`tests_passed`/`tests_failed`), so each card round-trips through
  `ModelScorecard.from_dict`.
- `hermes_cli/jarvis_prime/task_router.py` (`TaskClass`) — supplies the lane
  vocabulary the per-class pass-rate is bucketed by.

## Owned (writable) files — NEW only

- `hermes_cli/jarvis_prime/depth_scorecard.py` (new)
- `tests/test_depth_scorecard.py` (new)
- `docs/launch/followups/fu-16-benchmark-scorecard.md` (this snapshot)

No existing file is modified. The CLI was intentionally **not** touched:
`hermes_cli/jarvis_prime/__main__.py` is a 3.3k-line file and not in the owned
set, and the task says module-only unless a CLI hook is trivial/additive. The
producer is exposed as a module API (`produce_scorecard`, `render_scorecard`)
instead.

## What it does

`produce_scorecard(tasks=None) -> DepthScorecard`:

- Grades a small built-in suite (`BUILTIN_TASKS`) of pure string/number
  transforms whose correct output is known exactly (reverse, sum, upper,
  count-vowels, slugify), each carrying a known-correct candidate and tagged
  with a real `TaskClass` value.
- Runs them through `run_suite` and maps each outcome onto a `ModelScorecard`.
- Aggregates per-`TaskClass` pass-rate + an overall verifiable score.
- Is **100% offline + deterministic**: the artifact carries only
  correctness-derived fields (no latency, no timestamps — `created_at` is pinned
  to the epoch); `per_class` is sorted; `to_json()` uses `sort_keys=True`.
- **Never raises**: import failure / empty suite / harness exception all degrade
  to an honest all-zero scorecard with the reason in `notes`.

Sample output (this env): `5/5 verifiable tasks passed (score=1.00)` —
`coding_build 3/3`, `summarization 2/2`.

## Validation

Run from the worktree root (`uv run` here ships pytest 9.0.3).

- `uv run ruff check hermes_cli/jarvis_prime/depth_scorecard.py tests/test_depth_scorecard.py`
  → **All checks passed!**
- `uv run ty check hermes_cli/jarvis_prime/depth_scorecard.py tests/test_depth_scorecard.py`
  → 1 diagnostic: `unresolved-import: pytest` in the test file. This is a
  **pre-existing, environment-wide** condition (the freshly-built ty venv lacks
  the dev `pytest` dep); every existing test that does `import pytest` (e.g.
  `tests/test_parallel_orchestration.py`) emits the identical diagnostic.
  `depth_scorecard.py` itself is clean. **No new diagnostics vs base.**
- `python -m pytest tests/test_depth_scorecard.py tests/test_jarvis_prime_model_scorecard.py -o addopts="" -q`
  → **25 passed**.

## Tests pin

- Schema shape (`to_dict()` keys, `per_class` entry keys, schema_version).
- Determinism: two runs → identical `to_dict()` and `to_json()`.
- Reuse: built-in candidates are correct-by-construction → perfect bar; each
  card round-trips through `ModelScorecard.from_dict`; lanes are real
  `TaskClass` values.
- Robustness: empty suite + simulated harness failure degrade without raising; a
  wrong candidate is graded as a failing test (not an error).
- No network: `socket.socket` / `socket.create_connection` patched to raise
  during the call; grading still succeeds.

## Branch / base

- Branch: `claude/fu-16-benchmark-scorecard`
- Base: `main` @ `b74f9889`

## Residual risks

- The grader shells out to a subprocess per task (the research-fabric sandbox),
  so the *call* is not pure-Python; determinism is preserved because only the
  binary correctness signal is recorded, never wall-clock latency. The
  no-network test patches the parent process's `socket`; the subprocess
  additionally runs under the sandbox's dead-proxy scrubbed env.
- Strictly additive, opt-in module — no default runtime path changes — so this
  is auto-mergeable on green CI under the follow-up contract.
