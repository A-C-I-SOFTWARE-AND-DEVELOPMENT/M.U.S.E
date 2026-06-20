# Launch Branch Matrix — MUSE + Hermes runtime

> ⚠️ **SUPERSEDED (2026-06-01).** The nine-lane integration plan below was
> executed; PR #131's lanes have landed on `main` (211 commits past the
> `bc97e43` base). This matrix is historical. For current readiness see
> [`LAUNCH_STATUS_CURRENT.md`](./LAUNCH_STATUS_CURRENT.md).
>
> **Supersession addendum (2026-06-10, SYNAPSE P1-05a):** every instruction
> below — including "must not be merged" (Purpose section) — is historical.
> The chain's closure record is two-way linked: current status lives in
> [`LAUNCH_STATUS_CURRENT.md`](./LAUNCH_STATUS_CURRENT.md) (Update
> 2026-06-10), and the frozen artifact→PR evidence map lives in the
> **RESOLUTION ADDENDUM — 2026-06-10** at the bottom of
> [`../aci/reports/R00_REMAINING_SPRINT_DECISION_MATRIX.md`](../aci/reports/R00_REMAINING_SPRINT_DECISION_MATRIX.md);
> both documents link back here. Nothing below this banner was edited.
>
> **Cross-link addendum (2026-06-20, P1-04):** This document and
> [`LAUNCH_STATUS_CURRENT.md`](./LAUNCH_STATUS_CURRENT.md) now cross-reference
> each other bidirectionally. The R00 decision matrix's HOLD instructions are
> superseded by the resolution addendum. The launch-chain closure is recorded
> in both places. No HOLD instructions below remain actionable.

