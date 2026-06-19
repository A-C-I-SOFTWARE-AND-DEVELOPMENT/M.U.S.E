# muse — final gap map (Android)

This document is the line-by-line gap list between **what is shipped
in `apps/android/`** and **what is required to call the app
"muse" without lying to the user**. Numbered by the audit
questions in `jarvis-prime-app-deep-audit.md` §24. Each row carries:

- the file or surface it lives on,
- the exact shipped state today,
- the target state for muse
- the wave it lands in (W0 cosmetic → W4 voice; see the
  [roadmap](jarvis-prime-app-finish-roadmap.md) for the full order),
- risk class (LOW / MED / HIGH).

> "Required" means required to make the cockpit a faithful muse
> Prime surface. Nice-to-haves are tagged **NTH** and are not blockers.

---

## Branding gaps (W0 — cosmetic, no behavior change)

| # | Surface | Today | Target | Wave | Risk |
|---|---|---|---|---|---|
| B-01 | `apps/android/app/src/main/res/values/strings.xml:3` | `app_name = "Hermes Agent"` | `app_name = "muse"` | W0 | LOW |
| B-02 | `strings.xml:6-7` | "Hermes Orchestrator Running" / "Hermes is coordinating your local AI workflow." | "muse — listening" / "muse is on-deck for builds and audits." | W0 | LOW |
| B-03 | `strings.xml:11,15-31` | All `orchestrator_*` strings reference "HermesService" / "Hermes" | Rephrase to "muse", retain "Local Subscription Tools" mode label since that's a Hermes-internal contract | W0 | LOW |
| B-04 | `SplashScreen.kt:46` | `Text("Hermes Agent")` | `Text("muse")` | W0 | LOW |
| B-05 | `SplashScreen.kt:41` | Caduceus glyph `☤` | muse mark (new vector) | W0 | LOW |
| B-06 | `apps/android/app/src/main/res/values/themes.xml:3` | `Theme.HermesAgent` style name | `Theme.JarvisPrime` (manifest references update in lockstep) | W0 | LOW |
| B-07 | `apps/android/app/src/main/res/drawable/ic_launcher_foreground.xml` | Caduceus glyph + Hermes Agent comment | New muse mark; comment updated | W0 | LOW |
| B-08 | `apps/android/settings.gradle.kts:23` | `rootProject.name = "HermesAgent"` | `rootProject.name = "JarvisPrime"` (CI cache key changes — accept one cold build) | W0 | LOW |
| B-09 | `apps/android/README.md` (whole file) | Describes a network-client app that doesn't exist | Rewrite from scratch as muse cockpit README | W0 | LOW |
| B-10 | `apps/android/docs/ARCHITECTURE.md` (whole file) | Describes the same stale network architecture | Rewrite as the muse architecture doc; cross-link to `docs/jarvis-prime-operating-system.md` | W0 | LOW |
| B-11 | `OrchestratorScreen.kt:194` | "Mode" row literal `"Local Subscription Tools"` | Replace with "muse · Operator" by default; switch on mode (see C-01) | W2 | LOW |
| B-12 | Strings safety banner (`orchestrator_safety_body`) | "Hermes does not bypass OpenAI or Anthropic." | "muse never bypasses provider authentication and only acts after explicit owner authorization." | W0 | LOW |
| B-13 | Channel display name (`HermesService.kt:124`) | `"Hermes Orchestrator"` | `"muse"` (channel **id** stays — see C-04) | W0 | LOW |
| B-14 | Notification channel description (`HermesService.kt:152`) | "Persistent indicator that Hermes is coordinating local AI workflows." | "Persistent indicator that muse is on-deck." | W0 | LOW |
| B-15 | Color palette names (`Color.kt`) | `HermesGold`, `HermesInk`, … | Rename to `JarvisGold`, `JarvisInk`, … in same wave as B-06 | W0 | LOW |

## Doc-vs-code drift gaps (W0 — must resolve before Wave 1)

