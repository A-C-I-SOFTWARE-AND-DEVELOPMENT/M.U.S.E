# JARVIS Prime — Mobile-Native Cockpit Build: Final Report

- **Repo:** `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`
- **Working branch:** `claude/jarvis-prime-android-ZtoB7`
- **Date:** 2026-06-04
- **Companion audit:** [`JARVIS_MOBILE_NATIVE_FULL_BUILD_AUDIT.md`](./JARVIS_MOBILE_NATIVE_FULL_BUILD_AUDIT.md)
  (+ `jarvis_mobile_native_full_build_audit.json`)

## 1. Mission & outcome

Goal: finish JARVIS Prime as a mobile-first/mobile-native Android command
center for the full Hermes backend, **without reducing backend power or
duplicating existing systems**.

Outcome: the audit established this was largely a *wiring* problem, not a
building one. The cockpit API was broad and live; the gap was backend powers
the app didn't surface. Over this effort the headline gap (driving real
orchestration jobs from the phone) and the remaining read-only gaps were
closed — partly by the work below, partly by parallel sessions whose work was
re-audited against (not duplicated). The mobile-native cockpit is now
**feature-complete** against the cockpit API: jobs (dispatch/run/cancel/
pause/resume/rerun/approve/diff/validate/ledger), coding (audit/plan/execute),
research, evidence, memory tree, ledger + rollback, models/routes, autonomy,
learning, voice, approvals, emergency-stop, capabilities, diagnostics, skills,
navigation, sessions.

Every change preserved owner gates, emergency stop, the audit ledger, and the
honest "unpaired/empty/error — never fabricated" data contract.

## 2. Delivered (merged) — this session

| PR | Title | Summary |
|---|---|---|
| #214 | docs(audit) + Jobs in Tasks tab + dispatch→run coherence | Read-only end-to-end audit (md+json). Wired the real orchestration **Job Queue** into the Tasks tab: list, create runnable **orchestrator** jobs, **owner-gated Run**, cancel. Added `jobRun`, a `jobs/lanes` endpoint, and an `orchestrate` endpoint so a created job is actually runnable (fixing a JobQueue-vs-orchestrator store split + a worker-ID namespace mismatch flagged in review). Fixed a pre-existing repo-wide test red (TokenJuice truncation marker). |
| #239 | (integration) backend launch-readiness in Diagnostics | The Phase-2 Diagnostics work (`/v1/cockpit/diagnostics` surfaced as a "Backend readiness" card with honest paired/empty/error states) was integrated to `main`. |
| #244 | Navigation transparency in Job Detail | Surfaced the HyperAgent navigator's pre-dispatch "where to look" (ranked candidate files + rationale) as an on-demand section in Job Detail. Added a server-side `?job=` filter so an older job's decision isn't lost to the global recency cap (review fix). |
| #262 | Compose UI smoke tests | Added Robolectric Compose smoke tests for Diagnostics + Capability (run by `testDebugUnitTest`, no emulator). Fixed `Dispatchers.Main` test-pollution that briefly broke an unrelated test. |
| #264 | Recent sessions in Diagnostics | Surfaced `/v1/cockpit/sessions` (decision-ledger activity) as a read-only card. |

## 3. Files changed (by area, representative)

- **Android transport/models:** `data/cockpit/CockpitApi.kt`,
  `HermesCockpitClient.kt`, `CockpitJobsRepository.kt` (added `jobRun`,
  `orchestrate`, `jobLanes`, `diagnostics`, `navigation`(+`job` filter),
  `skills`, `sessions` + their wire models).
- **Android UI/VM:** `ui/screens/jobs/CockpitJobsViewModel.kt` (new) +
  `ui/screens/tasks/TasksScreen.kt` (Backend Jobs section + dispatch/run
  dialogs); `ui/screens/jobs/JobDetail{Screen,ViewModel}.kt` (navigation
  section); `ui/screens/diagnostics/Diagnostics{Screen,ViewModel}.kt`
  (backend readiness + recent sessions); `ui/screens/capability/
  Capability{Screen,ViewModel}.kt` (installed-skills section);
  `di/AppContainer.kt`, `ui/navigation/HermesNavGraph.kt` (factories/wiring);
  `res/values/strings.xml`.
