# FU-10 — Harden the release gate against a pytest-less venv (no false-RED)

- **Task ID:** FU-10
- **Branch:** `claude/fu-10-release-gate-venv`
- **Base commit:** `e1ac6eed95406e90ce8d656a45b767ab865e8a0b` (origin/main)
- **Status:** in-review (draft PR)
- **Owner gate:** behavior change to a default runtime path (the release
  gate's interpreter selection) — **owner-gated**, do not auto-merge.

## Intent

The unified release gate (`hermes doctor --release-gate`) prefers `uv run`
for CI parity. On a host where `uv` is on PATH **but its project venv lacks
pytest** (an un-synced checkout), `uv run python -m pytest` exits non-zero
with `No module named pytest`. The old gate read that as a **hard FAIL** of
the fast test slice — a *false-RED* that blocked the gate's own GREEN verdict
even when the suite is green under the system interpreter.

This task makes the gate distinguish **"tooling absent in the chosen env"**
(honest, non-blocking `WARN`) from **"tests actually failed / lint dirty"**
(hard `FAIL`), and makes the interpreter choice robust by *probing* before
committing.

> Note: the task brief said this checkout's `uv` has pytest 9.0.3 and would
> not repro. In fact **this worktree's `uv` venv lacks pytest**
> (`uv run python -c "import pytest"` exits 1) while system pytest is 9.0.3 —
> so the bug reproduces here, and the fix is verified live: the selector now
> falls back to `/usr/local/bin/python -m pytest` instead of false-RED-ing.

## What changed

`hermes_cli/release_gate.py` (additive robustness; default healthy path
unchanged — when `uv`'s venv *does* have the tool, the `uv run` path is kept):

- New `_probe_ok(argv)` — runs a capability probe via the existing
  never-raising `_run_subprocess`; non-zero / missing binary / timeout ⇒
  `False`.
- New `_uv_can_import(module)` — `True` iff `uv run python -c "import
  <module>"` exits 0. Guards the `uv run` fast-path.
- `_ruff_argv()` → returns `(argv, available)`. Probes `uv run ruff
  --version`, then a bare `ruff --version`; first responder wins. `available`
  is `False` only when **no** reachable ruff exists.
- `_pytest_argv()` → returns `(argv, available)`. Prefers `uv run python …`
  **only if** `_uv_can_import("pytest")`; otherwise falls back to
  `sys.executable -m pytest` (if *it* imports pytest). `available` is `False`
  only when **no** reachable interpreter has pytest.
- `_ruff_check()` / `_fast_test_slice_check()` — when `available` is `False`,
  emit a clearly-labeled soft `WARN` (`hard=False`, "tooling absent"), never a
  hard FAIL. A genuine non-zero with real lint/test output stays a hard
  `FAIL`. Defensive layer: a run that still prints `No module named pytest`
  (or a ruff "executable not found") is downgraded FAIL→WARN so a missing
  runner can never masquerade as a red suite.
- `run_release_gate` is untouched in shape/contract: still never-raises, still
  returns `ReadinessReport`, `ok` still flips only on a **hard** FAIL — so a
  tool-absent WARN keeps an otherwise-healthy tree shippable.

`tests/test_release_gate.py` (additive + 2 corrected):

- Corrected `test_ruff_check_missing_tool_is_*` and the slice missing-tool
  case: a missing tool is now a soft `WARN`, not a hard FAIL (this is the
  intended FU-10 contract change). Kept/added explicit "genuine failure is
  still a hard FAIL" tests for both ruff and pytest.
- New FU-10 section simulating "uv present but its python lacks pytest":
  selector falls back to `sys.executable`; healthy path still prefers `uv
  run`; no-interpreter-has-pytest ⇒ `available False`; end-to-end slice runs
  green under the fallback (PASS, not RED); defensive `No module named pytest`
  downgrade; tool-absent WARN keeps the gate shippable; ruff bare fallback;
  probe never raises on bogus argv.

## Owned (writable) files

- `hermes_cli/release_gate.py`
- `tests/test_release_gate.py`
- `docs/launch/followups/fu-10-release-gate-venv.md` (this snapshot)

No other files touched. Did **not** edit
`docs/launch/10_10_followups_ledger.md`.

## Validation

Commands run from repo root:

- `uv run ruff check hermes_cli/release_gate.py tests/test_release_gate.py`
  → `All checks passed!` (exit 0)
- `uv run ty check hermes_cli/release_gate.py tests/test_release_gate.py`
  → `All checks passed!` (exit 0; no new diagnostics, not even the exempt
  pytest false-positive)
- `python -m pytest tests/test_release_gate.py -o addopts="" -q`
  → `21 passed`

Live selector check on this (pytest-less-uv) host:

- `_uv_can_import('pytest')` → `False`
- pytest selector → `['/usr/local/bin/python', '-m', 'pytest', …]`, available
  `True` (correct fallback)
- ruff selector → `['uv', 'run', 'ruff', …]`, available `True` (uv venv has
  ruff)

## Constraints honored

- Additive robustness; never-raises preserved; no network (probes are local
  `import`/`--version`); stdlib-light (adds only `import sys`).
- Default healthy path keeps current behavior: prefer `uv` when it works.
- `ReadinessReport` / `ReadinessCheck` shapes and `run_release_gate` contract
  unchanged.

## Residual risks / notes

- The defensive text markers (`no module named pytest`, ruff "executable not
  found" / "command not found") are matched case-insensitively against the
  one-line tail `_run_subprocess` keeps. The primary guard is the pre-run
  probe; the text match is a belt-and-suspenders fallback only.
- A tool-absent `WARN` is intentionally non-blocking. On CI, where the venv is
  synced, both probes pass and behavior is identical to before — CI still
  enforces lint + slice as hard gates.