| # | Surface | Today | Target | Wave | Risk |
|---|---|---|---|---|---|
| D-01 | `apps/android/README.md:268-274` ("What's not wired up yet") | Lists push-from-gateway, skill picker, voice, release signing, HTTPS-only | Replace with the live muse gap list once W0 lands | W0 | LOW |
| D-02 | `apps/android/README.md:252-261` (Screens table) | Lists splash / setup / provider / chat / status / settings / diagnostics | Replace with the actual route list (splash / orchestrator / task_detail / settings / diagnostics) | W0 | LOW |
| D-03 | `gradle.properties:14-32` (gateway URL docstring) | Documents `DEFAULT_GATEWAY_URL` BuildConfig field | `build.gradle.kts` doesn't define that field — either remove the docstring or add the field in W1 when the gateway client lands | W0 then W1 | MED |
| D-04 | `apps/android/app/src/main/res/xml/backup_rules.xml`, `data_extraction_rules.xml` | Excludes `hermes_secure_prefs.xml` from backup/transfer | The file no longer exists in code. Keep the exclusion (forward compat, harmless) OR remove it if W1 brings the gateway-token store back at a new path | W0 / W1 | LOW |
| D-05 | `ARCHITECTURE.md` `Wire format` section | Describes `/v1/health`, `/v1/chat` SSE | Move to the W1 muse cockpit gateway-client doc; remove from this file | W1 | MED |
| D-06 | `data/cockpit/CockpitApi.kt` header comment | "Phase 18 cockpit API contract — Kotlin mirror." | Either land the W1 client that consumes these types or delete the file. Currently dead surface area. | W1 | MED |
| D-07 | `data/termux/TermuxIntentBridge.kt` header | Labels itself a "stub" | Land the W1 fire path and remove the stub label, or delete the class. Currently dead surface area. | W1 | MED |
| D-08 | `apps/android/README.md:283-332` ("Service intent contract") | Documents `com.aci.hermes.action.STOP_ORCHESTRATOR` + observational extras | Keep verbatim — this is an external contract for Termux integration | KEEP | LOW |

## Connection / cockpit gaps (W1 — muse gateway client)

| # | Surface | Today | Target | Wave | Risk |
|---|---|---|---|---|---|
| C-01 | (new) `data/network/JarvisGatewayClient.kt` | Does not exist | OkHttp + OkHttp-SSE based client implementing the `CockpitApi` types | W1 | MED |
| C-02 | (new) `data/network/JarvisHealthProbe.kt` | Does not exist | 5 s connect / 8 s call probe; surfaces ConnectionState | W1 | MED |
| C-03 | Manifest | No `INTERNET`, no `ACCESS_NETWORK_STATE` | Add both, narrowly justified | W1 | MED |
| C-04 | `HermesService.CHANNEL_ID = "hermes_orchestrator"` | Channel id is `hermes_orchestrator` | **Keep** the id. Migration: only rename the user-visible name. Renaming the id orphans user-customized importance | W0 KEEP | LOW |
| C-05 | `build.gradle.kts` | No `buildConfigField` for `DEFAULT_GATEWAY_URL` | Add the field; resolve from `hermesGatewayUrl` Gradle property → `$HERMES_GATEWAY_URL` → `$ANDROID_API_BASE_URL` → debug `http://10.0.2.2:8080` → release `""` | W1 | MED |
| C-06 | (new) `data/preferences/SecureGatewayPrefs.kt` | Does not exist (removed) | Reintroduce `EncryptedSharedPreferences` for the gateway bearer token only | W1 | MED |
| C-07 | `data/termux/TermuxIntentBridge.kt` | Build-only stub | Add `fireHermesIntent`, permission probe, result handling; gate on `<queries>` declaration | W1 | MED |
| C-08 | Manifest `<queries>` block | Absent | Add `<package android:name="com.termux" />` and `com.termux.files` so `getLaunchIntentForPackage` returns non-null on Android 11+ | W1 | LOW |
| C-09 | (new) `ui/screens/cockpit/CockpitScreen.kt` | Does not exist | Job list + dispatch + worker picker; reads `/v1/cockpit/jobs` | W1 | MED |
| C-10 | (new) `ui/screens/cockpit/JobDetailScreen.kt` | Does not exist | Diff + validation gates + approve / deny | W1 | MED |
| C-11 | `ARCHITECTURE.md` updates | Stale | Document the live wire format + retry/backoff + offline cache policy | W1 | LOW |

## Local-orchestrator continuity (preserve — do not break)

| # | Surface | Today | Target | Wave | Risk |
|---|---|---|---|---|---|
| L-01 | `HermesTaskRepository` (file: `hermes_tasks.json`) | Working JSON envelope | **Keep**. Bump envelope version when (and only when) a field migration lands | KEEP | LOW |
| L-02 | `DataStore name = "hermes_settings"` | Working | **Keep**. User prefs migrate cleanly across rebrand | KEEP | LOW |
| L-03 | `HermesTask` schema | 7 types, 7 statuses, 5 targets | Add (without breaking existing JSON envelopes): `prUrl`, `commitSha`, `evidence: List<EvidenceRef>`, `parentTaskId`. All optional. | W2 | LOW |
| L-04 | `HermesRole.kt` | 5 labels | Map onto the six muse modes; rename to `JarvisRole`; keep `displayName` strings for tasks already serialized | W2 | LOW |
| L-05 | `PromptBuilder.SAFETY_BLOCK` | Already invariant across targets | **Keep verbatim**. The muse safety addendum stacks on top, not replaces. | KEEP | LOW |
| L-06 | `HandoffLauncher.openOfficialTool` | Two-step (package → web fallback) | **Keep**. Add a third step: if `allowExternal` is false **and** a gateway is configured, post the prompt to the gateway as a worker job instead of the clipboard. | W1 | MED |
| L-07 | `OrchestratorViewModel.isServiceRunning` | Uses deprecated `ActivityManager.getRunningServices` | Replace with a `ServiceConnection` + bound-service probe **or** a `MutableStateFlow` the service updates from `onCreate`/`onDestroy`. The deprecated API still works for self-services, so this is a polish item. | W3 | LOW |

