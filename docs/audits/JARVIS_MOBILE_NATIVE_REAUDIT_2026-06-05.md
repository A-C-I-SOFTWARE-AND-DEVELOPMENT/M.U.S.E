# JARVIS Prime — Mobile-Native Cockpit Re-Audit (2026-06-05)

- **Repo:** `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`
- **Base branch audited:** `main` @ `313e21f` (#336), plus the two in-flight
  device-control PRs **#324** / **#325** where noted.
- **Generated:** 2026-06-05
- **Method:** Read-only static inspection (four parallel evidence sweeps:
  mobile wiring, cockpit routes, testing/CI/security, device-control safety),
  cross-checked against git history. Lightweight validation only; **no
  functional code edited** — the only writes are this file and its JSON mirror.
- **Supersedes:** [`JARVIS_MOBILE_NATIVE_FULL_BUILD_AUDIT.md`](./JARVIS_MOBILE_NATIVE_FULL_BUILD_AUDIT.md)
  (2026-06-03) and its [`.json`](./jarvis_mobile_native_full_build_audit.json).
- **Machine-readable mirror:** [`jarvis_mobile_native_reaudit_2026-06-05.json`](./jarvis_mobile_native_reaudit_2026-06-05.json)

---

## 1. Executive summary

**The June-3 audit's headline conclusion — "this is a *wiring* problem, not a
*building* problem" — has been acted on, and the wiring is now substantially
done.** The biggest gap (driving real orchestration jobs from the phone) and
the read-only surfaces (diagnostics, sessions, navigation, skills, models,
research/evidence, memory tree, ledger + rollback, autonomy, learning) are all
now consumed by real screens.

What changed since 2026-06-03:

- **Cockpit API grew from ~25 routes to 90** (`gateway/cockpit/server.py:47–155`),
  all additive, owner gates intact.
- **Every High/Medium "built-but-not-wired" item from the last audit is now
  WIRED.** The generic `getRaw` passthrough is no longer used by any screen —
  every endpoint has a typed accessor.
- **Device pairing (#319)** landed as a reachable screen + nav route + Settings
  entry.
- **Device-control safety hardening (#4 / #5)** is implemented and locally
  unit-verified on open PRs **#324** (non-disableable `IRREVERSIBLE`
  confirmation floor) and **#325** (emergency-stop unification) — **not yet
  merged to `main`**.
- **The Android Main-dispatcher unit-test flake** got a structural fix in
  **#336** (status: *applied, awaiting CI confirmation*).

The work is no longer "finish the cockpit." The remaining items are
**hardening, dependency hygiene, and on-device verification**:

1. **(NEW, High) 26 Dependabot vulnerabilities (7 high, 19 moderate)** on the
   default branch — the single most important new finding.
2. **(In-flight, High) Land #324/#325** and run the device-control emergency /
   irreversible-action flows on a real device/emulator (the one gap their PRs
   explicitly call out).
3. **(Medium) Confirm the #336 flake fix** with repeated green CI runs, and add
   instrumented (`androidTest`) coverage for the gated flows.

**Bottom line:** the mobile-native cockpit is feature-complete against the
cockpit API and preserves every owner gate. Ship-readiness now hinges on
dependency patching, merging the safety hardening, and on-device test proof —
not on building new surfaces.

---

## 2. State delta since 2026-06-03

| Area | June 3 | June 5 | Evidence |
|---|---|---|---|
| Orchestration Job Queue on mobile | **UNWIRED (High)** | **WIRED** — list/dispatch/run/cancel/pause/resume/rerun/approve/diff/validate | `HermesCockpitClient.kt:432–687`, `CockpitJobsRepository.kt:24–150`, `ui/screens/jobs/*`, `TasksScreen.kt`; owner gate `CockpitJobsRepository.kt:136–143` |
| Backend diagnostics | UNWIRED | **WIRED** | `DiagnosticsViewModel.kt:36–80` |
| Sessions | UNWIRED | **WIRED** | `DiagnosticsViewModel.kt:72–75` |
| Navigation (HyperAgent, `?job=`) | UNWIRED | **WIRED** | `JobDetailViewModel.kt:149–162` |
| Capability ↔ installed skills | drift risk | **WIRED** (skills section) | `CapabilityViewModel.kt:68–84` |
| Models / scorecards | UNWIRED | **WIRED** (routes/center) | `ui/screens/modelroute/*`, `ModelCenter*` |
| Research Vault / evidence | backend-only | **WIRED** | `HermesCockpitClient.kt:393–821`, `ui/screens/research/*`, `evidence_*` routes |
| Ledger replay / rollback | backend-only | **WIRED** (timeline + rollback) | `HermesCockpitClient.kt:401–429`, `ui/screens/ledger/*` |
| Autonomy / TokenJuice grants | backend-only | **WIRED** (controls) | `HermesCockpitClient.kt:607–646`, `ControlScreen.kt:164` |
| Learning queue | n/a | **WIRED** | `HermesCockpitClient.kt:293–312` |
| Device pairing | n/a | **WIRED (#319)** | `ui/screens/pairing/*`, `Screen.Pairing`, `SettingsScreen.kt:160` |
| `getRaw` passthrough | used in 1 test | **unused** (typed accessors everywhere) | `HermesCockpitClient.kt:101–102` |
| Cockpit routes | ~25 | **90** | `server.py:47–155` |
| Device-control sensitivity | binary; confirm disableable | **`IRREVERSIBLE` floor** (PR #324, not on main) | `DeviceActionPacket.kt`, `DeviceActionBroker.kt` on #324 |
| Device-control emergency halt | local writable flag + unguarded release | **projection of audited global stop** (PR #325, not on main) | #325 |
| Android unit-test flake | open | **fix applied (#336), awaiting CI** | `docs/testing/known-flaky-tests.md:12` |

---

## 3. Architecture map (updated)

Three distinct HTTP surfaces now exist — **keep them distinct; do not merge or
duplicate**:

| Surface | Location | Audience | Notes |
|---|---|---|---|
| **Cockpit API** | `gateway/cockpit/{server,handlers,contract,auth}.py` | **the mobile app** | 90 routes, loopback-only default, bearer-token-only. The phone's single backend. |
| Orchestrator API | `hermes_cli/orchestrator_api.py` | backend/CLI | FastAPI; hosts `GET /jobs/{id}/snapshot` (replay rebuild, PR #317) — **not** exposed to mobile. |
| Desktop web UI | `hermes_cli/web_server.py` | desktop | Separate FastAPI `/api/*`. |

Android cockpit: Kotlin/Compose, single `NavHost`
(`ui/navigation/HermesNavGraph.kt`), **32 route objects** in `Screen.kt`
(26 composable blocks; the rest via shell destinations), hand-rolled DI in
`di/AppContainer.kt`, typed transport in `data/cockpit/HermesCockpitClient.kt`.

---

## 4. Mobile app — current state

**Wired live to the cockpit (verdict: WIRED, with consuming VM):** Jobs (full
lifecycle), Diagnostics (+ backend readiness, recent sessions), Job Detail
(+ navigation transparency), Capability (+ installed skills), Models
(routes + center), Research/Evidence, Memory + Memory Tree, Ledger timeline +
rollback, Autonomy, Learning, Approvals (owner phrase), Chat (SSE),
Avatar/persona/room, Voice, Device pairing.

**Deliberately local / not backend-backed (by design):** the
clipboard-handoff task flow (`HermesTaskRepository` + `OrchestratorViewModel`)
is preserved alongside the backend Job Queue.

**Still UNWIRED (low; intentional):**

| Capability | Why it's acceptable | Evidence |
|---|---|---|
| `/v1/cockpit/events` stream | superseded by the richer wired **Ledger timeline** | no `EventsViewModel`/route |
| `/v1/cockpit/proposals` | overlaps the actionable **Approvals** screen | no `ProposalsViewModel`/route |

**Harmless leftovers:** `PlaceholderScreen.kt` exists but is unreferenced in the
nav graph (it now has a Robolectric smoke test only).

---

## 5. Backend — current state

- **90 routes** in `server.py:47–155`. New since June 3 (all additive, no
  existing handler behavior changed): `jobs/lanes` (`handlers.py:1052`),
  `orchestrate` (`handlers.py:1077`), `voice/transcribe` + `voice/responses`
  (Sprint 8), plus the broad evidence / memory-tree / ledger / autonomy /
  learning / templates / graph families.
- **Owner gates — verified intact:**
  - `job_run` is **double-gated**: exact owner phrase **and** loopback-only
    refusal when bound externally (`handlers.py:3239–3259`; phrase constant
    `"Yes, with authorization."` at `hermes_cli/jarvis_prime/owner_auth.py:20`).
  - `approvals_decide` approve requires the exact owner phrase
    (`handlers.py:2661–2680`).
- **Loopback-only by default** (`server.py:456–480`, default host `127.0.0.1`);
  **bearer-token-only**, token stored 0600, **no provider secrets in request
  bodies** (the models route explicitly rejects API keys, `handlers.py:144`).
- **Backend-only (no cockpit route — acceptable, low):** TokenJuice budget,
  model scorecards (`scoring.py`), orchestrator-API replay snapshot. Mobile
  reaches replay via the wired Ledger timeline + rollback instead.

---

## 6. Resolved since the last audit

- **§5 "Already-built-but-not-wired" (the whole table): closed.** Every High/
  Medium item is now consumed by a screen.
- **§7 "Two task mental models" confusion: addressed** — the backend Job Queue
  is now visible on the phone (Jobs + Tasks), so dispatched backend work is no
  longer invisible.
- **§7 "Capability catalog drift": addressed** — installed skills now surfaced.
- **§7 "Diagnostics shows local logs only": addressed** — backend readiness +
  sessions surfaced.
- **§10 Job Queue UI/VM coverage gap: addressed** — `CockpitJobsViewModelTest`,
  `JobDetailViewModelTest`, etc. exist.

---

## 7. Open findings & risk table (ranked)

| # | Area | Severity | Issue | Evidence | Mitigation / action |
|---|---|---|---|---|---|
| 1 | **Dependencies** | **High (NEW)** | 26 Dependabot vulnerabilities (7 high, 19 moderate) on default branch | push-time GitHub alert; manifests `pyproject.toml`, `apps/android/gradle/libs.versions.toml`, `app/build.gradle.kts`; OSV-scanner is **detection-only**, `fail-on-vuln` disabled (`.github/workflows/osv-scanner.yml`) | Triage the 7 high first; bump pins; let OSV/Dependabot re-scan. Owner-gated if any bump is a major. |
| 2 | **Device-control safety** | **High (in-flight)** | On `main` today, sensitivity is still binary + confirmation disableable, and the device halt is a local writable flag with an **unguarded** `releaseEmergencyStop()` that can diverge from the audited global stop | `DeviceControlController.kt:60,102,146` on `main` | **Merge #324 + #325** (both locally unit-verified). Fix is done; it just isn't on `main` yet. |
| 3 | **On-device testing** | **Medium** | No instrumented (`androidTest`) suite — only 124 JVM/Robolectric tests + 3 Compose smoke tests. The gated **Run** flow and the device-control **emergency / irreversible** flows have no on-device proof | no `app/src/androidTest`; #324/#325 PRs both flag pending emulator smoke | Add a connected test runner; smoke the owner-phrase Run dialog + emergency stop/resume + IRREVERSIBLE confirm on a device. |
| 4 | **Test reliability** | **Medium** | Android Main-dispatcher flake fix is **applied but unconfirmed** (~1-in-N) | `docs/testing/known-flaky-tests.md:12`; #336 | Re-run the Android JVM unit CI job several times; mark closed only after sustained green. |
| 5 | **Privacy / permissions** | **Medium** | Accessibility (can read window content) + overlay + query-all-packages is a powerful automation surface | `AndroidManifest.xml`, `res/xml/jarvis_accessibility.xml` | **Already mitigated:** every action goes through the pure broker; captured node content is **on-demand and never persisted** (`JarvisAccessibilityService.kt:47,68–95`); `PrivacyRedactor` + `SecretRedactor` run at write **and** render time; the ledger stores only labels/outcomes. **Remaining:** a formal pre-Play privacy review of the automation surface. |
| 6 | **Duplication risk** | **Low** | Three HTTP surfaces (cockpit / orchestrator-API / web_server) | §3 | Keep the cockpit as the mobile surface; don't build a fourth. The local handoff task flow is intentionally preserved. |
| 7 | **Backend-only powers** | **Low** | TokenJuice budget, model scorecards, raw replay snapshot have no cockpit route | §5 | Add read-only cockpit routes only if a concrete mobile need appears; otherwise leave backend-only. |

---

## 8. Recommended sequence (post-wiring)

1. **Patch dependencies (Finding 1).** Triage the 7 high Dependabot alerts;
   bump `pyproject.toml` + Gradle pins; re-scan. Highest value, lowest product
   risk.
2. **Merge the safety hardening (Finding 2).** Land #324 then #325 (stacked);
   retarget #325 to `main` after #324.
3. **On-device verification (Findings 3 + 4).** Stand up a connected/emulator
   test job; smoke the gated Run, emergency stop/resume, and IRREVERSIBLE
   confirm; confirm the #336 flake fix over repeated runs.
4. **Pre-Play privacy review (Finding 5).** Document data handling for the
   accessibility/overlay surface; confirm redactor coverage end-to-end.
5. **Defer** events-stream/proposals wiring and backend-only route exposure
   until a concrete need exists (avoid duplication).

---

## 9. Do-not-overwrite list (refreshed)

- `gateway/cockpit/contract.py` — canonical schema source of truth.
- `gateway/cockpit/{server,handlers,auth}.py` route table + owner gates — the
  live, double-gated API.
- `hermes_cli/jarvis_prime/owner_auth.py` `AUTHORIZATION_PHRASE` — the owner gate.
- `apps/android/.../data/cockpit/CockpitApi.kt` / `HermesCockpitClient.kt` — wire
  mirror; keep in lockstep with the contract.
- `apps/android/.../data/orchestrator/HermesTaskRepository.kt` +
  `OrchestratorViewModel` — the local handoff flow must stay.
- `apps/android/.../data/devicecontrol/DeviceActionBroker.kt` — the pure
  single-chokepoint; never add a bypass.
- `apps/android/.../data/emergency/EmergencyStopController.kt` — replay-protected
  audited resume; never add an unguarded release.
- Decision-ledger files + `hermes_cli/decision_ledger.py` — never silently
  rewrite entries.
- `SettingsRepository` `EncryptedSharedPreferences` token storage path.

## 10. Extend-rather-than-replace list (refreshed)

| Target | Why |
|---|---|
| `apps/android/gradle/libs.versions.toml` + `pyproject.toml` | Patch dependency pins in place (Finding 1) — don't restructure the build. |
| `MainDispatcherRule` (test util) | The #336 fix lives here; extend the same register/clear pattern for any new ViewModel test rather than re-introducing manual `setMain/resetMain`. |
| `gateway/cockpit/handlers.py` + `contract.py` | Add any new read routes (e.g. scorecards) via the existing adapter pattern; don't fork the surface. |
| `ui/screens/diagnostics/*` | If events streaming is ever needed, augment here rather than adding a new tab. |

---

*This re-audit changed no functional code. The only writes are this file and
its JSON mirror under `docs/audits/`. The device-control safety verdicts for
findings #4/#5 describe the state on PRs #324/#325; on `main` those fixes are
pending merge.*
