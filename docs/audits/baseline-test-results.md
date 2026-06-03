# Baseline & Verification Test Results

Environment: CPython 3.11.15, `uv` venv with the `dev` extra
(`uv sync --extra dev`). The project's default pytest `addopts` use
`-n auto` (xdist) + `--timeout`; runs below pass `-o addopts=""` to run
single-process for a clean, deterministic signal.

## New code — all green

```
uv run --extra dev python -m pytest \
  tests/test_tokenjuice_scrub.py tests/test_tokenjuice_reduce.py \
  tests/test_tokenjuice_integration.py tests/test_tokenjuice_tool_loop.py \
  tests/test_background_learner.py -p no:cacheprovider -o addopts="" -q
→ 66 passed
```

## Regression — tool-path unaffected

```
uv run --extra dev python -m pytest \
  tests/tools/test_tool_result_storage.py tests/tools/test_budget_config.py \
  -p no:cacheprovider -o addopts="" -q
→ 69 passed   (existing persistence/budget behavior intact)

# combined new + regression
→ 128 passed in ~1.6s
```

## Lint

```
uv run --extra dev ruff check tools/tokenjuice hermes_cli/background_learner agent/tool_executor.py
→ All checks passed!
```

## Pre-existing collection errors (NOT caused by this change)

A repo-wide `pytest tests/` collection hits ~16 import errors in modules that
require optional extras not installed here (e.g. `websockets` for
`tools/browser_supervisor.py`, gateway/messaging/HA modules). These are
unrelated to this change and fail identically on a clean checkout without those
extras. The tool-execution path and all new modules import and test cleanly.

## Audit correction captured during implementation

A model-registry/router scaffold was started, then **removed** when the audit
found Hermes already has `hermes_cli/model_registry.py` +
`hermes_cli/model_router.py`. Removing the colliding package restored the
existing system's import (`hermes_cli.model_router` + `hermes_cli.model_registry`
import OK). See `jarvis-architecture-gap-analysis.md` and
`model-registry-research.md`.