- **Backend (Python, additive):** `gateway/cockpit/handlers.py` +
  `server.py` — `job_lanes`, `orchestrate_submit`, and a `?job=` filter on
  `navigation_list`. No existing handler behavior changed.
- **Tests:** `tests/gateway/test_cockpit_job_run.py` (lanes, orchestrate→run,
  navigation filter); `tests/run_agent/test_run_agent.py` +
  `test_primary_runtime_restore.py` (de-flaked two pre-existing reds);
  Android `HermesCockpitClientTest`, `CockpitJobsRepositoryTest`,
  `CockpitJobsViewModelTest`, `DiagnosticsViewModelTest`, and two Compose
  smoke tests.
- **Docs:** this report, the audit artifacts, and `docs/android/hermes-apk-cockpit.md`.

## 4. Tests run / verification

- **Backend (run locally here):** `pytest` on the cockpit suites passed —
  `test_cockpit_job_run.py`, `test_cockpit_api.py`, `test_cockpit_routing.py`,
  `test_cockpit_contract.py` (83 passing at the time of the jobs work; the
  navigation-filter and orchestrate/lanes tests pass). Endpoint shapes for
  `diagnostics`, `skills`, `sessions`, `navigation` were verified by invoking
  the handlers directly.
- **Android:** unit + Compose tests run in CI via `android-build.yml`
  (`testDebugUnitTest`, `Build debug APK`, `Lint`). **`ANDROID_HOME` is unset
  in the build environment used here**, so Android compilation/tests were
  validated by CI, not locally — every Android PR went green before merge.
- **CI loop:** three real CI issues were diagnosed and fixed during review
  (pre-existing TokenJuice truncation red; a pre-existing `sleep`-mock flake;
  Compose-test Main-dispatcher pollution), plus two correct Codex P2 review
  findings (dispatch→run store split / worker-ID mismatch; navigation recency
  cap).

## 5. Risks

| Area | Risk | Mitigation |
|---|---|---|
| Owner gate | Execute-lane runs are irreversible/external | Run requires the exact owner phrase client-side; the gateway re-checks it and refuses on a non-loopback cockpit. Never bypassed. |
| Privacy/permissions | Accessibility + overlay + query-all-packages are powerful | Unchanged by this work; flagged in the audit risk table for ongoing scrutiny. |
| Blind Android edits | No local Android compile here | Mirrored existing patterns exactly; relied on CI; fixed the one pollution failure that surfaced. |
| Fast-moving repo | Parallel sessions merging large surface | Re-audited `main` before every increment; chose only non-duplicative gaps. |

## 6. Rollback

Each increment is an isolated, additive commit/PR. To roll back any one,
revert its merge commit (e.g. `git revert -m 1 <merge-sha>` for #244/#262/
#264) — no other change depends on them, and no existing flow was modified
destructively. The backend additions (`job_lanes`, `orchestrate_submit`,
navigation `?job=`) are new routes/params; reverting them only removes the
mobile create/run-coherence path and restores prior behavior.

## 7. Deliberately out of scope (with rationale)

- **`/v1/cockpit/proposals`** — the same self-update queue the **Approvals**
  screen already manages actionably; a read-only mirror would duplicate and
  split the owner-action surface ("don't duplicate" rule).
- **`/v1/cockpit/events`** — superseded by the richer `/ledger` timeline
  already wired in the Ledger screen.
- **build → diff → validate → publish-PR** as a *new* workflow — the
  underlying client methods (`jobDiff`/`jobValidate`/`jobApprove`) and Job
  Detail controls already landed via parallel work; no separate build needed.

## 8. Follow-up tasks

1. **Instrumented/connected UI tests** for the gated Run flow (owner-phrase
   dialog) — beyond the JVM Robolectric smoke tests, when an emulator runner
   is available.
2. **Live event streaming** (`/v1/cockpit/events` SSE) for push-style job
   updates, if real-time beats the current poll/refresh.
3. **Termux intent bridge** — still a documented stub for on-phone runtime.
4. **Privacy review** of the accessibility/overlay automation surface
   (audit risk table item).
