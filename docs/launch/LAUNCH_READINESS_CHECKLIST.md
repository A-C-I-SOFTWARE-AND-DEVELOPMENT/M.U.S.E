# Launch Readiness Checklist — muse + Hermes runtime

> ⚠️ **SUPERSEDED (2026-06-01).** Written 2026-05-26 against PR #131 / base
> `bc97e43`; `main` is now 211 commits ahead. The GREEN/YELLOW/RED grades
> below are stale (e.g. chat UI and the interactive icon, marked RED here,
> have since landed). For current readiness see
> [`LAUNCH_STATUS_CURRENT.md`](./LAUNCH_STATUS_CURRENT.md). Kept for history.

**Trunk PR:** [#131](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent/pull/131)
**Base:** `origin/main` at `bc97e43`
**Branch matrix:** [`LAUNCH_BRANCH_MATRIX.md`](./LAUNCH_BRANCH_MATRIX.md)
**Status doc:** [`LAUNCH_STATUS.md`](./LAUNCH_STATUS.md)

Each check is owned by exactly one lane and graded `GREEN` / `YELLOW` / `RED`.
A row only flips to `GREEN` when its evidence is reproducible by an independent
reviewer (lane I) on a clean clone of PR #131.

Legend: 🟢 GREEN ✅ verified; 🟡 YELLOW ⚠️ partial / pending evidence; 🔴 RED ❌ blocker.

---

## 1. Android build

| # | Check | Lane | Evidence path | Status |
|---|-------|------|---------------|--------|
| 1.1 | `./gradlew --no-daemon assembleDebug` exits 0 on CI | B | `android-build.yml` job log | 🔴 |
| 1.2 | `app-debug.apk` produced under `apps/android/app/build/outputs/apk/debug/` | B | CI artifact | 🔴 |
| 1.3 | `aapt dump badging app-debug.apk` reports `package=com.aci.hermes`, `versionCode=1`, `versionName=0.1.0`, `application-label='muse'` | B / H | demo trace §3 | 🟡 (pending CI green) |
| 1.4 | `targetSdk=35`, `minSdk=26` unchanged | B | `apps/android/app/build.gradle.kts` | 🟢 |
| 1.5 | No new gradle dependency added without owner sign-off | B / H | `git diff bc97e43 -- apps/android/gradle/libs.versions.toml` | 🟡 |
| 1.6 | Chat composable compiles end-to-end | C | C lane CI | 🔴 (currently demoted) |
| 1.7 | Interactive `JarvisPrimeIcon` composable compiles | D | D lane CI | 🔴 (currently demoted) |

## 2. Android unit tests

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 2.1 | `./gradlew testDebugUnitTest` exits 0 (job added by #128) | B / G | `android-build.yml` job `Unit tests` | 🔴 |
| 2.2 | `ScreenTest` validates the full route catalog (`splash`, `onboarding`, `home`, `tasks`, `chat`, `approvals`, `memory`, `audit`, `audit_detail/{auditId}`, `capability`, `control`, `settings`, `diagnostics`, `task_detail/{taskId}`) | E / G | `apps/android/app/src/test/java/com/aci/hermes/ui/navigation/ScreenTest.kt` | 🟡 |
| 2.3 | `AuditFormattingTest` covers secret-redactor masks | F / G | `apps/android/app/src/test/java/com/aci/hermes/audit/AuditFormattingTest.kt` | 🟡 |
| 2.4 | IconState mapper has ≥3 pure-JUnit tests (idle / thinking / acting variants) | D / G | `apps/android/app/src/test/java/com/aci/hermes/ui/jarvis/IconStateMapperTest.kt` | 🟢 |
| 2.5 | Chat ViewModel tests cover empty / streaming / error states | C / G | `apps/android/app/src/test/java/com/aci/hermes/ui/screens/chat/*` | 🔴 (new) |
| 2.6 | Approval ViewModel tests cover empty / pending / resolved | E / G | `apps/android/app/src/test/java/com/aci/hermes/approval/**` | 🟡 |
| 2.7 | Emergency-stop confirm dialog is the only path to halt | E / G | `EmergencyStopControllerTest` | 🟡 |

## 3. Android lint

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 3.1 | `./gradlew lint` exits 0 on CI | B | `android-build.yml` | 🔴 |
| 3.2 | No new lint baseline entries added (additive baseline only with owner note) | B | `apps/android/app/lint-baseline.xml` diff | 🟡 |
| 3.3 | No `@Suppress("...")` added without a code comment naming the underlying ticket | B / E | grep audit | 🟡 |

## 4. Python tests

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 4.1 | `pytest tests/test_jarvis_prime_*.py tests/test_orchestrator_*.py -q` reports 398+ passed, 1 skipped | G | local + CI | 🟢 (per Phase 1 / Phase 4 checkpoint) |
| 4.2 | Full `pytest tests/ -q -n auto --timeout=30 --timeout-method=signal` exits 0 except documented pre-existing LSP failures (`tests/agent/lsp/test_client_e2e.py`, 4) | G | `tests.yml` job log | 🔴 (PR #131 `test` check currently failing) |
| 4.3 | `tests/test_jarvis_prime_owner_auth.py` continues to assert literal `AUTHORIZATION_PHRASE = "Yes, with authorization."` | G / F | unit test | 🟢 |
| 4.4 | `tests/test_jarvis_prime_gates.py` continues to assert `OWNER_GATED_ACTIONS` membership | G / F | unit test | 🟢 |
| 4.5 | New WorkPacket schema (#104) tests pass | G | `tests/test_workpacket*` | 🟢 |
| 4.6 | CLI proposals + handoff tests (#105, 15 tests) pass | G | `tests/test_jarvis_prime_proposals*.py` | 🟢 |

## 5. ruff

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 5.1 | `ruff check .` exits 0 | A / F | `lint.yml` job `ruff enforcement (blocking)` | 🟢 |
| 5.2 | PLW1514 stays blocking; never demoted | A | `pyproject.toml` ruff config | 🟢 |
| 5.3 | No new `# noqa` added without a comment naming the underlying rule and ticket | A / G | grep audit | 🟡 |
| 5.4 | `ruff + ty diff` job stays advisory but produces ≤7 warnings (current baseline) | A | `lint.yml` | 🟡 |

## 6. CodeQL / security

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 6.1 | CodeQL run on PR #131 exits 0 | F | `CodeQL` check on #131 | 🔴 (currently failing) |
| 6.2 | The 12 outstanding clear-text-logging threads close out | F | `gh pr view 131 --json reviewThreads` | 🔴 |
| 6.3 | No new high-severity CodeQL finding introduced by lanes A–H | F | CodeQL diff vs baseline | 🟡 |
| 6.4 | `osv-scanner.yml` job remains green | A | check | 🟢 |
| 6.5 | `supply-chain-audit.yml` job remains green | A | check | 🟢 |
| 6.6 | `Analyze (python|ruby|javascript-typescript|actions)` all green | F | check | 🟢 |

## 7. Owner gates

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 7.1 | `AUTHORIZATION_PHRASE` value equals literal `Yes, with authorization.` | E / F / H | `git show :hermes_cli/jarvis_prime/owner_auth.py | grep AUTHORIZATION_PHRASE` | 🟢 |
| 7.2 | `OWNER_GATED_ACTIONS` frozenset preserved verbatim (16 entries per audit) | F / H | grep | 🟢 |
| 7.3 | No code path within PR #131 prompts or accepts the phrase from a non-owner channel | F | source walk | 🟢 |
| 7.4 | No commit on any lane branch issues the phrase in a commit message, branch name, or PR body | All | git log audit | 🟢 |
| 7.5 | Q4 (RECORD_AUDIO / #123) remains DEFERRED | H | demo trace §7 | 🟢 |
| 7.6 | Q5 (Gateway event spine / #127) remains DEFERRED | H | demo trace §7 | 🟢 |

## 8. Permissions

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 8.1 | `diff bc97e43:AndroidManifest.xml HEAD:AndroidManifest.xml` shows zero `<uses-permission>` deltas | B / H | demo trace §5 | 🟢 |
| 8.2 | `POST_NOTIFICATIONS` is runtime-requested (Android 13+) | B / E | code grep `requestPermissions` | 🟡 |
| 8.3 | `FOREGROUND_SERVICE_DATA_SYNC` declared with matching service `foregroundServiceType` | B | manifest read | 🟢 |
| 8.4 | No background-location, contacts, SMS, microphone, camera permission anywhere on any lane branch | All | manifest + manifest-merger report | 🟢 |

## 9. Emergency stop

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 9.1 | Top-bar emergency-stop button reachable from every shell route | E / H | manual walk | 🟢 |
| 9.2 | Tap → confirm dialog → controller call. No bypass path. | E | `EmergencyStopController` callers | 🟢 |
| 9.3 | Each halt emits an `EmergencyStopAuditEvent` to the audit sink | E / F | `AuditScreen` shows the latest event after a halt | 🟢 |
| 9.4 | Service `OrchestratorService` actually stops (`stopForeground(STOP_FOREGROUND_REMOVE)` + `stopSelf()`) | E | `OrchestratorService` source | 🟡 |
| 9.5 | Cold-restart after a halt resumes in a stopped state until user re-engages | B / E | manual test | 🟡 |

## 10. Redaction

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 10.1 | Python `agent/redact.py` redacts secret-like patterns end-to-end | F | unit tests | 🟢 |
| 10.2 | `hermes_logging` calls route sensitive fields through `safe_log_summary` (22 sites + CodeQL taint break) | F | grep | 🟢 |
| 10.3 | Android `SecretRedactor` covers token / bearer / api-key shapes | F | `AuditFormattingTest` | 🟢 |
| 10.4 | Android `MemoryRedactor` redacts PII when surfacing memory rows | E / F | `MemoryScreen` test | 🟢 |
| 10.5 | Android `PrivacyRedactor` redacts social-pattern identifiers | E / F | unit test | 🟢 |
| 10.6 | Chat history (when revived) routes user content through redactors before persistence | C / F | `JarvisChatGateway` adapter | 🔴 (new) |
| 10.7 | Audit screen never displays an unredacted line (golden-path manual walk) | E | demo trace §4.6 | 🟢 |

## 11. Memory privacy

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 11.1 | Memory entries are local-only; no network sink | E / F | `MemoryRepository` audit | 🟢 |
| 11.2 | Backup rules + data-extraction rules exclude `datastore/hermes_settings.preferences_pb` and `files/hermes_tasks.json` | B | `backup_rules.xml` / `data_extraction_rules.xml` | 🟢 |
| 11.3 | "Forget" action is fully destructive (no soft-delete shadow) | E | repo + test | 🟡 |
| 11.4 | Privacy redactor runs before display, not after persistence | E / F | source walk | 🟢 |

## 12. Approvals

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 12.1 | Approval card UI present at `approvals` route | E | demo trace §4.4 | 🟢 |
| 12.2 | "Approve" emits an audit event; "Reject" emits an audit event | E / F | `ApprovalsScreen` callbacks | 🟡 |
| 12.3 | Approvals are read-only emit-from-app (decision authority lives in runtime) | E | design doc | 🟢 |
| 12.4 | No approval mutation can bypass the approval store | E | grep callers | 🟢 |
| 12.5 | Owner-gated action attempts surface a clear approval request | E / F | `OwnerAuthGuard` + tests | 🟡 |

## 13. Audit / proof

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 13.1 | Audit screen renders the latest events; row taps push to `audit_detail/{auditId}` | E | demo trace §4.6 | 🟢 |
| 13.2 | Every emergency-stop event is logged | E / F | `AuditFormattingTest` | 🟢 |
| 13.3 | Every approval / rejection is logged | E / F | `AuditFormattingTest` | 🟡 |
| 13.4 | Every owner-gated attempt is logged (allowed or denied) | F | python audit log | 🟢 |
| 13.5 | Audit rows are redacted on render | E / F | source walk | 🟢 |

## 14. Chat

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 14.1 | Chat data layer (`JarvisChatGateway`, `JarvisChatChunk`, `JarvisChatMessage`, `JarvisClipboard`, `JarvisInlineCard`, `JarvisIntentClassifier`, `MockJarvisChatGateway`) compiles | C | gradle | 🟢 |
| 14.2 | Chat composable + ViewModel revived; route `chat` returns a real screen (not placeholder) | C | demo trace §4.5 | 🔴 |
| 14.3 | Empty / streaming / error states have visible affordances | C | UI walk | 🔴 |
| 14.4 | Inline cards render without breaking the scroll | C | manual | 🔴 |
| 14.5 | `MockJarvisChatGateway` remains the production gateway until Q5 (#127) is owner-decided | C / H | wiring | 🟢 |

## 15. Icon state

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 15.1 | `IconState` mapper exists and is tested (3+ JUnit cases) | D | unit test | 🟢 |
| 15.2 | `JarvisIconColors` palette tokens match design-system spec | D | `JarvisIconColors.kt` | 🟢 |
| 15.3 | Interactive `JarvisPrimeIcon` composable revived | D | demo walk | 🔴 |
| 15.4 | Presence transitions follow `OrchestratorIconStateMapping` (idle ↔ thinking ↔ acting ↔ waiting-approval) | D | screencap | 🔴 |
| 15.5 | Icon-area gesture never bypasses emergency-stop confirm | D / E | code walk | 🟡 |

## 16. Release notes

| # | Check | Lane | Evidence | Status |
|---|-------|------|----------|--------|
| 16.1 | `INTEGRATION_LOG.md` Phase 9 closure appended with final lane SHAs | H | git log | 🔴 |
| 16.2 | `docs/jarvis-prime-integration-demo-trace.md` regenerated to remove chat-placeholder note (if C lands) and to register interactive icon (if D lands) | H | grep | 🔴 |
| 16.3 | `apps/android/README.md` reflects the post-launch state | H | diff | 🟡 |
| 16.4 | PR #131 body re-summarized to reflect the lane outcomes (still DRAFT pending owner authorization) | H | PR body diff | 🟡 |
| 16.5 | Wave 0 duplicate cluster (#93–#102) referenced as "to be closed manually by owner" — never closed by this branch | H | PR body | 🟢 |

## 17. Demo path

The launch-ready demo path (full golden path) must run end-to-end on a fresh
install of the debug APK. Lane H gates on this walk passing without bug
intervention.

| # | Step | Lane(s) gating | Status |
|---|------|----------------|--------|
| 17.1 | Cold start → Splash with muse caduceus + tagline | B | 🟡 |
| 17.2 | Onboarding → mode selection → permission education → emergency-stop primer | B / E | 🟡 |
| 17.3 | Home → mission-control card, status, quick-links visible | B / D / E | 🟡 |
| 17.4 | Home presence indicator transitions to "thinking" on any orchestrator-busy state | D | 🔴 |
| 17.5 | Tap Approvals quick-link → empty / pending / resolved variants render | E | 🟡 |
| 17.6 | Tap Memory quick-link → mock-seeded local memory rows render redacted | E / F | 🟢 |
| 17.7 | Tap Audit quick-link → recent events list; tap one → push detail | E | 🟢 |
| 17.8 | Tap Capability quick-link → catalog renders | E | 🟢 |
| 17.9 | Tap Chat quick-link → conversation surface renders, send mock message round-trip | C | 🔴 |
| 17.10 | Tap Control bottom-nav → service start/stop + emergency-stop confirm wired | B / E | 🟡 |
| 17.11 | Trigger emergency stop from shell top bar → confirm dialog → halt → audit event visible | E | 🟢 |
| 17.12 | Settings (full-screen push) renders | E | 🟢 |
| 17.13 | Diagnostics (full-screen push) renders | E | 🟢 |
| 17.14 | TaskDetail (deep-link `task_detail/{taskId}`) renders | E | 🟢 |
| 17.15 | Force-stop the app, relaunch — no stale token in memory rows, no leaked secret in any log line | F | 🟡 |

---

## Summary rollup

| Section | Count | GREEN | YELLOW | RED |
|---------|-------|-------|--------|-----|
| 1. Android build | 7 | 1 | 2 | 4 |
| 2. Android unit tests | 7 | 1 | 5 | 1 |
| 3. Android lint | 3 | 0 | 2 | 1 |
| 4. Python tests | 6 | 5 | 0 | 1 |
| 5. ruff | 4 | 2 | 2 | 0 |
| 6. CodeQL / security | 6 | 3 | 1 | 2 |
| 7. Owner gates | 6 | 6 | 0 | 0 |
| 8. Permissions | 4 | 3 | 1 | 0 |
| 9. Emergency stop | 5 | 3 | 2 | 0 |
| 10. Redaction | 7 | 6 | 0 | 1 |
| 11. Memory privacy | 4 | 3 | 1 | 0 |
| 12. Approvals | 5 | 3 | 2 | 0 |
| 13. Audit / proof | 5 | 4 | 1 | 0 |
| 14. Chat | 5 | 2 | 0 | 3 |
| 15. Icon state | 5 | 2 | 1 | 2 |
| 16. Release notes | 5 | 1 | 2 | 2 |
| 17. Demo path | 15 | 6 | 6 | 3 |
| **Total** | **99** | **51** | **28** | **20** |

Launch readiness = **(GREEN / total) = 51 / 99 = 52%**.
Launch is blocked by the 20 RED items; YELLOW items must be re-graded
during lane execution and re-counted by lane I before owner sign-off.
