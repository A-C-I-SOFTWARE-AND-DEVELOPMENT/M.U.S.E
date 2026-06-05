# Follow-up 4 — Unified release gate (`hermes doctor --release-gate`)

- **Status:** complete (implemented, validated, pushed)
- **Risk class:** additive (new CLI flag + new module + tests; no behavior
  change to existing commands)
- **Branch / base:** `claude/fu-4-release-gate` cut from `origin/main`
  (`b32db703`)
- **Contract:** Parallel Follow-up Execution Contract (BUILDER)

## Intent

Aggregate the existing 10/10 release-readiness checks (the 23 checks behind
`hermes doctor --10-10`) with the two *runtime* gates the smoke script
(`scripts/hermes-10-10-smoke.sh`) also runs — `ruff check .` and a fast,
launch-critical pytest slice — behind a single safe-to-ship verdict, so an
operator (or CI) gets one command and one exit code.

## Owned files (only these were created/modified)

- `hermes_cli/release_gate.py` — **new.** `run_release_gate(*, run_tests=True)`.
- `hermes_cli/main.py` — **modified, doctor block only.** `--release-gate` /
  `--no-tests` flags, `cmd_release_gate(args)`, one dispatch line in
  `cmd_doctor`.
- `tests/test_release_gate.py` — **new.** Mirrors
  `tests/test_release_readiness_doctor.py`.
- `docs/launch/followups/fu-4-release-gate.md` — **new.** This snapshot.

`hermes_cli/release_readiness_doctor.py` was **reused, not modified** (its
`run_10_10_doctor()` + `ReadinessReport`/`ReadinessCheck` dataclasses are
imported directly). No other file was touched. The `main.py` diff is three
textually-local hunks (`@@ 5812`, `@@ 5852`, `@@ 11523`) — no unrelated
subcommand changed.

## Plan / implementation

1. `run_release_gate(*, run_tests=True) -> ReadinessReport`:
   - calls `run_10_10_doctor()` to get the doctor's checks (23 today);
   - appends a **ruff** check (`uv run ruff check .`, falling back to bare
     `ruff` when `uv` is absent) as a `ReadinessCheck` (hard);
   - when `run_tests`, appends the **fast pytest slice** (the same six suites
     and `-o addopts=""` the smoke script runs) as a `ReadinessCheck` (hard);
   - recomputes `ok = not any(c.status == FAIL and c.hard for c in checks)`.
   - Reuses the doctor's dataclasses — **no parallel report type.**
   - Subprocesses run via a defensive wrapper: a missing executable (127), a
     timeout (124), or any `OSError` becomes a `FAIL` check. The function
     **never raises** (matches `run_10_10_doctor`).
2. `main.py` (doctor subparser only): added `--release-gate` (dest
   `release_gate`, `store_true`) and a companion `--no-tests` (dest
   `no_tests`) so the gate can run readiness+ruff without the slow slice;
   extended the `--json` help to mention `--release-gate`. Added
   `cmd_release_gate(args)` that mirrors `cmd_10_10_doctor` exactly (text or
   `--json` render, `raise SystemExit(0 if report.ok else 1)`). Added the
   dispatch line in `cmd_doctor` **before** the `args.ten_ten` check.
3. Tests mirror the readiness-doctor tests: composition (doctor checks + ruff,
   `run_tests=False`), test-slice inclusion when requested, `ok` aggregation
   over hard-only FAILs, soft-FAIL non-blocking, subprocess-failure→FAIL,
   `--json`/dict shape, and well-formedness. Subprocesses are monkeypatched in
   the shape/aggregation tests so the unit suite stays deterministic and fast
   (it never runs the real slow slice).

## Validation results

| Check | Command | Result |
|---|---|---|
| ruff | `uv run ruff check hermes_cli/release_gate.py hermes_cli/main.py tests/test_release_gate.py` | **All checks passed!** |
| ty | `uv run ty check hermes_cli/release_gate.py` | **All checks passed!** (no new diagnostics) |
| pytest | `uv run --extra all --extra dev pytest tests/test_release_gate.py tests/test_release_readiness_doctor.py -o addopts="" -q` | **20 passed** (12 new + 8 existing) in ~3.1s |
| smoke (no slice) | `doctor --release-gate --no-tests --json` | valid JSON, **24** checks (23 doctor + ruff), all pass, **exit 0** |
| smoke (full) | `doctor --release-gate --json` | valid JSON, **25** checks (23 doctor + ruff + fast slice = "passed (6 suites)"), `ok: true`, **exit 0** |

`doctor --release-gate` exit behavior: prints the report (text, or JSON with
`--json`) and `raise SystemExit(0 if report.ok else 1)` — exit 0 when no hard
gate fails, exit 1 on any hard FAIL (a doctor hard gate, ruff, or the fast
slice). Soft 10/10 punch-list warnings never change the exit code. On the
current tree the gate emits exit 0 with zero warnings (no soft FAILs observed).

## Residual / notes

- The ruff gate and the fast-test-slice gate are both **hard** (a dirty lint
  tree or a red fast slice is not safe to ship), unlike the doctor's soft
  loop-closure punch list which stays soft and advisory.
- The fast pytest slice list is duplicated from `scripts/hermes-10-10-smoke.sh`
  (kept in lockstep by a comment in `release_gate.py`). If the smoke script's
  slice changes, update `_FAST_TEST_SLICE` to match. A future cleanup could
  source the list from one place, but that would mean touching the smoke
  script, which is outside this follow-up's owned-files set.
- Generous subprocess timeouts (ruff 300s, pytest 900s) so a slow-but-healthy
  run is not misreported as a timeout FAIL.
- No PR opened / no merge (per contract). No model identifier in the commit.
