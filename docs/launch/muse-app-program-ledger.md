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
| **G0.2** | Tauri v2 desktop scaffold + Singularity Vite/React client + PWA | `apps/desktop/**` | `claude/muse-app-g02-desktop-scaffold` | building |
| **G0.3** | Android Compose design-system module (components + gallery + tests) | `apps/android/.../ui/designsystem/**`, `.../test/.../ui/designsystem/**` | `claude/muse-app-g03-android-ds` | building |

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