## Approval gaps (W2 — muse gate UI)

| # | Surface | Today | Target | Wave | Risk |
|---|---|---|---|---|---|
| A-01 | `ui/navigation/Screen.kt` | No Approvals route | `Approvals : Screen("approvals")` and `ApprovalDetail : Screen("approvals/{id}")` | W2 | MED |
| A-02 | (new) `ApprovalsScreen.kt`, `ApprovalDetailScreen.kt` | Don't exist | List `PendingApproval` items; render kind, summary, expires-at; *Approve* / *Deny* / *Defer* actions | W2 | MED |
| A-03 | (new) `OwnerAuthorizationDialog.kt` | Doesn't exist | Captures the exact phrase `Yes, with authorization.` (no partial match); mirrors `hermes_cli/jarvis_prime/owner_auth.py:AUTHORIZATION_PHRASE` | W2 | MED |
| A-04 | Notification | One channel, one notification, one action (*Stop*) | Per-approval high-priority notification on a separate `jarvis_approvals` channel with *Approve* / *Defer* actions (deny is intentionally not a notification action — too easy to mis-tap) | W2 | MED |
| A-05 | Driving-mode gate | None | Suppress high-risk approval notifications while driving mode is on; queue to next focused-mode launch (`docs/voice/driving-mode-safety.md`) | W4 | MED |
| A-06 | `SettingsRepository` | No `ownerAuthorized` ledger | Add a short-lived in-memory cache (not persisted) for the authorization phrase so reload behavior matches the runtime | W2 | LOW |

## Memory transparency gaps (W2)

| # | Surface | Today | Target | Wave | Risk |
|---|---|---|---|---|---|
| M-01 | `ui/navigation/Screen.kt` | No Memory route | `Memory : Screen("memory")` | W2 | LOW |
| M-02 | (new) `MemoryScreen.kt` | Doesn't exist | List `MemoryRecord` items grouped by kind (decisions / preferences / lessons / goals) with source + created-at + expires-at | W2 | MED |
| M-03 | (new) `data/memory/MemoryClient.kt` | Doesn't exist | Reads from the gateway (`/v1/cockpit/memory`) when reachable; local-only mode shows a graceful empty state | W2 | MED |
| M-04 | Forget affordance | None | Soft delete with confirmation; mirrors the Python runtime's "forget" verb | W2 | LOW |
| M-05 | Save affordance | None | Long-press on a task → "Save this as durable memory" with a kind picker | W2 | LOW |
| M-06 | Memory rules visibility | None | Static card on Memory screen header listing what *will not* be saved (per `docs/jarvis-prime-operating-system.md` §Memory Rules) | W2 | LOW |

## Audit / proof gaps (W2)

| # | Surface | Today | Target | Wave | Risk |
|---|---|---|---|---|---|
| P-01 | (new) `GatesPanel.kt` Composable | Doesn't exist | Visualizes the eight muse gates (Planning / Build / Review / Test / Security / Release / Owner Approval / Rollback) — mirrors `GateSummary` | W2 | MED |
| P-02 | Job detail screen | Doesn't exist | Carries diff, files-changed, validation summary, PR url, gate panel, decision ledger excerpt | W1 (skeleton) / W2 (gates) | MED |
| P-03 | Evidence list per task | None | A per-task list of `EvidenceRef { kind: TEST_RUN \| DIFF \| LOG \| PR, url: String?, summary: String }`; persisted in `HermesTask` (see L-03) | W2 | LOW |
| P-04 | Decision ledger reader | None | Read-only view of the gateway's ledger excerpt for a job; copy-as-markdown action | W2 | LOW |
| P-05 | Proof export | None | NTH — share-sheet export of the audit pack (markdown + diff + ledger excerpt) | NTH | LOW |

## Interactive icon gaps (W3)

