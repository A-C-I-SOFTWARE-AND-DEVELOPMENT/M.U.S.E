# CI Workflow Repair Report — PR #131

**Trunk PR:** [#131](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent/pull/131)
**Trunk head:** `claude/hopeful-bardeen-KBVqi` at `d0caf92`
**Repair branch:** `claude-review/launch-ci-workflow-repair`
**Author:** Claude Reviewer acting as CI repair engineer
**Date:** 2026-05-26

## Headline

**No workflow file changes were required.** All 16 `.github/workflows/*.yml`
parse, all `working-directory:` paths resolve, all `cache-dependency-path:`
lockfile paths exist, all gradlew paths exist. The four failing checks on
PR #131 (`Build debug APK`, `Lint`, `test`, `CodeQL`) are caused by real
code / dependency-config issues, not by stale workflow paths.

This branch therefore lands a single docs-only artifact: this report.
The actual fixes belong to lanes B, F, A, and G per
[`docs/launch/LAUNCH_BRANCH_MATRIX.md`](LAUNCH_BRANCH_MATRIX.md). Each
section below tells the receiving lane exactly what to change.

## Failing workflows on PR #131 (snapshot 2026-05-26 15:38 UTC)

| Workflow / job | Conclusion | Root cause | Owning lane |
|----------------|------------|------------|-------------|
| `android-build.yml` → `Build debug APK` | failure | gradle compile / kapt error post-3356f03 revert (logs auth-gated; manifest itself is intact) | B |
| `android-build.yml` → `Lint` | failure | gradle `lintDebug` failure (1 error + 1 warning per job summary) | B |
| `tests.yml` → `test` | failure | `ModuleNotFoundError: No module named 'psutil'` raised inside `tools/code_execution_tool.py:1455`; plus pre-existing 4 LSP-guard fails + 1 cron `test_script_timeout` | A (psutil) + G (LSP guard / cron) |
| CodeQL → `Analyze (python)` | success | — | — |
| CodeQL (overall) | failure | 2 new high-severity clear-text-logging alerts in `agent/agent_init.py:865` and `cron/scheduler.py:1078` | F |

## Inspection checklist (Step 1)

```
grep -rEn "cache-dependency-path|setup-node|package-lock\.json|working-directory|gradlew|android" .github/workflows/
```

Results (every reference + its target path on disk):

| Workflow | Reference | Target | Exists on disk? |
|----------|-----------|--------|-----------------|
| `android-build.yml:25,96` | `working-directory: apps/android` | `apps/android/` | ✅ |
| `android-build.yml:57,119` | `hashFiles('apps/android/**/*.gradle*', 'apps/android/gradle/libs.versions.toml', 'apps/android/gradle/wrapper/gradle-wrapper.properties')` | all 3 patterns match real files | ✅ |
| `android-build.yml:62,124` | `chmod +x ./gradlew` | `apps/android/gradlew` | ✅ |
| `android-build.yml:75` | `apps/android/app/build/outputs/apk/debug/*.apk` | produced at build time | (n/a) |
| `deploy-site.yml:40,44,69,73` | `cache-dependency-path: website/package-lock.json` + `working-directory: website` | `website/package-lock.json`, `website/` | ✅ |
| `skills-index.yml:63,67,81,85` | `cache-dependency-path: website/package-lock.json` + `working-directory: website` | same | ✅ |
| `docs-site-checks.yml:19,23,27,44,48` | `cache-dependency-path: website/package-lock.json` + `working-directory: website` | same | ✅ |
| `osv-scanner.yml:29,31,33,41–43,65,66` | `package-lock.json`, `ui-tui/package-lock.json`, `website/package-lock.json` | all 3 | ✅ |
| `nix-lockfile-fix.yml:7,9,30,112,113` | `ui-tui/package-lock.json`, `web/package-lock.json`, `ui-tui/package.json`, `web/package.json` | all 4 | ✅ |
| `supply-chain-audit.yml:50` | `:!uv.lock`, `:!*.lock`, `:!package-lock.json`, `:!yarn.lock` (exclusion glob) | n/a (pathspec) | ✅ |

## Lockfile inventory (Step 2)

```
find . -name "package-lock.json" -o -name "pnpm-lock.yaml" -o -name "yarn.lock"
```

Six `package-lock.json` files exist:

| Path | Referenced by workflow? |
|------|-------------------------|
| `./package-lock.json` | `osv-scanner.yml`, `supply-chain-audit.yml` (exclusion) |
| `./web/package-lock.json` | `nix-lockfile-fix.yml` |
| `./ui-tui/package-lock.json` | `osv-scanner.yml`, `nix-lockfile-fix.yml` |
| `./ui-tui/packages/hermes-ink/package-lock.json` | (none — leaf workspace) |
| `./website/package-lock.json` | `deploy-site.yml`, `skills-index.yml`, `docs-site-checks.yml`, `osv-scanner.yml` |
| `./scripts/whatsapp-bridge/package-lock.json` | (none — script-local) |

No `pnpm-lock.yaml`, no `yarn.lock`. The hypothetical wrong path the brief
warned about (`hermes-agent/package-lock.json`) **does not appear in any
workflow**.

## Workflow YAML validity (Step 3)

```
python3 -c "import yaml; [yaml.safe_load(open(f)) for f in __import__('glob').glob('.github/workflows/*.yml')]; print('All workflow YAML files parse')"
→ All workflow YAML files parse
```

Every workflow loads as valid YAML. No syntax errors.

## Local validation runs (Step 4)

| Command | Result | Notes |
|---------|--------|-------|
| `ruff check .` | ✅ All checks passed! | Matches the green `ruff enforcement (blocking)` job on PR #131. |
| `python3 scripts/check-windows-footguns.py --all` | ✅ No Windows footguns (556 files scanned) | Matches the green `Windows footguns (blocking)` job on PR #131. |
| `python3 -m pytest tests/test_jarvis_prime_*.py tests/test_orchestrator_*.py -q` | ⚠️ blocked — environment missing `yaml`, `psutil`, `pytest-xdist`, etc. The container is not provisioned with `.[all,dev]`. | CI installs `.[all,dev]` via uv and gets further; see "test failure" analysis below. |
| `cd apps/android && ./gradlew assembleDebug` | ⛔ blocked — `ANDROID_HOME` not set; no Android SDK provisioned in this container | The CI runner provisions the SDK via `android-actions/setup-android@v3`. Locally unreproducible. |
| `cd apps/android && ./gradlew testDebugUnitTest` | ⛔ same blocker | — |
| `cd apps/android && ./gradlew lintDebug` | ⛔ same blocker | — |

Honest acknowledgement per the brief: **Android SDK is not available in
this container.** I did not attempt to fake an assembly. Gradle outcomes
must be re-validated by lane B on a runner with `ANDROID_HOME` populated.

## Per-failure root cause

### Build debug APK (failure) — owned by lane B

- Logs are auth-gated on the public job URL, so the exact stack trace was
  not retrievable from this container.
- Context from `INTEGRATION_LOG.md` and the commit chain (`78e7330 →
  3356f03 → d0caf92`): the chat ViewModel test was added (78e7330) with
  `kotlinx-coroutines-test`, then the chat UI was reverted (3356f03), then
  the unit-tests CI job was reverted (d0caf92). Combined with the chat
  data layer surviving (`apps/android/app/src/main/java/com/aci/hermes/data/jarvis/JarvisChat*.kt`)
  the most likely failure is a Kotlin / kapt compile error against
  `AppContainer`, `HermesTask`, or `LogBuffer` surfaces — the same surfaces
  cited in the PR body as the reason the chat UI was reverted.
- **Not a workflow path issue.** No file path in `android-build.yml`
  needs to change. The job will pass once lane B closes the underlying
  gradle build.

### Lint (failure) — owned by lane B

- Same gradle context as above. `./gradlew lintDebug` cannot succeed if
  `assembleDebug` cannot link.
- The job's annotation summary reports "1 error and 1 warning". The
  error is not visible without auth; lane B must re-run with the job's
  artifact (`android-lint-report` is uploaded on `always()`).

### test (failure) — owned by lane A (config) + lane G (test correctness)

The CI job log surfaces three distinct issues:

1. `ModuleNotFoundError: No module named 'psutil'` raised inside
   `tools/code_execution_tool.py:1455` (`def _kill_process_group`). The
   import is intentionally lazy, but at runtime in tests the kill-tree
   helper is invoked and `psutil` is not installed. The cause is
   `pyproject.toml` line 62–63:

   ```
   # Cross-platform process / PID management.
   # Disabled for Android/Termux because psutil currently fails to build there.
   # Desktop/server installs should restore psutil through a non-Android extra.
   ```

   neither base deps nor `[all]` nor `[dev]` declare `psutil`. Tests
   running on Linux CI hit the bare lazy import and ModuleNotFound.

   **Recommended fix (lane A):** add `psutil` to `[dev]`. The comment in
   pyproject already directs this ("non-Android extra"); `[dev]` is the
   correct non-Android extra. `[dev]` is never installed by Termux
   profiles (`[termux]`, `[termux-all]`) so Android/Termux builds remain
   unaffected. If a stricter platform marker is wanted, use
   `psutil==<pin>; sys_platform != 'android'`. Note: `sys.platform` is
   `"linux"` on Termux, so a Termux-specific exclusion via marker is
   non-trivial and not strictly required because `[dev]` is opt-in.

2. `tests/agent/lsp/test_client_e2e.py` — 5 failures via the
   `live_system_guard` killing `os.kill()` outside the test subtree.
   `INTEGRATION_LOG.md` and the demo trace document **4** baseline LSP
   failures already on `main`; the 5th may be drift from a new change.

   **Recommended fix (lane G):** add the
   `@pytest.mark.live_system_guard_bypass` marker (mentioned in the
   webhook log analysis) to the 5 LSP tests, or alternatively mock
   `find_gateway_pids` + `os.kill` in those tests. Per the
   brief, do **not** mark them `@pytest.mark.skip`.

3. `tests/cron/test_cron_script.py::TestRunJobScript::test_script_timeout`
   — 1 failure. Likely a flake or environment-sensitive subprocess
   timeout. Owned by lane G to investigate.

   **None of these are workflow path issues.** `tests.yml` itself is
   well-formed: pytest options correct, env-var stubs in place,
   timeout-method=signal is appropriate.

### CodeQL (failure) — owned by lane F

- 2 new high-severity `clear-text-logging` alerts:
  1. `agent/agent_init.py:865` — "This expression logs sensitive data
     (secret) … as clear text."
  2. `cron/scheduler.py:1078` — "This expression logs sensitive data
     (secret) … as clear text."
- These are the same class of issue that #109 partially closed (22 alerts
  cleared). The 12 outstanding alerts called out in the PR #131 body are
  a different cluster; these 2 are new since the last CodeQL re-run.
