# FU-17b: Distinct on-brand colors for the avatar attention states

- **Status:** in-review (draft PR)
- **Risk class:** behavior-change (visual only) — color tokens + state mapping
- **Branch:** `claude/fu-17b-attention-colors` · **Base:** `main` @ `3af96285`
- **PR:** #<n> (draft)
- **Owner-gate required to merge?** no — strictly additive visual fix on an
  unreleased surface, no logic/API change. Auto-merge once CI is green.

## Intent (one paragraph)

FU-17 (already on `main`) re-pointed the avatar's private `JarvisPalette`
values to the Singularity palette and, in doing so, mapped the old gold to
white (`Gold = 0xFFFFFFFF`). That killed gold at rest (correct) but had a side
effect: `WAITING_FOR_APPROVAL` and `SERIOUS_ACTION_PENDING` both became
**white core + white ring** — visually **identical to each other** and nearly
identical to `IDLE` (white core + cyan ring). Two distinct attention states
became indistinguishable, a design regression. FU-17b restores a coherent
**Singularity attention-escalation ramp** in which every at-rest/attention
state is visually distinct, still with **no gold at rest**:

| State | Before (FU-17) | After (FU-17b) |
|---|---|---|
| `IDLE` | white core + cyan ring | white core + **cyan** ring (unchanged) |
| `WAITING_FOR_APPROVAL` | white core + **white** ring | white core + **violet** ring |
| `SERIOUS_ACTION_PENDING` | **white** core + white ring | **violet** core + **violet** ring |
| `CRITICAL_ACTION_PENDING` | red core + red ring | red core + red ring (unchanged) |

The ramp reads as calm → needs-you → heightened → danger:
cyan (`--ring-1`) → violet (`--ring-2`) ring, then violet pulled into the core,
then red. SERIOUS also keeps its stronger pulse (0.9) and a heavier violet halo
(alpha 0.45 vs WAITING's 0.30), reinforcing the escalation beyond color alone.

### Chosen SERIOUS treatment

SERIOUS = **violet core + violet ring** (`JarvisPalette.Violet` = `0xFFB388FF`
= `--ring-2`). Rationale: it reuses an existing Singularity hex (no new token),
is unambiguously heightened versus WAITING (which keeps the white core), stays
clearly apart from the red CRITICAL state, and pairs with the existing stronger
pulse/halo so the difference is legible even to color-vision-deficient users.

## Owned files (the ONLY files this task may write)

- `apps/android/app/src/main/java/com/aci/hermes/ui/jarvis/JarvisIconColors.kt`
  (state→appearance mapping for the two attention states; one palette comment)
- `apps/android/app/src/test/java/com/aci/hermes/ui/jarvis/IconColorsTest.kt`
  (new assertions for the ramp; FU-17's "no gold at rest" guarantee preserved)
- `apps/android/app/src/test/java/com/aci/hermes/ui/jarvis/IconStateAccessibilityTest.kt`
  (updated the `approval ring uses gold` assertion to the new violet
  assignment so the suite stays self-consistent; kept its distinctness intent)
- `docs/launch/followups/fu-17b-attention-colors.md` (this snapshot)

> Disjoint from every other in-flight task. No shared writable file discovered.

## What changed (color tokens + state mapping only)

`JarvisIconColors.kt`:
- `WAITING_FOR_APPROVAL`: `ringColor`/`haloColor` `Gold` → `Violet` (core stays
  `Core` = white).
- `SERIOUS_ACTION_PENDING`: `coreColor`/`ringColor`/`haloColor` `Gold` →
  `Violet`.
- Pulse amplitudes, `dim`, and the `IconAppearance` structure are untouched.
- One comment on `JarvisPalette.Violet` now notes its approval/serious role; a
  block comment documents the ramp. No new tokens; no hex literals beyond the
  ones already in the palette.

No logic, no API, no new `IconState`, no renderer change — `appearanceFor` is
the single source of truth and remains the only consumer.

## Tests

`IconColorsTest` (existing, owned) — added:
1. `waiting for approval renders white core and violet ring`.
2. `serious action pending renders violet core and violet ring`.
3. `idle, waiting and serious are mutually distinct` — each `(core, ring)` pair
   differs from the others, so none can collapse again.
FU-17's "no gold-era literal at rest" tests are kept verbatim.

`IconStateAccessibilityTest` (existing, owned) — updated:
- Renamed `approval ring uses gold` → `approval ring uses violet`; now asserts
  both approval states use `JarvisPalette.Violet` (the rename is required —
  after FU-17 `Gold` is white, and FU-17b moves the ring to violet, so the old
  assertion would fail).
- Added `waiting and serious are perceivably distinct` (different core),
  reinforcing the accessibility intent that the two states are not confusable.
- Its `serious and critical have distinct appearance colors` test still passes:
  SERIOUS is now violet/violet, CRITICAL is red/red.

No other test in the Android module touches `appearanceFor` or `JarvisPalette`
color fields (verified by search), so the rest of the suite is unaffected.

## Validation — CI-only (no local Android toolchain)

There is **no local Android/Gradle/JDK toolchain in this environment**, so the
Kotlin compile and the JVM unit tests could **not** be run locally. Validation
was **inspection-only**:

- Re-read the full diff for Kotlin correctness: value-class `Color` equality,
  3-arg `assertEquals(message, expected, actual)`, `assertNotEquals` on
  `Pair`/`Color`, and the `to` infix for `(core, ring)` pairs — all mirror
  patterns already compiling in this package.
- Confirmed every changed hex resolves to a canonical Singularity token in
  `ui/theme/Color.kt` (`JarvisViolet = 0xFFB388FF` = `--ring-2`,
  `JarvisGold = 0xFFFFFFFF` = `--core`, `JarvisCyan = 0xFF7AE0FF` = `--ring-1`).
- Confirmed imports are unchanged/already sorted (`assertNotEquals` was already
  imported in `IconStateAccessibilityTest`); no new imports needed.
- `uv run ruff check` ignores `.kt` (no Python touched).

**The authoritative gate is CI** — specifically the **"Android JVM unit
(testDebugUnitTest)"** job. Please confirm it is green before merge.

## Residual / follow-on

- Compile/test not locally verifiable → relying on CI (flagged in the PR).
- `IconState.kt` still has stale "Gold ring" doc comments on
  `WAITING_FOR_APPROVAL` / `SERIOUS_ACTION_PENDING`. That file is **outside this
  task's owned set**, so it was intentionally not touched; the comments are
  cosmetic (no compile/behavior impact) and can be corrected in a later
  doc-only sweep.
- THINKING also renders violet/violet; it is an *active* (not at-rest) state and
  out of scope here — it is distinguished behaviorally (pulse/halo) and by the
  state-resolution priority, and no test asserts THINKING-vs-SERIOUS color
  distinctness.