| # | Surface | Today | Target | Wave | Risk |
|---|---|---|---|---|---|
| I-01 | App shortcuts | None | Three static shortcuts: *Dispatch job*, *Approvals*, *Voice capture* | W3 | LOW |
| I-02 | Quick settings tile | None | NTH — *Driving mode* toggle tile | NTH | LOW |
| I-03 | Home screen widget | None | NTH — *Pending approvals* count widget | NTH | LOW |
| I-04 | Notification actions | *Stop* only | Per-job notification with *Open*, *Approve*, *Defer*; per-approval channel | W2 | MED |
| I-05 | Notification updates | None | Foreground notification text changes with mode (Operator / Companion / Mobile Voice / Driving) | W3 | LOW |
| I-06 | App icon | Caduceus | muse mark + monochrome adaptive icon | W0 | LOW |
| I-07 | Badging | Off | Optional badge when pending approvals exist (still off by default) | W3 | LOW |

## Voice gaps (W4 — last wave, opt-in only)

| # | Surface | Today | Target | Wave | Risk |
|---|---|---|---|---|---|
| V-01 | Manifest | No `RECORD_AUDIO` | Add `RECORD_AUDIO`; lazy-requested when the user enables voice; never requested on startup | W4 | MED |
| V-02 | Manifest | `foregroundServiceType="dataSync"` | Add `microphone` to the type bitmask (`dataSync\|microphone`) while voice capture is active; the service flips type at runtime | W4 | MED |
| V-03 | (new) `data/voice/VoiceRecorder.kt` | Doesn't exist | `AudioRecord` wrapper; cold `Flow<ByteArray>` of PCM frames at 16 kHz mono per `docs/mobile/app-voice-service.md` | W4 | MED |
| V-04 | (new) `data/voice/VoicePlayer.kt` | Doesn't exist | `AudioTrack` consumer for TTS readback | W4 | LOW |
| V-05 | (new) `ui/screens/voice/VoiceIntakeScreen.kt` | Doesn't exist | Push-to-talk button + transcript readout + "send to gateway" action | W4 | MED |
| V-06 | Driving mode toggle | None | `SettingsRepository.drivingMode` + a top-bar toggle in Voice Intake; auto-defers high-risk approval notifications (A-05) | W4 | MED |
| V-07 | Voice mode awareness in ViewModels | None | Mode-aware persona selection: `Persona.DEFAULT_FORMAT` (default), `OPERATOR_FORMAT` (cockpit job dispatch), `MOBILE_VOICE_FORMAT` (driving / walking) | W4 | LOW |

## Mode / persona gaps (W2 — visible in UI, W3 — gating)

| # | Surface | Today | Target | Wave | Risk |
|---|---|---|---|---|---|
| O-01 | Settings screen | No mode picker | Six-radio picker: Companion / Strategy / Critic / Operator / Builder / Mobile Voice | W2 | LOW |
| O-02 | Top bar | No mode indicator | Small chip showing the active mode; tap → mode settings | W2 | LOW |
| O-03 | Persona prompt | Not surfaced | The Persona builder from `hermes_cli/jarvis_prime/persona.py` is unused; the cockpit must request mode-specific persona text from the gateway and pass it on dispatch | W2 | MED |
| O-04 | Awareness snapshot | Not surfaced | A small "what muse is currently watching" card on Orchestrator (gateway state, last job status, memory load) reading `AwarenessSnapshot` | W3 | LOW |

## Permission gaps already prevented (must stay absent)

The permissions in [`jarvis-prime-app-permission-risk-register.md`](jarvis-prime-app-permission-risk-register.md)
must remain undeclared. Reviewers should reject any PR that adds them
without an explicit user-flow justification and an updated permission
register entry.

---

## Cross-references

- Audit body: [`jarvis-prime-app-deep-audit.md`](jarvis-prime-app-deep-audit.md)
- Build order: [`jarvis-prime-app-finish-roadmap.md`](jarvis-prime-app-finish-roadmap.md)
- Permissions: [`jarvis-prime-app-permission-risk-register.md`](jarvis-prime-app-permission-risk-register.md)
- Python ↔ Android mapping: [`jarvis-prime-app-research-translation-map.md`](jarvis-prime-app-research-translation-map.md)
- Source-of-truth runtime: `hermes_cli/jarvis_prime/`
- Apex persona spec: [`jarvis-prime-operating-system.md`](jarvis-prime-operating-system.md)
- Skill: [`/skills/jarvis-prime/SKILL.md`](../skills/jarvis-prime/SKILL.md)
- Existing APK API contract: [`docs/android/hermes-apk-api-contract.md`](android/hermes-apk-api-contract.md)
- Existing cockpit spec: [`docs/android/hermes-apk-cockpit.md`](android/hermes-apk-cockpit.md)
