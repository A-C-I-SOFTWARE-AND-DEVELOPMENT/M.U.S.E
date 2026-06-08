# WC-2: Release gate hard tooling precondition (strict mode opt-in)

- **Status:** building → in-review (PR opens on push)
- **Risk class:** behavior-change (owner-gated) — the verdict inverts on a
  release host when tools are absent. Default behavior on dev hosts is
  byte-identical (FU-10 anti-false-RED preserved).
- **Branch:** `claude/vigilant-knuth-519h3u` · **Base:** `main` @ `860a88b8e`
- **PR:** TBD (draft on push)
- **Owner-gate required to merge?** **yes** — owner authorized via
  `Yes, with authorization.` on 2026-06-08.

## Intent (one paragraph)

The audit found the single highest-priority residual risk: the release
gate at `hermes_cli/release_gate.py:220-272` *fails OPEN* when both
`uv run` and `sys.executable` lack `ruff`/`pytest`. The FU-10 fix
(soft WARN, `hard=False`) was correct on dev hosts but inverts on a
stripped release host or CI runner — the operator-facing
`muse doctor --release-gate` then reports **GREEN SHIP with zero tests
executed**. WC-2 adds an opt-in strict mode: when
`HERMES_RELEASE_GATE_STRICT=1` (or `strict_tooling=True` is passed),
missing tools become a *hard FAIL* with a clear "tooling absent on
release host" message that names the env var so the operator knows
exactly which flag inverted the verdict. Default stays soft for dev
convenience — strict is strictly opt-in.

## Owned files (the ONLY files this task may write)

- `hermes_cli/release_gate.py` — env-var reader + `_tool_absent_check`
  helper + `strict_tooling` keyword on `_ruff_check`,
  `_fast_test_slice_check`, `run_release_gate`.
- `tests/test_release_gate.py` — 8 new WC-2 tests + lambda stub
  signature updates to accept `**_kw` (no-op for existing tests but
  required because the production functions gained a kwarg).

## Plan (bounded steps)

1. **Env-var reader**: `_strict_tooling_enabled()` reads
   `HERMES_RELEASE_GATE_STRICT` at every call (not cached) so tests +
   CI can flip it via monkeypatch without restarting the process.
   Canonical truthy values: `1` / `true` / `yes` / `on`. [done]
2. **Strict-aware tool-absent verdict**: extract `_tool_absent_check`
   so both `_ruff_check` and `_fast_test_slice_check` route through
   the same dev-WARN-vs-strict-FAIL decision; strict message names
   `HERMES_RELEASE_GATE_STRICT` so the operator can act on it. [done]
3. **Thread `strict_tooling` through `run_release_gate`**: default
   `None` consults the env var; `True`/`False` force the decision (the
   `False` escape hatch lets a dev manually override even with the
   env var set, e.g. for an offline doctor run). [done]
4. **Tests**: 8 cases — ruff missing under strict / under dev (×2),
   pytest slice missing under strict / under dev (×2), env-var-driven
   end-to-end (×2), explicit-override-beats-env (×1), truthy /
   falsey variants of the env var (×2). Plus six `lambda` stub
   signature updates: `lambda: ReadinessCheck(...)` →
   `lambda **_kw: ReadinessCheck(...)` so the existing stubs accept
   the new kwarg without spurious `TypeError`. [done]

## Validation

- `uv run ruff check hermes_cli/release_gate.py tests/test_release_gate.py` → **clean**
- `uv run ty check hermes_cli/release_gate.py` → **all checks passed**
- `uv run python -m pytest tests/test_release_gate.py -q` → **30 passed**
  (22 existing FU-10 / FU-11 behavior preserved + 8 new WC-2).

## Residual / follow-on

- The `launch-gate.yml` aggregator workflow does not yet set
  `HERMES_RELEASE_GATE_STRICT=1` in its env. Threading that env var
  into the CI matrix is a small, additive follow-on packet — kept
  separate so this WC-2 packet stays code-only and the CI-config edit
  has its own reviewable diff. WC-2 ships the *capability*; the workflow
  edit *adopts* it.
- The `release_readiness_doctor._check_budget_enforced` false-PASS bug
  was flagged in the prior audit and is **already fixed**
  (`release_readiness_doctor.py:403-410` now requires both paths to
  actually meter via `evaluate_budget`). No additional work needed here.