- **Not a workflow issue.** The CodeQL workflow is unchanged and
  functioning. The fix is redaction at the two log-call sites.

## Files changed by this branch

| File | Change |
|------|--------|
| `docs/launch/CI_WORKFLOW_REPAIR_REPORT.md` | new (this file) |

**Zero changes** to `.github/workflows/*`, `pyproject.toml`, scripts,
or any source file. Lanes B / A / F / G must each push their own
follow-up to their lane branch per `LAUNCH_BRANCH_MATRIX.md`.

## Before / after paths

Not applicable — no path was wrong, so no before/after diff exists.

## Commands actually run

```
git fetch origin claude/hopeful-bardeen-KBVqi
git checkout claude/hopeful-bardeen-KBVqi
git checkout -b claude-review/launch-ci-workflow-repair

# Step 1 — inspect
grep -rEn "cache-dependency-path|setup-node|package-lock\.json|working-directory|gradlew|android" .github/workflows/

# Step 2 — lockfile inventory
find . -name "package-lock.json" -o -name "pnpm-lock.yaml" -o -name "yarn.lock"

# Step 3 — YAML validity
python3 -c "import yaml; [yaml.safe_load(open(f)) for f in __import__('glob').glob('.github/workflows/*.yml')]; print('All workflow YAML files parse')"

# Step 4 — local validation
ruff check .
python3 scripts/check-windows-footguns.py --all
python3 -c "import psutil"             # → ModuleNotFoundError (confirms config gap)
python3 -m pytest tests/test_jarvis_prime_*.py tests/test_orchestrator_*.py -q   # → blocked (env not provisioned)
./gradlew assembleDebug                # → blocked (no ANDROID_HOME)

# Cross-checks
grep -n "psutil" pyproject.toml
grep -rln "import psutil\|from psutil" tools/ agent/ hermes_cli/ gateway/ plugins/
find apps/android/app/src/main -path '*/ui/jarvis/*' -name "*.kt"
find apps/android/app/src/main -path "*/screens/chat*" -name "*.kt"
```

