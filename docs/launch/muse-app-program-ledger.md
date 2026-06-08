# MUSE App Program — single-writer swarm ledger

> **Single source of truth** for the "MUSE desktop (Tauri) + mobile (Android) on one
> Singularity design system" program. **Only the orchestrator** (top-level session) writes
> this file. Parallel builder grains never edit it — they each write their own snapshot at
> `docs/launch/muse-app/<grain>.md`. On resume, read this first to rebuild state.
>
> Plan of record: `/root/.claude/plans/...` (approved). Design rules: `docs/brand/muse-design-language.md`.

## Program
Apply the world-class design craft (Google Material 3, Microsoft Fluent 2, AAA/UE5-Lumen)
captured in the design-language doc to build a Tauri v2 desktop app + a Singularity web/PWA
client, and to enhance the native Android app — all over the existing gateway API. Built as a
Grainler Parallel Swarm: non-overlapping grains, one branch + worktree each from fresh `main`,
builder ≠ reviewer, validate before every PR, disjoint file ownership.

- **Base `main`:** `d22c3e4a` (PR #398 merged — banner + glyph + favicons + design-language doc).
- **Branch convention:** `claude/muse-app-<grain>`. **Merge gating:** additive/new-dir grains
  auto-merge on green; anything changing default runtime behavior or needing secrets is owner-gated.

## Status legend
`planned → building → in-review → merged` · `blocked` · `deferred`

## Wave 0 — foundation (disjoint dirs; scaffolds the shared files later waves consume)
| Grain | Scope | Owns | Branch | Status |
|---|---|---|---|---|
| **G0.1** | MUSE design system (tokens.json → tokens.css + Tokens.kt; component catalog) | `design-system/**`, append `docs/brand/muse-design-language.md` | `claude/muse-app-g01-design-system` | **merged** (#400 → `a7f2fc9f`) |
| **G0.2** | Tauri v2 desktop scaffold + Singularity Vite/React client + PWA | `apps/desktop/**` | `claude/muse-app-g02-desktop-scaffold` | **merged** (#402 → `a1d8198e`; Rust `cargo check` + Vite build both green locally) |
| **G0.3** | Android Compose design-system module (components + gallery + tests) | `apps/android/.../ui/designsystem/**`, `.../test/.../ui/designsystem/**` | `claude/muse-app-g03-android-ds` | **merged** (#401 → `d4c66c09`; needed a 1-line test-import fix; Lint/Unit tests/Build APK green) |

**Wave 0 ✅ complete — design system + desktop scaffold + Android component lib all on `main`.**

## Wave 0.5 — infra unblockers (additive; clear the path for Wave 2 CI)
| Grain | Scope | Owns | Branch | Status |
|---|---|---|---|---|
| **G0.4** | Stabilize/quarantine the flaky `AvatarPickerViewModelTest` (reddens every Android PR; main-dispatcher coroutine flake) | `apps/android/.../ui/screens/avatar/AvatarPickerViewModelTest.kt` (+ a test util if needed) | `claude/muse-app-g04-android-flake` | planned |
| **G0.5** | Rust+Node CI lane so `apps/desktop` is machine-built (npm build + `cargo check`) on every desktop PR | `.github/workflows/desktop.yml` (new) | `claude/muse-app-g05-desktop-ci` | planned |

## Wave 1 — proof slice (owner review gate; after Wave 0 merges)
| Grain | Scope | Status |
|---|---|---|
| W1-DESK | Desktop hero slice: Chat + Jobs/Approvals + live glyph over the real gateway | planned |
| W1-AND | One Android screen-group re-skinned onto the G0.3 component lib | planned |
| — | Render screenshots → **owner signs off the look** before fan-out | planned |

## Wave 2 — parallel fan-out (after Wave 1 sign-off)
| Track | Grains (one disjoint module each) | Status |
|---|---|---|
| Desktop pages | Chat · Jobs/JobDetail · Approvals/Autonomy · Memory/Evidence/Ledger · Voice · Models/Diagnostics · Settings/Pairing | planned |
| Android re-skin | home+jobs+job_detail · chat+live+avatar · memory+evidence+ledger+audit · voice+control+device_control · settings+diagnostics+model+capability · onboarding+splash+pairing+coding | planned |

## Known environment / infra notes
- Local toolchain present: node 22, npm (registry reachable), cargo/rustc 1.94, JDK 21, gradlew.
- **Tauri Linux build** needs webkit2gtk system libs (may be absent in sandbox) → Rust validated
  in CI lane; scaffold still correct.
- **Android** needs the Android SDK (absent in sandbox/CI per audit) → Kotlin self-reviewed +
  CI-gated; the unrelated flaky `AvatarPickerViewModelTest` is quarantined for re-skin grains.
- Owner gates: Tauri code-signing certs, Android Play keystore (no secrets in repo → dev builds).

## Event log
- `2026-06-08` — Program approved. `main` advanced to `d22c3e4a` via PR #398 (design foundation).
  Wave 0 launched: G0.1, G0.2, G0.3 building in isolated worktrees.
- `2026-06-08` — **G0.1 merged** (PR #400 → `main` `a7f2fc9f`): shared `design-system/` token
  source (validated, 35/35 assertions, committed `dist/` matches generator). G0.2/G0.3 still building.
- `2026-06-08` — **G0.2 merged** (PR #402 → `a1d8198e`): Tauri v2 desktop scaffold + Singularity
  Vite/React client + PWA. Validated locally — Vite build + `cargo check` (Tauri 2.11.2 tree) both green.
- `2026-06-08` — **G0.3 merged** (PR #401 → `d4c66c09`): Android Compose component library. Orchestrator
  caught + fixed a 1-line test-compile error (invalid `assertExists` import → `assertIsDisplayed`); Lint /
  Unit tests / Build debug APK all green; the lone red was the unrelated flaky `AvatarPickerViewModelTest`.
- `2026-06-08` — **Wave 0 ✅ complete.** Next: Wave 0.5 infra (G0.4 flaky-test quarantine, G0.5 desktop
  CI lane), then Wave 1 proof slice (desktop hero + one Android group) → render screenshots for owner sign-off.
