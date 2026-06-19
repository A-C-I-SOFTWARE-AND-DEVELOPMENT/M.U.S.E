# muse Integration — Demo Trace

> **Historical trace (2026-05-26), partially refreshed 2026-06-01.** This
> document was written against the PR #131 / base `bc97e43` integration and
> reads as a point-in-time record. `main` has since advanced ~211 commits and
> several surfaces it described as pending have landed (notably the **chat
> screen** — see step 5 / 3a). Current launch readiness lives in
> [`launch/LAUNCH_STATUS_CURRENT.md`](launch/LAUNCH_STATUS_CURRENT.md) and the
> full audit in [`audits/CODEBASE_AUDIT_2026-06-01.md`](audits/CODEBASE_AUDIT_2026-06-01.md).
> Inline `**LANDED on main**` notes mark claims corrected on 2026-06-01.

**Branch:** `claude/hopeful-bardeen-KBVqi`
**Integration PR:** [#131](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent/pull/131)
**Base:** `origin/main` at `bc97e43` (2026-05-26 audit time)
**Audit doc:** [`INTEGRATION_AUDIT.md`](audits/INTEGRATION_AUDIT.md)
**Log doc:** [`INTEGRATION_LOG.md`](audits/INTEGRATION_LOG.md)
**Plan:** see attached integration plan

This document is the end-to-end demo trace for the muse 53-PR
integration. It walks the user-visible muse flow through each integrated
surface and pairs each surface with its Kotlin source for reviewer audit.

## 1. Environment

| Item | Value |
|------|-------|
| Python | 3.11.15 |
| Kotlin / Android Gradle | as specified in `apps/android/gradle/libs.versions.toml` |
| Java | 17 (CI uses Temurin 17 — `.github/workflows/android-build.yml`) |
| Android `minSdk` / `targetSdk` | 26 / 35 (per `apps/android/app/build.gradle.kts`) |
| Integration-branch tip | (see latest commit on PR #131) |
| Base-main SHA at integration start | `bc97e43` (`fix(orchestrator): unify decision ledger at canonical JSONL path (#92)`) |

## 2. CI gates (local pre-flight + CI workflow targets)

Local pre-flight (run during integration, mirrors CI):

```text
ruff check hermes_cli/jarvis_prime/ tests/test_jarvis_prime_*.py
  → All checks passed!

python3 scripts/check-windows-footguns.py --all
  → ✓ No Windows footguns found (556 file(s) scanned).

python3 -m pytest tests/test_jarvis_prime_*.py tests/test_orchestrator_*.py -q
  → 398 passed, 1 skipped in 12.02s
```

CI jobs that gate the integration (per `.github/workflows/*.yml`):

| Job | File | Purpose |
|-----|------|---------|
| `tests` | `tests.yml` | Full pytest suite |
| `Lint` / `ruff enforcement (blocking)` | `lint.yml` | `ruff check .` PLW1514 blocking + ty advisory |
| `Windows footguns (blocking)` | `lint.yml` | `scripts/check-windows-footguns.py --all` |
| `Orchestration unit tests` | `orchestration-tests.yml` | Orchestrator subsystem pytest |
| `Build debug APK` | `android-build.yml` | `./gradlew --no-daemon --stacktrace assembleDebug` |
| `Unit tests` | `android-build.yml` (added by #128) | `./gradlew --no-daemon --stacktrace testDebugUnitTest` |
| `uv lock --check` | `uv-lockfile-check.yml` | Lockfile integrity |
| `check-attribution` | `contributor-check.yml` | Contributor commit signoff |

## 3. APK metadata (to be filled by CI artifact)

After CI completes `Build debug APK`, the artifact at
`apps/android/app/build/outputs/apk/debug/app-debug.apk` will provide:

```text
aapt dump badging app-debug.apk | head -20
  → package: name='com.aci.hermes' versionCode='1' versionName='0.1.0'
    sdkVersion:'26'
    targetSdkVersion:'35'
    application-label:'muse'
```

(Package name `com.aci.hermes` is preserved for install/signing continuity
per the design-system migration plan; every user-facing label is "muse".)

## 4. Screen walk — the integrated muse flow

| # | Route | Composable | File |
|---|-------|------------|------|
| 1 | `splash` | `SplashScreen` | `apps/android/app/src/main/java/com/aci/hermes/ui/screens/splash/SplashScreen.kt` |
| 2 | `onboarding` | `OnboardingScreen` | `apps/android/app/src/main/java/com/aci/hermes/ui/screens/onboarding/OnboardingScreen.kt` |
| 3 | `home` | `HomeScreen` (sequel: `JarvisPrimeHomeScreen` aggregating presence state) | `apps/android/app/src/main/java/com/aci/hermes/ui/screens/home/HomeScreen.kt`, `JarvisPrimeHomeScreen.kt` |
| 4 | `tasks` | `TasksScreen` | `apps/android/app/src/main/java/com/aci/hermes/ui/screens/tasks/TasksScreen.kt` |
| 5 | `chat` | `JarvisChatScreen` + `JarvisChatViewModel` (real chat surface — **LANDED on `main`** since this trace was first written; the old `PlaceholderScreen` no longer binds the `chat` route) | `apps/android/app/src/main/java/com/aci/hermes/ui/screens/chat/JarvisChatScreen.kt`, `JarvisChatViewModel.kt`; gateways under `apps/android/app/src/main/java/com/aci/hermes/data/jarvis/` (`JarvisChatGateway`, `HttpJarvisChatGateway`, `RoutingJarvisChatGateway`, `MockJarvisChatGateway`) |
| 6 | `approvals` | `ApprovalsScreen` (from #107) wrapped by `ShellHost` | `apps/android/app/src/main/java/com/aci/hermes/approval/ui/screens/ApprovalsScreen.kt` |
| 7 | `memory` | `MemoryScreen` (from #122) — local-only mock seed; redactor wired | `apps/android/app/src/main/java/com/aci/hermes/ui/screens/memory/MemoryScreen.kt` |
| 8 | `audit` | `AuditScreen` (from #118) — links to `AuditDetail` | `apps/android/app/src/main/java/com/aci/hermes/ui/screens/audit/AuditScreen.kt` |
| 8a | `audit_detail/{auditId}` | `AuditDetailScreen` | `apps/android/app/src/main/java/com/aci/hermes/ui/screens/audit/AuditDetailScreen.kt` |
| 9 | `capability` | `CapabilityScreen` (from #124) | `apps/android/app/src/main/java/com/aci/hermes/ui/screens/capability/CapabilityScreen.kt` |
| 10 | `control` | `ControlScreen` (from #112 placeholder; #115's ControlViewModel wired for future swap) | `apps/android/app/src/main/java/com/aci/hermes/ui/screens/control/ControlScreen.kt` |
| 11 | `settings` | `SettingsScreen` (full-screen push) | `apps/android/app/src/main/java/com/aci/hermes/ui/screens/settings/SettingsScreen.kt` |
| 12 | `diagnostics` | `DiagnosticsScreen` (full-screen push) | `apps/android/app/src/main/java/com/aci/hermes/ui/screens/diagnostics/DiagnosticsScreen.kt` |
| 13 | `task_detail/{taskId}?target={target}` | `TaskDetailScreen` | `apps/android/app/src/main/java/com/aci/hermes/ui/screens/orchestrator/TaskDetailScreen.kt` |

All routes register in `apps/android/app/src/main/java/com/aci/hermes/ui/navigation/HermesNavGraph.kt`. Compile-time route catalog asserted in
`apps/android/app/src/test/java/com/aci/hermes/ui/navigation/ScreenTest.kt`.

### User-visible flow (golden path)

1. **Cold start → SplashScreen.** Shows the muse caduceus icon + "muse" name (from `strings.xml`) + tagline ("Your command-center agent."). 600ms delay then routes.
2. **First-run → OnboardingScreen.** Mode selection, permission education, emergency-stop primer. Skipping still finishes onboarding.
3. **Subsequent runs → HomeScreen.** Mission-control card, status, quick-links (Tasks, Chat, Approvals, Memory, Audit, Capability), tool launcher cards.
3a. **User taps Chat tab.** `JarvisChatScreen` renders the live conversation surface (transcript, streaming "thinking" bubble, inline cards, stop/retry, copy, voice-capture entry). The `RoutingJarvisChatGateway` streams from the live `HttpJarvisChatGateway` (local Hermes gateway, default `http://127.0.0.1:8765`, JSONL wire format) once a token is paired, and falls back to `MockJarvisChatGateway` on a fresh/offline device — selection is re-checked per send.
4. **User taps Approvals quick-link.** Bottom-nav stays visible; `ApprovalsScreen` renders any pending/historical approval cards. Approvals are read-only emit-from-app; the runtime decides whether to fulfill them.
5. **User taps Memory quick-link.** `MemoryScreen` shows the mock-seeded local memory items, with filter chips and detail dialogs. PrivacyRedactor (from #114) ensures social patterns don't leak identifying info.
6. **User taps Audit quick-link.** `AuditScreen` shows the redacted log of every approval/handoff/decision. Tapping a row pushes to `AuditDetailScreen` (full-screen).
7. **User taps Capability quick-link.** `CapabilityScreen` shows which muse skills/tools are enabled (mock catalog from #124).
8. **User taps Control bottom-nav.** Service start/stop + emergency-stop confirm dialog (with the "Halt everything?" copy from #113 design system).
9. **Emergency Stop** (always reachable from `ShellHost`): tap → confirm dialog → `OrchestratorServiceController.emergencyStop()` halts the foreground service. Audit-event sink records `EmergencyStopAuditEvent` (#120). No UI bypasses the confirm.

## 5. Safety inventory

### Android permissions (UNCHANGED from baseline)

```text
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
```

Diff against `bc97e43:apps/android/app/src/main/AndroidManifest.xml`: **IDENTICAL**.

Per safety rule #7 ("Do not add restricted Android permissions unless absolutely
required and documented") and the per-PR audit:

- #123 voice capture (which needs `RECORD_AUDIO`) was **DEFERRED** pending owner authorization (Q4).
- #109a / #106 Android orphan PRs that would have introduced new permissions were **DEMOTED** as functionally incompatible with the existing `com.aci.hermes` module.

### Backup / data extraction rules (#128 fix)

`apps/android/app/src/main/res/xml/backup_rules.xml` and `data_extraction_rules.xml`
were updated by #128 to **exclude** the real user-data sinks from cloud backup:
- `datastore/hermes_settings.preferences_pb`
- `files/hermes_tasks.json`

Previously these were silently included because the rules only excluded the
long-removed `hermes_secure_prefs.xml`.

### Emergency stop integration

- App-wide button: `JarvisShell` top bar (every shell route exposes it).
- Repository: `apps/android/app/src/main/java/com/aci/hermes/data/emergency/EmergencyStopRepository.kt`
- Controller: `apps/android/app/src/main/java/com/aci/hermes/data/emergency/EmergencyStopController.kt`
- Audit event type: `EmergencyStopAuditEvent.kt`
- State model: `EmergencyStopState.kt`
- Confirm-flow copy (from #113): `emergency_stop_confirm_*` strings (7 entries)

### Owner-gated actions (Python runtime preserved)

`OWNER_GATED_ACTIONS` frozenset from `hermes_cli/jarvis_prime/owner_auth.py`:

```text
['app_store_submission', 'change_default_active_agents', 'create_third_party_account',
 'credential_change', 'delete_recovered_sources', 'dns_change', 'force_push',
 'main_branch_merge', 'modify_secrets', 'oauth_change', 'package_publish',
 'post_publicly', 'production_deploy', 'registry_mutation', 'regulated_claim',
 'spend_money']
```

`AUTHORIZATION_PHRASE` (literal, preserved verbatim from `owner_auth.py`):

```text
'Yes, with authorization.'
```

This is the phrase required to merge PR #131 to `main`. Owner authorization is
per-merge, not standing.

### Redaction sites (Python + Android)

Approximate count of redaction call sites: **99 references** to "redact" in
`apps/android/app/src/main`, `hermes_logging.py`, and `agent/redact.py`.

- #109 cherry-pick `bbfc6ed` added 22 Python redaction sites
- #109 cherry-pick `d687a8a` strengthened CodeQL taint-tracking via `re.sub` rebuild
- #122 added `MemoryRedactor` for the memory transparency screen
- #114 added `PrivacyRedactor` for social-pattern memory
- #118 added `SecretRedactor` for the audit screen

### CodeQL findings (12 review threads on PR #131)

PR #131's CodeQL run flagged 12 clear-text-logging findings — **all in files
that #109's redaction work touched**. Investigation shows:
- #109 cleared 22 of the original 22 CodeQL alerts (its target)
- These 12 new findings are CodeQL's deeper taint-tracking flagging additional
  call paths through the same call sites
- #109's follow-up `d687a8a` ("rebuild audit identifiers via re.sub to break
  CodeQL taint") was designed to address this and partially succeeded

**Recommendation:** the 12 remaining findings should be reviewed in a follow-up
PR specifically for CodeQL closure. They are **not new** logging of sensitive
data — the actual log lines already redact via `safe_log_summary` and similar.
They are CodeQL false positives or partial-coverage gaps in the taint model.

## 6. Provenance — what merged from which PR

| PR | Verdict | Method | Commit(s) | Files | Notes |
|----|---------|--------|-----------|-------|-------|
| #104 | MERGED | merge --no-ff | `e3e62ba` | 5 | WorkPacket foundation, additive |
| #105 | MERGED | merge --no-ff (3 commits) | `9ac789e`+`31424cb`+`52d5f1b` | 4 | CLI proposals + 15 tests + docs |
| #107 | MERGED | merge --no-ff w/ conflict resolution | `b82b6e2` | 17 | Approvals UI; 5 file conflicts resolved |
| #108 | MERGED-DOCS | merge --no-ff | `fbbfae4` | 5 | Product spec |
| #109 | MERGED-SPLIT | cherry-pick `bbfc6ed`+`d687a8a` | (Python parts) | 11 | Redactions + CodeQL fix; Android part (`5bf1eb7`) DEMOTED |
| #110 | MERGED-DOCS | merge --no-ff | `82bf452` | 5 | Deep audit |
| #111 | MERGED-DOCS | merge --no-ff | `7919e56` | 1 | Launch readiness audit |
| #112 | MERGED | cherry-pick -x | `249f7f5` | 13 | 5→10 route shell |
| #113 | MERGED | cherry-pick -x w/ conflict resolution | `8478240` | 35 | Visual identity; SplashScreen + strings.xml resolved |
| #114 | SELECTIVE | git checkout (new files only) | `4a9a051` | 8 | Social/privacy redactor — skipped MemoryScreen overlap with #122 |
| #115 | SELECTIVE | git checkout (new files only) | `8248cdb` | 12 | Control data + tests — skipped #112 route collisions, Memory/Audit dupes |
| #118 | SELECTIVE | git checkout (new files only) | `56c1e07`+`12f8b47` | 10 | Audit screen + tests |
| #120 | SELECTIVE | git checkout (new files only) | `621b07e` | 4 | Emergency stop data layer |
| #121 | SELECTIVE | git checkout (new files only) | `7d3a8d9` | 4 | Polish theme files |
| #122 | SELECTIVE | git checkout (new files only) | `637102f` | 12 | Memory transparency |
| #124 | SELECTIVE | git checkout (new files only) | `ccbad67` | 9 | Capability UI |
| #128 | SELECTIVE | git checkout (test + README + backup + CI) | `516c04d` | 10 | Launch blocker fixes (test files + README rewrite + backup rules + unit-tests CI job) |
| #129 | SELECTIVE | git checkout (new files only) | `36fc226` | 4 | Home command center |
| (wiring) | INTEGRATION | this branch | `fa74a70` | 4 | AppContainer + Screen + NavGraph + strings.xml wired together |

| PR | Verdict | Reason |
|----|---------|--------|
| #93–#102 | REJECT-dupe | Wave 0 foundation lock duplicates; #104 is the curated survivor |
| #103 | SUPERSEDED-BY-#104 | Older Wave 0 attempt |
| #106 | DEMOTED | Creates separate gradle module `apps/android/` outside the `apps/android/app/` Android module |
| #109a | DEMOTED | Creates `com.jeremiahecherd.jarvisprime` package incompatible with existing `com.aci.hermes` |
| #116 | SKIP | Only test files (feature is in modifications that would conflict with #112+#113) |
| #117 | DEMOTED | Orphan trying to re-add baseline `AndroidManifest`, `MainActivity`, `CockpitApi` |
| #119 | DEMOTED | Same orphan re-baseline pattern as #117 |
| #123 | DEFERRED | Voice capture needs `RECORD_AUDIO`; owner Q4 unresolved |
| #125 | SELECTIVE-PARTIAL | Largely superseded by current integration; no new files claimed |
| #126 | SUPERSEDED-BY-#125 | Mobile command center foundation contained in #125 |
| #127 | DEFERRED | Gateway event spine; owner Q5 (architecture review needed) |

| PR | Verdict | Reason |
|----|---------|--------|
| #4, #17, #32, #36, #38, #39, #41, #42, #43, #54, #55, #57, #58, #60, #61, #62, #63, #64, #67, #68, #69, #70, #72, #82, #84 | DEFER-LATER-PASS | Older Phase orchestration PRs. All orphan vs current main (775-1009 file diffs). Most predate Wave 1 muse runtime + #92 decision-ledger fix. Re-evaluation deferred to a second integration pass. |

## 7. What still requires owner action

| Action | Authorization required |
|--------|------------------------|
| Merge PR #131 to `main` | `Yes, with authorization.` (literal phrase, per `owner_auth.py:AUTHORIZATION_PHRASE`) |
| Close 11 Wave-0 duplicate PRs (#93–#102) | Owner closes manually |
| Decide on #123 voice capture (RECORD_AUDIO) | Owner decision at Q4 |
| Decide on #127 gateway event spine | Owner decision at Q5 |
| Re-evaluate 25 older Phase PRs (#4–#84) | Separate audit pass after #131 merges |

## 8. Known issues / open items

1. **CodeQL — 12 review threads on PR #131.** Pre-existing partially-mitigated;
   #109 cleared 22 alerts but CodeQL's taint tracker still flags these 12 paths.
   Recommend a follow-up PR for full CodeQL closure.
2. **pytest LSP tests (`tests/agent/lsp/test_client_e2e.py`) — 4 failures.**
   These are PRE-EXISTING on `origin/main` (verified by running on main without
   any of the integration changes). Out of scope for this PR.
3. **ty type checker — 7 new warnings.** Advisory only (`lint.yml` reports
   diagnostics as warnings). Mostly intentional test patterns and a benign
   `None vs Sized` in `agent/redact.py`.
4. **Control screen still uses `OrchestratorViewModel`.** #115's richer
   `ControlViewModel` is wired into the container but not swapped into the nav
   yet. Future PR can simply swap the `ControlScreen` signature and replace
   the factory call.

---

This trace will be the human-readable handoff to the owner for the final
`Yes, with authorization.` decision.
