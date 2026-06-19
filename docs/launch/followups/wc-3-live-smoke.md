# WC-3: Live core-loop smoke test + opt-in CI marker (depth pick)

- **Status:** building → in-review (PR opens on push)
- **Risk class:** additive (test-only) — no production code path is
  modified; the existing CI e2e lane is untouched in behavior, only
  documented.
- **Branch:** `claude/vigilant-knuth-519h3u` · **Base:** `main` @ `860a88b8e`
- **PR:** TBD (draft on push)
- **Owner-gate required to merge?** **yes** — owner authorized via
  `Yes, with authorization.` on 2026-06-08. (The packet itself is
  additive, but it lands a new CI marker and we keep the gate consistent
  with WC-1 / WC-2 in the same merge train.)

## Intent (one paragraph)

The contrarian-reviewer found that no test in this repo calls a real
model and asserts on its generated output: `test_core_loop_depth_e2e.py`
is "offline by construction" (`:14-15`); `depth_scorecard.py` grades
hand-written correct-by-construction answers against themselves
(`test_depth_scorecard.py:36-41` asserts `==1.0`, a tautology). On the
"10/10 a proven tool not a demo" claim, "does the configured model
actually answer" was structurally untested. WC-3 lands the smallest
honest signal: a single live smoke test that, on a box with the
`claude` or `codex` worker CLI installed, runs one real worker turn and
asserts (a) zero exit code, (b) non-empty stdout, (c) no broken-loop
markers (`api key`, `unauthenticated`, …). Gated behind
`@pytest.mark.live` and a `--run-live` / `HERMES_E2E_LIVE=1` opt-in
hook in `tests/conftest.py` so the default CI lane is unchanged.

## Owned files (the ONLY files this task may write)

- `tests/e2e/test_core_loop_live_smoke.py` — new file, ~180 lines.
- `tests/conftest.py` — `pytest_addoption("--run-live")` +
  `pytest_configure` marker registration + `pytest_collection_modifyitems`
  skip hook.
- `.github/workflows/tests.yml` — comment-only annotation on the
  existing `e2e` job that documents the live marker and confirms it is
  not consumed on the default lane.

## Plan (bounded steps)

1. **Opt-in marker**: register `@pytest.mark.live` in `tests/conftest.py`
   alongside the existing `live_system_guard_bypass` registration. Add
   a `pytest_addoption("--run-live")` and a
   `pytest_collection_modifyitems` hook that skips every `live`-marked
   test unless `--run-live` is passed or `HERMES_E2E_LIVE=1` is set.
   [done]
2. **Smoke test**: `tests/e2e/test_core_loop_live_smoke.py` resolves
   the first available worker from `("claude", "codex")` via
   `shutil.which`, calls it once with a one-token prompt
   (`claude -p PROMPT` / `codex exec PROMPT`), and asserts the three
   honest signals above. Skips with a clear message when no worker is
   on PATH. Timeout 120s to absorb a cold model load without flaking.
   Broken-loop markers fire FIRST so a misconfigured local env produces
   a useful diagnostic, not a generic exit-code failure. [done]
3. **CI annotation**: add a comment block to `.github/workflows/tests.yml`
   on the existing `e2e` job explaining the live marker semantics. The
   existing job already runs `tests/e2e/` and will auto-skip live
   tests via the conftest hook — no new lane needed. [done]

## Validation

- `uv run ruff check tests/e2e/test_core_loop_live_smoke.py tests/conftest.py` →
  **clean**
- `uv run python -m pytest tests/e2e/test_core_loop_live_smoke.py -q` →
  **1 skipped** (default lane behavior — the live test does not run
  unless explicitly opted in).
- `uv run python -m pytest tests/e2e/test_core_loop_depth_e2e.py -q` →
  **passes** (the existing offline E2E is unaffected; this confirms
  the marker hook does not over-skip).

## Residual / follow-on

- This is the *seed*, not the full depth program. Per the deep-research
  finding on free/local LLM stacks, the actual proof-bar replacement
  for `depth_scorecard.py` should be **BFCL v3 multi-turn on Qwen3 32B
  Q4_K_M + llama.cpp** (target ≥ 65% — published reference is 75.7% in
  BF16, so consumer-hardware Q4 of 65% is honest), or **GLM-4.5 via
  OpenRouter** for the hosted-free path. WC-3 lands the marker
  infrastructure; the BFCL harness adoption is a separate packet
  ("Wave D — Real depth benchmark") and needs an owner go/no-go on
  budget for a self-hosted vLLM lane.
- The live smoke deliberately does not exercise muse's own gateway
  (Telegram / Discord / cockpit). Those paths have their own integration
  suites; WC-3 targets the single claim the offline E2E cannot make
  — "the configured model produces output". Anything broader would
  bloat the marker into a benchmark, which it must not be.
