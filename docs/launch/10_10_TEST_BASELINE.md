# Hermes 10/10 — Test & Verification Baseline

> **Owner:** Sprint 0 (Baseline, QA lane). **Created:** 2026-06-05.
> **Purpose:** The reliable command set every 10/10 phase runs before merge,
> documented **as the repo actually runs them** (correcting the plan's drafted
> commands where they differ). Companion to
> [`10_10_PROGRAM_STATUS.md`](10_10_PROGRAM_STATUS.md).

## Canonical commands

Run from the repo root. `uv` is the package manager; `uv.lock` is committed.

```bash
# 1. Dependency lock is consistent
uv lock --check

# 2. Lint + format
uv run ruff check .
uv run ruff format --check .

# 3. Types (config in [tool.ty] in pyproject.toml)
uv run ty check .

# 4. Tests — canonical runner (matches CI behavior; preferred)
scripts/run_tests.sh
```

### Test runner notes (repo truth)

`pyproject.toml` `[tool.pytest.ini_options]` already sets:

```ini
testpaths = ["tests"]
addopts   = "-m 'not integration' -n auto --timeout=30 --timeout-method=signal"
markers   = [
  "integration: marks tests requiring external services (API keys, Modal, etc.)",
  "real_concurrent_gate: opt out of the autouse concurrent-instance stub",
  "ssh: marks tests requiring a reachable SSH server",
]
```

So the default `uv run pytest` already excludes `integration`, runs in parallel
(`-n auto`), and enforces a 30s per-test timeout. **Prefer
`scripts/run_tests.sh`** — it pins the same behavior as CI and works around
xdist race conditions. The plan's drafted command
(`pytest -m "not integration" --timeout=30 --timeout-method=signal`) matches the
active config.

> Note: a comment block in `pyproject.toml` describes a "60s thread method" cap
> as historical context; the **active** `addopts` is `--timeout=30
> --timeout-method=signal`. Treat the `addopts` line as authoritative.

## Tiered subsets (fast local loops)

When iterating on one surface, run only its tests:

```bash
# Decision/JARVIS-prime surface (Sprint 2 work)
uv run pytest tests/ -k "approval or decision or judge or policy" -m "not integration"

# Workers + orchestration (Sprints 3,4,13)
uv run pytest tests/test_worker_*.py tests/test_orchestrator*.py tests/test_scoring.py tests/test_merge_engine.py -m "not integration"

# Gateway / cockpit API (Sprints 6,8,9)
uv run pytest tests/gateway -m "not integration"

# Publisher / validation (Sprints 4,5)
uv run pytest tests/test_validation.py tests/test_integration_orchestrator_pipeline.py -m "not integration"
```

Android (separate toolchain, from `apps/android/`):

```bash
./gradlew :app:testDebugUnitTest      # 123 JVM/Robolectric unit tests
```

## Test suite shape

- ~1,350 Python test files under `tests/`, largest areas: `gateway/` (~280),
  `hermes_cli/` (~235), `tools/` (~219), `agent/` (~121), `run_agent/` (~90).
- Fixtures are **pytest-native** in `tests/conftest.py` (~986 lines) and inline —
  there is no `tests/fixtures/` tree. New fixtures for 10/10 work go in
  `conftest.py` scopes or alongside the test module, mirroring the code layout.
- `tests/conftest.py` enforces credential isolation (unsets provider env vars),
  an isolated `HERMES_HOME` per test, and a deterministic runtime
  (`TZ=UTC`, `PYTHONHASHSEED=0`). **Do not weaken these** (protected — see
  [`PROTECTED_PATHS_10_10.md`](PROTECTED_PATHS_10_10.md) §8).

## Known flake / hazard

- **Full-suite ~96% hang:** on very large runs the suite could deadlock at
  session teardown from leaked threads / `atexit` handlers accumulating across
  thousands of tests. Mitigated by `pytest-timeout`. If a run appears to hang
  near the end, it is this teardown issue, not your change — re-run the affected
  subset with the tiered commands above to confirm.

## CI gates that must stay green

These workflows under `.github/workflows/` gate `main`:

| Workflow | Enforces |
|---|---|
| `tests.yml` | `uv sync` + pytest fast suite (`-m 'not integration'`, xdist) |
| `lint.yml` | `ruff check` + `ruff format --check` |
| `orchestration-tests.yml` | `py_compile` + `bash -n` + worker/orchestrator tests on `hermes_cli/**` |
| `uv-lockfile-check.yml` | `uv.lock` consistency |
| `osv-scanner.yml`, `supply-chain-audit.yml` | dependency / supply-chain audit |
| `android-build.yml` | Gradle build of the cockpit app |
| `launch-gate.yml` | launch-readiness checks |

## Per-phase verification expectation

Every 10/10 PR must, before requesting merge:

1. Run commands 1–4 above (or the relevant tiered subset + the full fast suite).
2. Add tests for new behavior next to the code they cover (mirror `tests/` layout).
3. For protected-path changes, attach a redaction/verdict trace or test as evidence.
4. Confirm `main` stays shippable (no skipped/xfail'd gate to make it pass).
