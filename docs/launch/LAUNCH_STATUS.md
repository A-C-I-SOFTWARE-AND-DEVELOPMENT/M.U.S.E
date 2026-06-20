# Launch Status — muse + Hermes runtime

> ⚠️ **SUPERSEDED (2026-06-01).** This document was written on 2026-05-26
> against PR #131 / base `bc97e43`. `main` is now 211 commits past that base
> and most of the work described below as pending has landed. Its "🔴 RED —
> 52%" verdict **no longer reflects the tree**. For current readiness see
> [`LAUNCH_STATUS_CURRENT.md`](./LAUNCH_STATUS_CURRENT.md) and the audit at
> [`../audits/CODEBASE_AUDIT_2026-06-01.md`](../audits/CODEBASE_AUDIT_2026-06-01.md).
> Kept for historical reference only.

**Trunk PR:** [#131](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent/pull/131)
**Head branch:** `claude/hopeful-bardeen-KBVqi`
**Base:** `origin/main` at `bc97e43`
**Generated:** 2026-05-26
**Branch matrix:** [`LAUNCH_BRANCH_MATRIX.md`](./LAUNCH_BRANCH_MATRIX.md)
**Checklist:** [`LAUNCH_READINESS_CHECKLIST.md`](./LAUNCH_READINESS_CHECKLIST.md)

## Current verdict

**🔴 RED — not launch-ready.**

PR #131 has integrated 18 of 53 in-scope PRs and brought the Python runtime
+ Android app to a coherent state on top of `bc97e43`. Four CI checks are
red and four owner decisions are open. The integration trunk is stable
for further work, but it must not merge to `main` and must not deploy
until every lane in [`LAUNCH_BRANCH_MATRIX.md`](./LAUNCH_BRANCH_MATRIX.md)
closes and lane I issues `READY-FOR-OWNER`.

## Blockers (must close before owner authorization)

| # | Blocker | Lane | Severity |
|---|---------|------|----------|
| B1 | `Build debug APK` CI job failing on PR #131 | B | critical |
| B2 | `Unit tests` (added by #128) CI job failing on PR #131 (rolled up under `Build debug APK`) | B | critical |
| B3 | `test` (pytest) CI job failing on PR #131 | G (root cause) / A (workflow if config) | critical |
| B4 | `Lint` CI job failing on PR #131 (ruff blocking is green; failure is in `ruff + ty diff` or another step) | A | high |
| B5 | `CodeQL` CI job failing on PR #131 (12 outstanding clear-text-logging threads, see audit) | F | high |
| B6 | Chat UI is `PlaceholderScreen` only — composable + ViewModel reverted in `3356f03` | C | medium |
| B7 | Interactive `JarvisPrimeIcon` composable absent — only state layer landed | D | medium |
| B8 | Demo-trace golden path (`docs/jarvis-prime-integration-demo-trace.md` §4) currently has placeholder text on step 17.9 (chat) and step 17.4 (icon presence) | C / D / H | medium |
| B9 | `INTEGRATION_LOG.md` Phase 5–8 entries exist twice (Phase 4 escalation + Phase 4 selective execution) — needs reconciled Phase 9 closure | H | low |

## Risks (do not block but must be tracked)

| # | Risk | Lane | Mitigation |
|---|------|------|------------|
| R1 | Per-PR conflict cost projection at Phase 4.2 (#107 produced 5 conflicts; #115 5 more) — future lane-C/D revival may re-surface AppContainer / Screen / NavGraph collisions | C / D / H | Lane H reconciles centralized files last; per-lane diffs stay surgical |
| R2 | The 12 outstanding CodeQL clear-text-logging threads may be false positives in `#109`'s already-redacted call sites — fix may require additional `re.sub` taint-break work | F | Lane F documents per-thread reasoning in `LAUNCH_REVIEW.md` |
| R3 | Pre-existing LSP test failures (`tests/agent/lsp/test_client_e2e.py`, 4) are baseline on `main` and out of scope; risk that CI conflates them with new failures | A / G | Lane A pins pytest filter; lane G documents the four expected failures |
| R4 | `#125`'s partial cherry-pick may have left dead imports in `HomeScreen`-adjacent files | B / H | Lane B's APK build will fail loudly if dead imports exist |
| R5 | `ty` advisory warnings (7 currently) creep up across lanes | A / G | Lane A retains the count cap in `lint.yml`; lanes that add a warning must justify in PR body |
| R6 | Manifest-merger surprise: a transitive AAR could introduce a permission silently | B / H | Lane H gates on `aapt dump permissions` matching baseline |
| R7 | Wave 0 duplicate cluster (#93–#102) still open; owner has not closed manually | (none) | Out of scope; documented in PR #131 body; lane I re-asserts in final review |
| R8 | `#127` gateway event spine (orphan, 378 files) is deferred; downstream chat lane assumes `MockJarvisChatGateway` remains the production gateway | C | Lane C wiring stays mock-only; owner Q5 stays open |
| R9 | `#123` voice (`RECORD_AUDIO`) is deferred; if revived later, every lane's "no new permission" gate must re-validate | All | Lane I checklist row 8.4 stays GREEN |

## What can be parallelized now

These six lane prompts can be dispatched simultaneously after this plan PR
lands. They touch disjoint file sets and validate against disjoint CI signals.

- **A (Codex)** — CI workflow repair: fixes `Lint`, `test`, `Build debug APK` from the workflow side. Unblocks B and G.
- **F (Codex)** — Security / CodeQL: closes the 12 outstanding threads. Parallel with A and B.

Once **A** is green, fan out:

- **B (Claude)** — Android build stabilization: bring `Build debug APK` + `Unit tests` to green.
- **G (Codex)** — Test expansion: assert every lane's contract. Depends on F first.

Once **B** is green, fan out:

- **C (Claude)** — Chat UI revival.
- **D (Claude)** — Interactive icon UI revival.
- **E (Claude)** — Approvals / memory / audit / control polish.

C, D, E touch disjoint screen subtrees and may run together.

## What must wait for owner approval

Per [`INTEGRATION_AUDIT.md`](../audits/INTEGRATION_AUDIT.md) §"Owner-gated decisions":

- **Q4** — `#123` voice capture / `RECORD_AUDIO` disposition. Until decided, no lane may add a recording permission.
- **Q5** — `#127` gateway event spine disposition. Until decided, chat lane C wires only `MockJarvisChatGateway`.
- **Q6** — Revival of the reverted `#117` chat UI + `#119` icon composable is owner-acknowledged but the actual revival work runs in lanes C and D under this plan.
- **Q7** — 25 older Phase PRs (#4–#84) re-evaluation strategy. Out of scope for this plan; lane I documents recommendation.
- **The merge of PR #131 to `main`** — requires the literal phrase from `hermes_cli/jarvis_prime/owner_auth.py:AUTHORIZATION_PHRASE`. This commander does **not** issue that phrase. Lane I produces the verdict; the owner alone authorizes.
- **Closing the 10 Wave 0 duplicate PRs (#93–#102)** — safety rule prevents this branch from closing them; owner closes manually.

## Exact next branch prompts

The following six prompts are ready to dispatch in parallel after the plan
PR merges. Each prompt is self-contained for a fresh agent.

### Prompt 1 — Lane A (Codex)

```
You are Codex acting as the CI engineer for A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent.

Base: PR #131 head branch claude/hopeful-bardeen-KBVqi
Create branch: launch/ci-codex-A

Mission: bring four failing checks on PR #131 to green without removing any
check, weakening any gate, or modifying production source.

Failing checks to fix:
- Lint
- test (pytest)
- Build debug APK
- CodeQL (config side only — redaction itself is lane F)

Allowed files (additive or surgical changes only):
- .github/workflows/{android-build,lint,tests,orchestration-tests,uv-lockfile-check,history-check,contributor-check,skills-index,osv-scanner,supply-chain-audit,nix,nix-lockfile-fix,docs-site-checks}.yml
- pyproject.toml (ruff/ty/pytest config sections)
- .ruff.toml
- scripts/check-windows-footguns.py

Forbidden:
- editing apps/android/app/src/main/**
- editing hermes_cli/jarvis_prime/{owner_auth,gates}.py
- removing or skipping any check
- bypassing CodeQL
- modifying upload_to_pypi.yml, docker-publish.yml, deploy-site.yml

Validate:
ruff check .
python3 scripts/check-windows-footguns.py --all
python3 -m pytest tests/ -q -n auto --timeout=30 --timeout-method=signal

Commit + open draft PR titled: fix(ci): repair launch workflow paths
```

### Prompt 2 — Lane B (Claude)

```
You are Claude acting as the Android build engineer for A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent.

Base: PR #131 head branch claude/hopeful-bardeen-KBVqi (after lane A lands)
Create branch: launch/android-build-claude-B

Mission: bring Build debug APK + Unit tests jobs to green. Permissions must
remain identical to bc97e43 baseline.

Allowed files: apps/android/app/build.gradle.kts, apps/android/build.gradle.kts,
apps/android/settings.gradle.kts, apps/android/gradle/libs.versions.toml,
apps/android/gradle.properties, AppContainer.kt, HermesTask*.kt, LogBuffer*.kt,
plus any file the failing build identifies as a compile error.

Protected: AndroidManifest.xml, backup_rules.xml, data_extraction_rules.xml,
EmergencyStop*, owner_auth, redactor classes.

Forbidden: new <uses-permission>; changes to applicationId, package, minSdk,
targetSdk, versionCode, versionName; removing owner-gate touch-points;
disabling lint globally.

Validate:
cd apps/android && ./gradlew --no-daemon --stacktrace assembleDebug testDebugUnitTest lint
aapt dump badging app/build/outputs/apk/debug/app-debug.apk | head -20
diff <(git show bc97e43:apps/android/app/src/main/AndroidManifest.xml) apps/android/app/src/main/AndroidManifest.xml  # must be empty

Commit + open draft PR titled: fix(android): stabilize debug APK build
```

### Prompt 3 — Lane C (Claude)

```
You are Claude reviving the muse chat composable for A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent.

Base: PR #131 head branch claude/hopeful-bardeen-KBVqi (after lane B lands)
Create branch: launch/chat-ui-claude-C

Mission: replace the `chat` route's PlaceholderScreen with a real Compose
screen powered by the existing JarvisChat* data layer. MockJarvisChatGateway
is the production gateway until owner Q5 (#127) is decided.

Allowed files: apps/android/app/src/main/java/com/aci/hermes/ui/screens/chat/**
(new); JarvisChat*.kt, JarvisClipboard.kt, JarvisInlineCard.kt,
JarvisIntentClassifier.kt, MockJarvisChatGateway.kt (existing data layer);
HermesNavGraph.kt (chat route registration only); strings.xml (chat-only
entries); new tests under apps/android/app/src/test/java/com/aci/hermes/ui/screens/chat/**.

Protected: lane B's allowed list; AppContainer.kt (only a new VM factory);
owner-auth / gate / emergency-stop files; other screens.

Forbidden: new <uses-permission>; network calls outside JarvisChatGateway;
weakening redaction; replacing MockJarvisChatGateway wiring.

Validate:
cd apps/android && ./gradlew --no-daemon --stacktrace assembleDebug testDebugUnitTest --tests "com.aci.hermes.ui.screens.chat.*" lint

Commit + open draft PR titled: feat(android): revive muse chat screen
```

### Prompt 4 — Lane D (Claude)

```
You are Claude reviving the interactive JarvisPrimeIcon for A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent.

Base: PR #131 head branch claude/hopeful-bardeen-KBVqi (after lane B lands)
Create branch: launch/icon-ui-claude-D

Mission: re-introduce the presence-aware JarvisPrimeIcon composable on top
of the existing IconState mapper. Idle ↔ thinking ↔ acting ↔ waiting-approval
transitions must follow OrchestratorIconStateMapping exactly. Tap gestures
must never bypass the emergency-stop confirm.

Allowed files: apps/android/app/src/main/java/com/aci/hermes/ui/jarvis/
{JarvisPrimeIcon.kt (new), JarvisPrimeIconAnimation.kt (new),
JarvisIconColors.kt (existing), IconState*.kt (read-only)}; new tests under
apps/android/app/src/test/java/com/aci/hermes/ui/jarvis/**.

Protected: lane B / C allowed lists; AppContainer.kt; owner-auth / gate /
emergency-stop files.

Forbidden: new <uses-permission>; re-implementing IconState mapping; gesture
handlers that bypass EmergencyStopController.

Validate:
cd apps/android && ./gradlew --no-daemon --stacktrace assembleDebug testDebugUnitTest --tests "com.aci.hermes.ui.jarvis.*" lint

Commit + open draft PR titled: feat(android): revive interactive muse icon
```

### Prompt 5 — Lane E (Claude)

```
You are Claude polishing the muse approval / memory / audit / control
surfaces for A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent.

Base: PR #131 head branch claude/hopeful-bardeen-KBVqi (after lane B lands)
Create branch: launch/polish-claude-E

Mission: bring Approvals, Memory, Audit, AuditDetail, and Control screens to
launch quality. Wire #115's ControlViewModel into the ControlScreen factory.
Tighten emergency-stop confirm copy / behavior. Add ViewModel tests for the
four screens.

Allowed files: ApprovalsScreen.kt + approval/ui/**; MemoryScreen.kt +
ui/screens/memory/**; AuditScreen.kt, AuditDetailScreen.kt + ui/screens/audit/**;
ControlScreen.kt + ui/screens/control/**; strings.xml entries scoped to the
four screens; new tests under each src/test counterpart.

Protected: OWNER_GATED_ACTIONS, AUTHORIZATION_PHRASE, EmergencyStop*,
SecretRedactor / MemoryRedactor / PrivacyRedactor (read-only), chat screen
(lane C), icon composable (lane D).

Forbidden: weakening any redactor; removing audit-event emission; adding to
OWNER_GATED_ACTIONS without owner sign-off; bypassing the approval store.

Validate:
cd apps/android && ./gradlew --no-daemon --stacktrace assembleDebug testDebugUnitTest --tests "com.aci.hermes.approval.*" --tests "com.aci.hermes.ui.screens.memory.*" --tests "com.aci.hermes.ui.screens.audit.*" --tests "com.aci.hermes.ui.screens.control.*" lint

Commit + open draft PR titled: feat(android): polish approvals/memory/audit/control
```

### Prompt 6 — Lane F (Codex)

```
You are Codex acting as the security engineer for A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent.

Base: PR #131 head branch claude/hopeful-bardeen-KBVqi (parallel-safe with lane A)
Create branch: launch/security-codex-F

Mission: close the 12 outstanding CodeQL clear-text-logging threads on PR #131
by strengthening Python redaction (agent/redact.py, hermes_logging.py) and
Android redactors (SecretRedactor, MemoryRedactor, PrivacyRedactor). Each
remaining alert must either be resolved by an additional redact call or
documented as a CodeQL false positive with reasoning.

Allowed files: agent/redact.py, hermes_logging.py, any Python file flagged
by the 12 alerts, SecretRedactor.kt, MemoryRedactor.kt, PrivacyRedactor.kt,
tests/test_*redact*.py, redactor tests under apps/android/app/src/test/**,
.github/codeql/** (config — never remove).

Protected: AUTHORIZATION_PHRASE, OWNER_GATED_ACTIONS, owner_auth.py,
gates.py, AndroidManifest.xml, backup/data-extraction rules.

Forbidden: removing any redact call site; reducing pattern coverage;
suppressing CodeQL alerts via inline comments instead of fixing the call;
disabling CodeQL workflow.

Validate:
ruff check agent/ hermes_logging.py hermes_cli/
python3 -m pytest tests/test_*redact*.py tests/test_jarvis_prime_owner_auth.py -q
cd apps/android && ./gradlew --no-daemon --stacktrace testDebugUnitTest --tests "*Redactor*Test"
gh pr checks 131  # CodeQL must flip to success

Commit + open draft PR titled: fix(security): close CodeQL clear-text-logging threads
```

### Prompt 7 — Lane G (Codex)

```
You are Codex acting as the test engineer for A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent.

Base: PR #131 head branch claude/hopeful-bardeen-KBVqi (after lane F lands)
Create branch: launch/tests-codex-G

Mission: assert every contract in LAUNCH_READINESS_CHECKLIST.md with new
tests. No production code changes. Pre-existing LSP failures
(tests/agent/lsp/test_client_e2e.py, 4) stay documented as out-of-scope.

Allowed files: tests/** (new files + additions where the test target already
exists in production), tests/conftest.py, tests/fixtures/**,
apps/android/app/src/test/**, apps/android/app/src/androidTest/**,
pyproject.toml (test dep section only).

Protected: all production source.

Forbidden: modifying production code from this branch; replacing real
owner-auth behavior with bypassing mocks; marking previously-passing tests
@skip without a root-cause issue.

Validate:
python3 -m pytest tests/ -q -n auto --timeout=30 --timeout-method=signal
ruff check tests/
cd apps/android && ./gradlew --no-daemon --stacktrace testDebugUnitTest

Commit + open draft PR titled: test(launch): expand coverage for launch gate
```

### Prompt 8 — Lane H (Claude)

```
You are Claude finalising the muse + Hermes integration for A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent.

Base: PR #131 head branch claude/hopeful-bardeen-KBVqi (after A, B, C, D, E, F, G have all merged)
Create branch: launch/final-integration-claude-H

Mission: reconcile any centralized-file conflicts (AppContainer.kt, Screen.kt,
HermesNavGraph.kt, strings.xml), regenerate the demo trace, append a Phase 9
closure to INTEGRATION_LOG.md, and bring every CI check on PR #131 to green
without weakening any safety gate.

Allowed files: AppContainer.kt, HermesNavGraph.kt, Screen.kt, strings.xml,
apps/android/README.md, README.md, docs/jarvis-prime-integration-demo-trace.md,
INTEGRATION_LOG.md.

Protected: OWNER_GATED_ACTIONS, AUTHORIZATION_PHRASE, AndroidManifest
permissions, all redactor classes, .github/workflows/** (rebase only).

Forbidden: reverting another lane's commit without that owner's approval;
introducing new dependencies; weakening redaction during a merge conflict;
modifying secrets.

Validate:
ruff check . && python3 scripts/check-windows-footguns.py --all
python3 -m pytest tests/ -q -n auto --timeout=30 --timeout-method=signal
cd apps/android && ./gradlew --no-daemon --stacktrace lint testDebugUnitTest assembleDebug
diff <(git show bc97e43:apps/android/app/src/main/AndroidManifest.xml) apps/android/app/src/main/AndroidManifest.xml  # must be empty
gh pr checks 131  # every check must be success

Commit + open draft PR titled: chore(launch): final integration of lane outcomes
```

### Prompt 9 — Lane I (Codex)

```
You are Codex acting as the independent launch reviewer for A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent.

Base: PR #131 head branch claude/hopeful-bardeen-KBVqi (after lane H merges)
Create branch: launch/review-codex-I (docs-only)

Mission: walk LAUNCH_READINESS_CHECKLIST.md row-by-row on a clean clone.
Produce docs/launch/LAUNCH_REVIEW.md with one of:
- READY-FOR-OWNER (all rows GREEN; owner-gate intent preserved)
- READY-AFTER-FIXLIST (≤ N rows YELLOW; enumerate each)
- NOT-READY (any RED row)

Do not edit any code file. Do not issue the owner authorization phrase.
Do not merge any PR.

Validate:
ruff check . && python3 scripts/check-windows-footguns.py --all
python3 -m pytest tests/ -q -n auto --timeout=30 --timeout-method=signal
cd apps/android && ./gradlew --no-daemon --stacktrace lint testDebugUnitTest assembleDebug
gh pr checks 131

Commit + open draft PR titled: docs(launch): independent launch review verdict
```

## Owner-only follow-ups (this commander will not perform)

- Issue the literal `AUTHORIZATION_PHRASE` to merge PR #131 to `main`
- Close the 10 Wave 0 duplicate PRs (#93–#102) manually
- Decide Q4 (`RECORD_AUDIO` / #123)
- Decide Q5 (gateway event spine / #127)
- Decide Q7 (older Phase PRs #4–#84)
- Deploy anything

## Next action for this commander

Open the launch-plan PR from `launch/commander-plan`. Then await owner
direction to dispatch the lane prompts above. Lane prompts run in fresh
agent sessions; this commander does not run them itself.