**Trunk PR:** [#131](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent/pull/131)
**Head branch:** `claude/hopeful-bardeen-KBVqi`
**Base:** `origin/main` at `bc97e43`
**Plan branch (this doc):** `launch/commander-plan`
**Date:** 2026-05-26

## Purpose

PR #131 is the integration trunk. It must not be merged to `main` and must
not be deployed. This matrix subdivides remaining launch work into nine
lanes so Claude and Codex can work in granular parallel without stepping
on each other's files.

Every lane targets PR #131 as the integration tip. Lane H rebases all
upstream lanes onto PR #131 and lane I reviews the result. No lane
merges to `main`. No lane changes secrets, bypasses owner gates, or
modifies the literal authorization phrase.

## Failure landscape (from PR #131 latest check run, 2026-05-26)

| Check | Conclusion | Owning lane |
|-------|------------|-------------|
| Build debug APK (`android-build.yml`) | failure | B |
| test (pytest) | failure | G (root cause), A (workflow if config) |
| Lint (`lint.yml`) | failure | A (ty / ruff config), F (if redaction-flagged) |
| CodeQL | failure | F |
| Orchestration unit tests | success | — |
| ruff enforcement (blocking) | success | — |
| Windows footguns (blocking) | success | — |
| e2e | success | — |
| Analyze (actions / python / ruby / javascript-typescript) | success | — |

Passing checks must remain green; lane validation includes "no regression of
green checks."

## Global protected paths (forbidden to all lanes unless explicitly allowed)

- `hermes_cli/jarvis_prime/owner_auth.py` — `AUTHORIZATION_PHRASE`, owner-gate logic
- `hermes_cli/jarvis_prime/gates.py` — gate decision functions
- `apps/android/app/src/main/AndroidManifest.xml` — permissions
- `apps/android/app/src/main/res/xml/backup_rules.xml` — backup scope
- `apps/android/app/src/main/res/xml/data_extraction_rules.xml` — data extraction scope
- `agents/**` — agent definitions
- `recovered-agent-sources/**` — recovered source tree
- `.github/workflows/upload_to_pypi.yml` — release flow
- `.github/workflows/docker-publish.yml` — release flow
- `.github/workflows/deploy-site.yml` — deploy flow
- Anything under `.claude/agents/**`

## Global forbidden edits (apply to every lane)

- Changing `AUTHORIZATION_PHRASE` value or removing it
- Removing or weakening any entry in `OWNER_GATED_ACTIONS` (additive extensions only, with owner gate)
- Adding any new Android permission to `AndroidManifest.xml`
- Removing or weakening any redactor (`SecretRedactor`, `MemoryRedactor`, `PrivacyRedactor`, Python `agent/redact.py`)
- Removing emergency stop controller, repo, audit event, or shell button
- Force-pushing over a lane branch that is not your own
- Merging any lane to `main`
- Deploying to any environment
- Closing PR #131 or any other open PR
- Changing secrets, OAuth, DNS, credentials
- Issuing the owner authorization phrase
- Bypassing CodeQL config

---

## Lane A — CI / workflow repair (Codex-owned)

| Field | Value |
|-------|-------|
| Branch name | `launch/ci-codex-A` |
| Base | PR #131 tip (`claude/hopeful-bardeen-KBVqi`) |
| Owner | Codex |
| Parallel-safe with | F, G (different file scopes) |
| Merge order | 1st — before B, C, D, E |

### Allowed files

- `.github/workflows/android-build.yml`
- `.github/workflows/lint.yml`
- `.github/workflows/tests.yml`
- `.github/workflows/orchestration-tests.yml`
- `.github/workflows/uv-lockfile-check.yml`
- `.github/workflows/history-check.yml`
- `.github/workflows/contributor-check.yml`
- `.github/workflows/skills-index.yml`
- `.github/workflows/osv-scanner.yml`
- `.github/workflows/supply-chain-audit.yml`
- `.github/workflows/nix.yml`
- `.github/workflows/nix-lockfile-fix.yml`
- `.github/workflows/docs-site-checks.yml`
- `pyproject.toml` (ruff/ty/pytest config sections only)
- `.ruff.toml`
- `pytest.ini` if introduced
- `scripts/check-windows-footguns.py`
- `apps/android/gradle/libs.versions.toml` (only if a CI step pins a version)

### Protected files

- `.github/workflows/upload_to_pypi.yml`
- `.github/workflows/docker-publish.yml`
- `.github/workflows/deploy-site.yml`
- Any production source file under `hermes_cli/`, `agent/`, `apps/android/app/src/main/`
- `hermes_cli/jarvis_prime/owner_auth.py` and `gates.py`

### Forbidden edits

- Removing CodeQL workflow or its config
- Disabling `Windows footguns (blocking)` or `ruff enforcement (blocking)`
- Adding `pull_request_target` or `workflow_dispatch` to release workflows
- Adding secrets to any workflow
- Skipping owner-gate guard scripts

### Validation commands

```bash
ruff check .
python3 scripts/check-windows-footguns.py --all
python3 -m pytest tests/ -q -n auto --timeout=30 --timeout-method=signal
gh run list --limit 5 --branch launch/ci-codex-A
```

CI gate: every failing check on PR #131 baseline that this lane targets
must flip to success, and every passing check must remain success.

### Rollback plan

- `git revert -m 1 <merge-sha>` on PR #131 branch
- PR #131 returns to baseline CI state (4 failures, original passes)

---

## Lane B — Android build stabilization (Claude-owned)

| Field | Value |
|-------|-------|
| Branch name | `launch/android-build-claude-B` |
| Base | PR #131 tip after lane A merges |
| Owner | Claude |
| Parallel-safe with | F, G (different file scopes) |
| Merge order | 2nd — after A, before C, D, E |

### Allowed files

- `apps/android/app/build.gradle.kts`
- `apps/android/build.gradle.kts`
- `apps/android/settings.gradle.kts`
- `apps/android/gradle/libs.versions.toml`
- `apps/android/gradle.properties`
- `apps/android/app/src/main/java/com/aci/hermes/di/AppContainer.kt`
- `apps/android/app/src/main/java/com/aci/hermes/HermesTask*.kt`
- `apps/android/app/src/main/java/com/aci/hermes/log/LogBuffer*.kt`
- Any Kotlin file that the failing APK build identifies as a compile error
- `apps/android/app/proguard-rules.pro` (additive only)

### Protected files

- `apps/android/app/src/main/AndroidManifest.xml`
- `apps/android/app/src/main/res/xml/backup_rules.xml`
- `apps/android/app/src/main/res/xml/data_extraction_rules.xml`
- `apps/android/app/src/main/java/com/aci/hermes/data/emergency/**`
- `apps/android/app/src/main/java/com/aci/hermes/audit/**`
- `apps/android/app/src/main/java/com/aci/hermes/owner/**`
- All redactor classes (`*Redactor.kt`)

### Forbidden edits

- Adding any new `<uses-permission>` to AndroidManifest
- Changing `applicationId`, `package`, `minSdk`, `targetSdk`, `versionCode`, `versionName`
- Removing any owner-gate touch-point
- Removing or weakening emergency stop wiring
- Disabling lint checks globally; per-file `@Suppress` requires a comment naming the underlying ticket

### Validation commands

```bash
cd apps/android
./gradlew --no-daemon --stacktrace assembleDebug
./gradlew --no-daemon --stacktrace testDebugUnitTest
./gradlew --no-daemon --stacktrace lint
aapt dump badging app/build/outputs/apk/debug/app-debug.apk | head -20
```

Gate: `Build debug APK` and `Unit tests` (from `#128`) jobs on PR #131 must
flip to success. Permissions diff against `bc97e43` must be IDENTICAL.

### Rollback plan

- `git revert -m 1 <merge-sha>` on PR #131 branch
- APK build returns to last-known-good (Phase 4 final checkpoint `2276e04` per `INTEGRATION_LOG.md`)

---

## Lane C — Chat UI revival (Claude-owned)

| Field | Value |
|-------|-------|
| Branch name | `launch/chat-ui-claude-C` |
| Base | PR #131 tip after lane B merges |
| Owner | Claude |
| Parallel-safe with | D, E (different screen files) |
| Merge order | 3rd or later — after B; parallel with D and E; before H |

### Allowed files

- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/chat/**` (new)
- `apps/android/app/src/main/java/com/aci/hermes/data/jarvis/JarvisChat*.kt` (existing, data layer already lives on PR #131)
- `apps/android/app/src/main/java/com/aci/hermes/data/jarvis/JarvisClipboard.kt`
- `apps/android/app/src/main/java/com/aci/hermes/data/jarvis/JarvisInlineCard.kt`
- `apps/android/app/src/main/java/com/aci/hermes/data/jarvis/JarvisIntentClassifier.kt`
- `apps/android/app/src/main/java/com/aci/hermes/data/jarvis/MockJarvisChatGateway.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/navigation/HermesNavGraph.kt` (chat route registration only)
- `apps/android/app/src/main/res/values/strings.xml` (chat-related entries only)
- `apps/android/app/src/test/java/com/aci/hermes/ui/screens/chat/**` (new tests)

### Protected files

- All of lane B's allowed list (lane B owns build wiring)
- AppContainer.kt — chat may register a new ViewModel factory; nothing else
- Any owner-auth, owner-gate, or emergency-stop file
- All other screen files (lanes D and E own theirs)

### Forbidden edits

- Adding `<uses-permission>` of any kind
- Calling network APIs outside of `JarvisChatGateway` abstraction
- Removing or weakening `PrivacyRedactor` / `MemoryRedactor` in chat-adjacent paths
- Replacing `MockJarvisChatGateway` wiring with a real network gateway without explicit owner sign-off (#127 is owner-deferred per audit Q5)
- Modifying lane D's icon-state mapper

### Validation commands

```bash
cd apps/android
./gradlew --no-daemon --stacktrace assembleDebug
./gradlew --no-daemon --stacktrace testDebugUnitTest --tests "com.aci.hermes.ui.screens.chat.*"
./gradlew --no-daemon --stacktrace lint
```

Manual: launch MUSE app, navigate to Chat route, send a mock
message via MockJarvisChatGateway, confirm bottom nav remains visible and
emergency stop is reachable.

### Rollback plan

- `git revert -m 1 <merge-sha>` on PR #131 branch
- Chat route falls back to `PlaceholderScreen` per current demo trace

---

## Lane D — Interactive icon UI revival (Claude-owned)

| Field | Value |
|-------|-------|
| Branch name | `launch/icon-ui-claude-D` |
| Base | PR #131 tip after lane B merges |
| Owner | Claude |
| Parallel-safe with | C, E (different files) |
| Merge order | 3rd or later — after B; parallel with C and E; before H |

### Allowed files

- `apps/android/app/src/main/java/com/aci/hermes/ui/jarvis/JarvisPrimeIcon.kt` (new composable; data layer at `IconState*` already exists)
- `apps/android/app/src/main/java/com/aci/hermes/ui/jarvis/JarvisPrimeIconAnimation.kt` (new)
- `apps/android/app/src/main/java/com/aci/hermes/ui/jarvis/JarvisIconColors.kt` (palette — existing)
- `apps/android/app/src/main/java/com/aci/hermes/ui/jarvis/IconState.kt` (existing — read-only reference, do not break parity)
- `apps/android/app/src/main/java/com/aci/hermes/ui/jarvis/IconStateMapper.kt` (existing — read-only reference)
- `apps/android/app/src/main/java/com/aci/hermes/ui/jarvis/OrchestratorIconStateMapping.kt` (existing — read-only reference)
- `apps/android/app/src/test/java/com/aci/hermes/ui/jarvis/**` (new presence/animation tests)

### Protected files

- All of lane B and lane C allowed lists
- AppContainer.kt (icon may consume an existing state flow; no new factories required)
- Any owner-auth, gate, or emergency-stop file
- Chat screen files (lane C owns)

### Forbidden edits

- Adding `<uses-permission>`
- Breaking parity with `IconStateMapper` orchestration → state map; the
  composable consumes `IconState`, never reimplements the mapping
- Embedding gesture handlers that bypass `EmergencyStopController`

### Validation commands

```bash
cd apps/android
./gradlew --no-daemon --stacktrace assembleDebug
./gradlew --no-daemon --stacktrace testDebugUnitTest --tests "com.aci.hermes.ui.jarvis.*"
./gradlew --no-daemon --stacktrace lint
```

Manual: home screen presence indicator transitions through idle / thinking /
acting / waiting-approval states; emergency stop tap from icon area still
routes through confirm dialog.

### Rollback plan

- `git revert -m 1 <merge-sha>` on PR #131 branch
- App falls back to data layer + state mapper only (current PR #131 state)

---

## Lane E — Approvals / memory / audit / control polish (Claude-owned)

| Field | Value |
|-------|-------|
| Branch name | `launch/polish-claude-E` |
| Base | PR #131 tip after lane B merges |
| Owner | Claude |
| Parallel-safe with | C, D (different files) |
| Merge order | 3rd or later — after B; parallel with C and D; before H |

### Allowed files

- `apps/android/app/src/main/java/com/aci/hermes/approval/ui/screens/ApprovalsScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/approval/ui/**` (ViewModel, cards)
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/memory/MemoryScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/memory/**` (ViewModel)
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/audit/AuditScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/audit/AuditDetailScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/audit/**` (ViewModel)
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/control/ControlScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/control/**` (ViewModel — wire #115's `ControlViewModel`)
- `apps/android/app/src/main/res/values/strings.xml` (entries scoped to the four screens above)
- `apps/android/app/src/test/java/com/aci/hermes/approval/**`
- `apps/android/app/src/test/java/com/aci/hermes/ui/screens/memory/**`
- `apps/android/app/src/test/java/com/aci/hermes/ui/screens/audit/**`
- `apps/android/app/src/test/java/com/aci/hermes/ui/screens/control/**`

### Protected files

- `OWNER_GATED_ACTIONS` frozenset (in `owner_auth.py`)
- `AUTHORIZATION_PHRASE` (in `owner_auth.py`)
- `EmergencyStopController.kt`, `EmergencyStopRepository.kt`, `EmergencyStopAuditEvent.kt`, `EmergencyStopState.kt`
- `SecretRedactor.kt`, `MemoryRedactor.kt`, `PrivacyRedactor.kt` (lane F owns redaction)
- Chat screen files (lane C owns)
- Icon UI composable (lane D owns)

### Forbidden edits

- Weakening or bypassing any redactor when displaying audit / memory / approval rows
- Removing audit-event emission from approval or emergency-stop flows
- Adding owner-gated actions without going through the owner-gate review
- Routing any approval action that bypasses the existing approval store

### Validation commands

```bash
cd apps/android
./gradlew --no-daemon --stacktrace assembleDebug
./gradlew --no-daemon --stacktrace testDebugUnitTest --tests "com.aci.hermes.approval.*" --tests "com.aci.hermes.ui.screens.memory.*" --tests "com.aci.hermes.ui.screens.audit.*" --tests "com.aci.hermes.ui.screens.control.*"
./gradlew --no-daemon --stacktrace lint
```

Manual: walk golden path from `docs/jarvis-prime-integration-demo-trace.md`
section 4. Confirm emergency-stop confirm dialog still gates every halt.

### Rollback plan

- `git revert -m 1 <merge-sha>` on PR #131 branch
- Screens fall back to PR #131 baseline (real screens already wired; this lane is polish)

---

## Lane F — Security / CodeQL / redaction audit (Codex-owned)

| Field | Value |
|-------|-------|
| Branch name | `launch/security-codex-F` |
| Base | PR #131 tip after lane A merges |
| Owner | Codex |
| Parallel-safe with | B, G (different file scopes) |
| Merge order | 2nd or later — after A; parallel with B; before G and H |

### Allowed files

- `agent/redact.py`
- `hermes_logging.py`
- Any Python file flagged by the 12 outstanding CodeQL clear-text-logging threads
- `apps/android/app/src/main/java/com/aci/hermes/audit/SecretRedactor.kt`
- `apps/android/app/src/main/java/com/aci/hermes/memory/MemoryRedactor.kt`
- `apps/android/app/src/main/java/com/aci/hermes/social/PrivacyRedactor.kt`
- Tests under `tests/test_*redact*.py`
- Tests under `apps/android/app/src/test/java/com/aci/hermes/**/redact*` and audit
- `.github/codeql/**` (config; never remove)

### Protected files

- `hermes_cli/jarvis_prime/owner_auth.py` (`AUTHORIZATION_PHRASE`, `OWNER_GATED_ACTIONS`)
- `hermes_cli/jarvis_prime/gates.py`
- AndroidManifest, backup rules, data extraction rules
- Anything under lanes B, C, D, E unless the diff is strictly an additional redaction call site

### Forbidden edits

- Removing any existing redaction call site
- Reducing the entropy / coverage of any redactor's pattern set
- Suppressing CodeQL findings via inline comments instead of fixing the underlying log call
- Disabling CodeQL workflow or query packs

### Validation commands

```bash
ruff check agent/ hermes_logging.py hermes_cli/
python3 -m pytest tests/test_*redact*.py tests/test_jarvis_prime_owner_auth.py -q
cd apps/android && ./gradlew --no-daemon --stacktrace testDebugUnitTest --tests "*Redactor*Test"
gh run list --limit 5 --workflow codeql
```

CodeQL gate: 0 outstanding clear-text-logging alerts on PR #131.

### Rollback plan

- `git revert -m 1 <merge-sha>` on PR #131 branch
- CodeQL reverts to 12 outstanding alerts (current baseline)

---

## Lane G — Test expansion / launch gate (Codex-owned)

| Field | Value |
|-------|-------|
| Branch name | `launch/tests-codex-G` |
| Base | PR #131 tip after lane F merges |
| Owner | Codex |
| Parallel-safe with | H planning (G writes assertions, H reads them) |
| Merge order | 3rd or later — after A and F; before H |

### Allowed files

- `tests/**` (new test files; additions to existing test files where the
  test target already exists in production)
- `tests/conftest.py`
- `tests/fixtures/**`
- `apps/android/app/src/test/**` (new unit tests)
- `apps/android/app/src/androidTest/**` (new instrumentation tests)
- `pyproject.toml` (test dependency section only)

### Protected files

- All production code under `hermes_cli/`, `agent/`, `apps/android/app/src/main/`
- Existing tests that assert owner-gate behavior (`test_jarvis_prime_owner_auth.py`, `test_jarvis_prime_gates.py`) — additive only; never weaken assertions

### Forbidden edits

- Modifying production code from a test branch
- Replacing real owner-auth or gate behavior with mocks that bypass the gate
- Marking a previously passing test `@pytest.mark.skip` without a documented root-cause issue

### Validation commands

```bash
python3 -m pytest tests/ -q -n auto --timeout=30 --timeout-method=signal
python3 -m pytest tests/test_jarvis_prime_*.py tests/test_orchestrator_*.py -q
ruff check tests/
cd apps/android && ./gradlew --no-daemon --stacktrace testDebugUnitTest
```

Launch gate: 100% of the lanes covered in `LAUNCH_READINESS_CHECKLIST.md`
have at least one new test asserting the lane's contract. Pre-existing LSP
failures (`tests/agent/lsp/test_client_e2e.py`, 4 failures, baseline on `main`)
remain documented as out-of-scope.

### Rollback plan

- `git revert -m 1 <merge-sha>` on PR #131 branch
- Test suite returns to Phase 4 baseline (398 passed, 1 skipped)

---

## Lane H — Final integration (Claude-owned)

| Field | Value |
|-------|-------|
| Branch name | `launch/final-integration-claude-H` |
| Base | PR #131 tip after A, B, C, D, E, F, G have merged |
| Owner | Claude |
| Parallel-safe with | I (I reviews H) |
| Merge order | 8th — only lane I follows |

### Allowed files

- `apps/android/app/src/main/java/com/aci/hermes/di/AppContainer.kt` (final wiring)
- `apps/android/app/src/main/java/com/aci/hermes/ui/navigation/HermesNavGraph.kt` (final route catalog)
- `apps/android/app/src/main/java/com/aci/hermes/ui/navigation/Screen.kt`
- `apps/android/app/src/main/res/values/strings.xml` (final unification of per-lane additions)
- `apps/android/README.md`
- `README.md`
- `docs/jarvis-prime-integration-demo-trace.md` (regenerate sections that lanes C, D, E changed)
- `INTEGRATION_LOG.md` (append Phase 9 closure)

### Protected files

- Anything in `OWNER_GATED_ACTIONS`, `AUTHORIZATION_PHRASE` — preserved verbatim
- AndroidManifest permissions — must remain identical to `bc97e43` baseline
- All redactor classes — preserved
- `.github/workflows/*` — owned by lane A; H may only rebase, not rewrite

### Forbidden edits

- Reverting another lane's commit without that lane's owner approving
- Introducing new dependencies (`build.gradle.kts`, `pyproject.toml`)
- Resolving a merge conflict by deleting a redaction call site or owner-gate hook
- Touching secrets

### Validation commands

```bash
ruff check .
python3 scripts/check-windows-footguns.py --all
python3 -m pytest tests/ -q -n auto --timeout=30 --timeout-method=signal
cd apps/android && ./gradlew --no-daemon --stacktrace lint testDebugUnitTest assembleDebug
aapt dump badging apps/android/app/build/outputs/apk/debug/app-debug.apk | head -20
diff <(git show bc97e43:apps/android/app/src/main/AndroidManifest.xml) apps/android/app/src/main/AndroidManifest.xml
```

Gate: every check on PR #131 green; permissions diff empty; demo-trace
golden path walks end-to-end on a fresh install.

### Rollback plan

- `git revert -m 1 <merge-sha>` on PR #131 branch
- PR #131 returns to post-G state; lanes A–G remain landed; H is re-attempted

---

## Lane I — Final independent review (Codex-owned)

| Field | Value |
|-------|-------|
| Branch name | `launch/review-codex-I` (docs-only) |
| Base | PR #131 tip after H merges |
| Owner | Codex |
| Parallel-safe with | none — terminal |
| Merge order | 9th — last |

### Allowed files

- `docs/launch/LAUNCH_REVIEW.md` (new)
- PR #131 review comments (via `mcp__github__pull_request_review_write`)

### Protected files

- Everything outside `docs/launch/LAUNCH_REVIEW.md`. This lane is read-only on code.

### Forbidden edits

- Any code change, even cosmetic
- Posting comments before completing the full LAUNCH_READINESS_CHECKLIST.md walk
- Issuing the owner authorization phrase

### Validation commands

```bash
ruff check .
python3 scripts/check-windows-footguns.py --all
python3 -m pytest tests/ -q -n auto --timeout=30 --timeout-method=signal
cd apps/android && ./gradlew --no-daemon --stacktrace lint testDebugUnitTest assembleDebug
gh pr checks 131
```

Output: `docs/launch/LAUNCH_REVIEW.md` with one of three verdicts —
`READY-FOR-OWNER`, `READY-AFTER-FIXLIST`, or `NOT-READY`.

### Rollback plan

- N/A — review is non-mutating. A `NOT-READY` verdict reopens lanes as needed.

---

## Merge order summary

```
A  CI / workflow repair                   (Codex)  → unblocks all CI
│
├─ B  Android build stabilization         (Claude) → unblocks C, D, E
│  │
│  ├─ C  Chat UI revival                  (Claude)  ┐
│  ├─ D  Interactive icon UI revival      (Claude)  ├─ parallel
│  └─ E  Approvals/memory/audit/control   (Claude)  ┘
│
├─ F  Security / CodeQL / redaction       (Codex)   ┐ parallel with B
│                                                    │
└─ G  Test expansion / launch gate        (Codex)   ┘ after F

→ H  Final integration                    (Claude)  (rebase + reconcile)
→ I  Final independent review             (Codex)   (read-only verdict)

→ (OWNER) authorization phrase to merge PR #131 to main
```

## Parallel-safe pairs (run at the same time)

- A ‖ F (different scopes: workflows vs redaction)
- B ‖ F (different scopes: Android build vs Python redaction)
- C ‖ D ‖ E (different screen subtrees, after B)
- F ‖ G (F closes CodeQL, G asserts coverage; G depends on F's tests existing first)

## Sequential dependencies (must not run in parallel)

- A → B (B needs CI green to validate)
- B → C, D, E (screens need APK building)
- F → G (G writes tests that assert against F's redactor strengthening)
- A, B, C, D, E, F, G → H (H reconciles)
- H → I (I is read-only verdict)
