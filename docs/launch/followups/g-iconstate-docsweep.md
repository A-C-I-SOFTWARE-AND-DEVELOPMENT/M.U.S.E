# Grain snapshot: g-iconstate-docsweep

## Intent

Sweep two stale "Gold ring" KDoc comments in the Android muse icon state
enum so they match the **shipped Singularity attention palette**. FU-17 /
FU-17b already retuned the *actual* colors in `JarvisIconColors.kt` (no gold
at rest — white core + spectral cyan→violet ring). Only the stale
*comments* on `IconState.WAITING_FOR_APPROVAL` and
`IconState.SERIOUS_ACTION_PENDING` still referenced the retired gold ring.
This grain restates them; **comment-only, zero behavior change**.

## Owned (writable) files

- `apps/android/app/src/main/java/com/aci/hermes/ui/jarvis/IconState.kt`
  (comment lines only — the two `... Gold ring.` doc comments at ~lines 29 & 32)
- `docs/launch/followups/g-iconstate-docsweep.md` (this snapshot)

Did **not** touch `docs/launch/10_10_followups_ledger.md` (single-writer =
orchestrator) or `JarvisIconColors.kt` (FU-17/FU-17b's domain).

## Branch / base

- Branch: `claude/g-iconstate-docsweep`
- Base: `origin/main` (cut at fetch time)

## Change

Two KDoc comments in `IconState.kt` restated to the shipped language,
matching the authoritative recipe in `JarvisIconColors.kt` (the attention
state appearances + the lines 90-96 comment block):

| State | Stale comment | Updated comment |
|---|---|---|
| `WAITING_FOR_APPROVAL` | "... needs explicit user OK. Gold ring." | "... needs explicit user OK. White core + violet ring." |
| `SERIOUS_ACTION_PENDING` | "... pending approval. Gold ring, stronger pulse." | "... pending approval. Violet core + violet ring (heightened), stronger pulse." |

Verified against `JarvisIconColors.kt`:
- `WAITING_FOR_APPROVAL` → `coreColor = Core` (white) + `ringColor = Violet`
- `SERIOUS_ACTION_PENDING` → `coreColor = Violet` + `ringColor = Violet`
  (heightened: halo alpha 0.45 vs 0.30, pulse 0.9 vs 0.55)

No gold is rendered at rest; `JarvisPalette.Gold`/`GoldDeep` are now
white/cyan aliases retained only for source compatibility.

## Validation

- `git diff` on `IconState.kt` shows **only** the two comment lines changed
  (`1 file changed, 2 insertions(+), 2 deletions(-)`). No code / enum /
  value / import changes.
- Comment-only Kotlin edit; valid `/** ... */` KDoc syntax preserved.
- **CI-verified only:** no local Android/Gradle toolchain in this
  environment. Comment-only Kotlin cannot affect compilation; rely on CI's
  Android JVM unit job for confirmation.
- `uv run ruff check` ignores `.kt` files (not applicable here).

## Merge gating

Strictly a documentation/comment correction — no default runtime behavior
change. Draft PR opened to `main`; **do not merge** (orchestrator gates the
merge). PR notes comment-only + CI-only verification.

## Residual risks

None substantive. If a future palette retune changes the attention-state
colors again, these comments (and the authoritative block in
`JarvisIconColors.kt`) must be updated in lockstep.