## Environment blockers

| Blocker | Impact | Workaround |
|---------|--------|------------|
| No `ANDROID_HOME`, no Android SDK | Cannot run any `./gradlew` task locally | Lane B re-validates on a CI runner |
| No `yaml`, `psutil`, `pytest-xdist`, `pytest-timeout` installed in container | Cannot run full pytest suite locally | Lane G re-validates after lane A adds psutil |
| GitHub Actions job logs auth-gated for unauthenticated WebFetch | Cannot read precise gradle error text from this container | Lane B downloads `android-build-reports` + `android-lint-report` artifacts on next run |
| The `gh` CLI is not available in this remote environment | Cannot inspect runs via `gh run view` | Used `mcp__github__pull_request_read` for what is exposed; raw logs still gated |

## Remaining risks

1. **Lane B may discover the gradle error is not where we suspect.** The
   3356f03 revert was surgical (chat UI + ui/jarvis composable only). If
   there are orphaned `import com.aci.hermes.ui.screens.chat.*` references
   left in `HermesNavGraph.kt`, `AppContainer.kt`, or `Screen.kt`, the
   compile will fail. Lane B's first action should be `grep -rn
   "ui.screens.chat\|ui.jarvis.JarvisPrimeIcon" apps/android/app/src/main/`
   and clean those up.
2. **Adding `psutil` to `[dev]` may transitively change `uv.lock`.** Lane
   A must run `uv lock` after the pyproject change and commit the updated
   `uv.lock`, or the `uv-lockfile-check.yml` job (currently green) will
   flip red.
3. **The 5th LSP failure may not be a marker miss.** If it's a real
   regression from one of #131's cherry-picks, lane G's fix is not just a
   marker but a code repair in `agent/lsp/client.py` (or wherever the new
   `os.kill` call lives).
4. **CodeQL may flag additional sites once `[dev]` adds psutil.** psutil
   itself is not a logging concern, but lane F should re-run the CodeQL
   analysis after lane A's commit to confirm no new alerts.
5. **This report assumes the failing-check snapshot taken at
   2026-05-26 15:38 UTC is current.** If a new commit on
   `claude/hopeful-bardeen-KBVqi` lands before lane B / A / F / G start,
   each lane should re-snapshot before acting.

## Should PR #131 be re-run?

**No.** A re-run will reproduce the same 4 failures. PR #131 must wait
for fixes from lanes B, A, F, and G to land on its branch (or rebase its
branch onto those fixes when they merge upstream).

## Verdict

CI workflow files are healthy. The four red checks on PR #131 are not
caused by stale workflow paths and cannot be cleared by editing
`.github/workflows/*`. This branch ships a report, not a code change,
because honestly documenting the boundary between "workflow repair"
(no-op) and "code repair" (other lanes) is more valuable than a sham fix.

Hand-off list — exact prompt that each lane should pick up next from
[`LAUNCH_STATUS.md`](LAUNCH_STATUS.md):

- **Lane A (Codex):** add `psutil` to `[dev]` in `pyproject.toml`, regen
  `uv.lock`, push to `launch/ci-codex-A`.
- **Lane B (Claude):** grep for orphaned chat/icon imports, repair, push
  to `launch/android-build-claude-B`.
- **Lane F (Codex):** redact secret-logging at `agent/agent_init.py:865`
  and `cron/scheduler.py:1078`, push to `launch/security-codex-F`.
- **Lane G (Codex):** apply `@pytest.mark.live_system_guard_bypass` to
  the 5 LSP tests; investigate the cron `test_script_timeout`; push to
  `launch/tests-codex-G`.
