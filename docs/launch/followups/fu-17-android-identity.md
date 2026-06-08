# FU-17 — Android Singularity identity coherence

- **Status:** in-review (draft PR)
- **Branch:** `claude/fu-17-android-identity`
- **Base commit:** `b74f9889` (`origin/main`)
- **Owner agent:** parallel builder (this task)

## Intent

The Android avatar icon must carry the canonical **Singularity** identity —
one white core in the void with a single thin spectral ring (cyan→violet) —
with **no gold rendered at rest**.

`ui/theme/Color.kt` and `Theme.kt` were already Singularity-correct
(`JarvisInkAbyss=0xFF050507` void, `JarvisGold=0xFFFFFFFF` white core,
`JarvisCyan=0xFF7AE0FF` ring-1, `JarvisViolet=0xFFB388FF` ring-2). The
incoherence was localized to the **private** `JarvisPalette` object inside
`ui/jarvis/JarvisIconColors.kt`, which still hardcoded gold-era literals and
used them at rest:

- `IDLE` ring = `GoldDeep` (`0xFFB8860B`)
- `WAITING_FOR_APPROVAL` ring = `Gold` (`0xFFFFD700`)
- `SERIOUS_ACTION_PENDING` core + ring = `Gold` (`0xFFFFD700`)

## What changed (color tokens only)

Migrated the private `JarvisPalette` **values** to the Singularity palette,
preserving the file's documented intent (the palette is deliberately restated
here, not imported, so retuning the Material theme can't silently drift the
icon) and **all** `IconState → IconAppearance` mappings. Only the hex values
moved:

| Token      | Before (gold-era) | After (Singularity) | Note |
|------------|-------------------|---------------------|------|
| `Cyan`     | `0xFF00E5FF`      | `0xFF7AE0FF`        | `--ring-1` |
| `Gold`     | `0xFFFFD700`      | `0xFFFFFFFF`        | `--core` (white) — kills gold at WAITING/SERIOUS |
| `GoldDeep` | `0xFFB8860B`      | `0xFF7AE0FF`        | `--ring-1` — IDLE ring is now spectral |
| `Violet`   | `0xFF5865F2`      | `0xFFB388FF`        | `--ring-2` |
| `Core`     | `0xFFE5E7EB`      | `0xFFFFFFFF`        | `--core` (white) |
| `Void`     | (new)             | `0xFF050507`        | `--void`, added for completeness |

Net effect on at-rest states:
- `IDLE` → white core + spectral (cyan) ring.
- `WAITING_FOR_APPROVAL` → white core + white ring (no gold).
- `SERIOUS_ACTION_PENDING` → white core + white ring (no gold).

The two retired gold literals (`0xFFFFD700`, `0xFFB8860B`) no longer appear
anywhere in the file. `CRITICAL` (red), `BLOCKED`, `WARNING` (amber),
`COMPLETE` (green), `WORKING` (slate), `OFFLINE` (dim) are unchanged.

## Owned files

- `apps/android/app/src/main/java/com/aci/hermes/ui/jarvis/JarvisIconColors.kt`
  (palette values only; mappings + structure preserved)
- `apps/android/app/src/test/java/com/aci/hermes/ui/jarvis/IconColorsTest.kt`
  (new)
- `docs/launch/followups/fu-17-android-identity.md` (this snapshot)

**Not touched:** `ui/theme/Color.kt`, `Theme.kt` (already Singularity).

## Test added

`IconColorsTest` (mirrors the package/style of the existing
`IconStateAccessibilityTest`):

1. No at-rest state (`IDLE` / `WAITING_FOR_APPROVAL` / `SERIOUS_ACTION_PENDING`)
   renders a gold-era ring color (`0xFFFFD700` / `0xFFB8860B`).
2. No at-rest state renders a gold-era core color.
3. The palette retires both gold-era literals (`Gold` / `GoldDeep` no longer
   equal them).
4. `IDLE` renders the Singularity white core + spectral `--ring-1`.
5. Palette tokens match the canonical Singularity values from `Color.kt`.

The existing `IconStateAccessibilityTest` keeps passing: its `approval ring
uses gold` / `listening glow uses cyan` assertions compare against the
`JarvisPalette` **symbols** (not hex literals), so re-pointing the values is
transparent to it.

## Validation — CI-only (no local Android toolchain)

There is **no local Android/Gradle/JDK toolchain in this environment**, so the
Kotlin compile and the JVM unit test could **not** be run locally. Validation
was **inspection-only**:

- Re-read the full diff for Kotlin correctness (value-class `Color`
  comparisons, JUnit 3-arg `assertEquals`, `in`/`!in` set membership) — this
  mirrors patterns already compiling in `IconStateAccessibilityTest`.
- Verified every migrated hex matches `ui/theme/Color.kt` exactly.
- Confirmed imports are alphabetized to match the surrounding test files
  (`androidx.*` < `org.junit.*`). Note: the repo's Android module has **no
  ktlint/spotless/detekt** configured — CI runs `assembleDebug`,
  `testDebugUnitTest`, and Android `lintDebug` only.
- `uv run ruff check apps/android/` → "All checks passed" (no Python files;
  expected to ignore `.kt`).

**The authoritative gate is CI** — specifically the Android `unit-tests`
(`testDebugUnitTest`) and `assemble-debug` (`assembleDebug`) jobs in
`.github/workflows/android-build.yml`. Please confirm both are green before
merge.

## Residual risks

- Compile/test not locally verifiable → relying on CI (flagged in the PR).
- Behavior change is **color tokens only**; no logic, no API, no new state
  mappings. Strictly a visual-identity coherence fix.
