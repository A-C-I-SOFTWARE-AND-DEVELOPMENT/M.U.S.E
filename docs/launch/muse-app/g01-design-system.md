# G0.1 — MUSE Design System (grain snapshot)

> Single-writer snapshot for builder grain **G0.1**. Only this grain writes
> this file. The central program ledger
> (`docs/launch/muse-app-program-ledger.md`) is owned by the orchestrator.

## Intent

Stand up `design-system/` — a framework-agnostic package that is the **single
source of craft** for M.U.S.E. It holds the canonical "Singularity" tokens in
one JSON file and a pure-Node generator that emits platform artifacts so the
web cockpit and the Android app render pixel-identical values from one source.
Also document the canonical UI components both apps implement.

## Owned files (created / modified)

- `design-system/tokens.json` — canonical tokens (color, gradient, spacing 4/8
  grid, radius, type scale + font stacks, tonal elevation, Material-3 motion,
  glyph geometry).
- `design-system/scripts/generate.mjs` — pure Node (zero deps) generator →
  `dist/tokens.css` + `dist/Tokens.kt`.
- `design-system/test/tokens.test.mjs` — pure Node contract test (exact hex on
  both targets; exits non-zero on mismatch).
- `design-system/package.json` — `@muse/design-system`; `build`/`test` scripts;
  no runtime deps.
- `design-system/README.md` — what it is + how web and Compose consume it.
- `design-system/dist/tokens.css` — generated (committed).
- `design-system/dist/Tokens.kt` — generated (committed).
- `docs/brand/muse-design-language.md` — appended a `## Component catalog`
  section (the component spec). No existing lines changed.
- `docs/launch/muse-app/g01-design-system.md` — this snapshot.

Did **not** touch `gateway/cockpit/static/tokens.css`, `apps/android/**`, the
program ledger, or anything outside the owned set.

## Token fidelity

Singularity palette reproduced exactly from
`gateway/cockpit/static/tokens.css`: `void #050507`, `void-2 #0b0d12`,
`void-3 #12151d`, `edge #1c2030`, `core #ffffff`, `signal #e8ecf4`,
`signal-dim #aab2c4`, `signal-mute #6b7388`, `ring-1 #7ae0ff`,
`ring-2 #b388ff`, `ok #5be3a0`, `warn #f5c451`, `danger #ff5c63`,
`radius 12px`, `ring-grad linear-gradient(90deg,#7ae0ff,#b388ff)`. Glyph block
(`rotate -32`, dasharray `66 28`, ratios) derived from the cockpit header SVG +
the design-language doc.

`dist/tokens.css` is a **superset** of the cockpit's current `tokens.css`: it
keeps the `--radius`, `--sans`, `--mono` aliases so it can drop in without
breaking existing cockpit CSS.

## Branch & base

- Branch: `claude/muse-app-g01-design-system`
- Base commit (`git rev-parse origin/main`): `d22c3e4a1efe779e234b0428f82484f8b457f9ce`

## Validation

Run from `design-system/`:

```
npm install   -> up to date, audited 1 package, found 0 vulnerabilities
npm run build -> generated dist/tokens.css and dist/Tokens.kt from tokens.json
npm test      -> all 35 assertions passed (exit 0)
```

The test asserts each canonical hex appears in **both** `dist/tokens.css`
(e.g. `#050507`, `#7ae0ff`, `#b388ff`, `#5be3a0`, `#f5c451`, `#ff5c63`) and
`dist/Tokens.kt` (matching `0xFF050507` … `0xFFFF5C63`), plus the ring gradient,
the 4/8 spacing grid, `--radius: 12px`, the `MuseTokens` object shape, and the
glyph `-32` rotate. Both `dist/` artifacts confirmed present with exact values.

Node `v22.22.2`, npm `10.9.7`. No runtime dependencies; `npm install` only
materializes the workspace.

## Residual risks

- **Kotlin is shape-validated, not compiled.** No Android/Compose toolchain in
  this grain, so `Tokens.kt` is verified by structure + the hex contract test,
  not by `kotlinc`. The downstream Android grain should compile it inside the
  Compose module (package `muse.designsystem`); it imports
  `androidx.compose.ui.{graphics.Color, text.font.FontWeight, unit.dp, unit.sp}`.
- **Adoption is not wired.** This grain ships the source of truth only; it does
  **not** modify `gateway/cockpit/static/tokens.css` or any Android theme. A
  follow-up grain migrates the cockpit to import `dist/tokens.css` and the app
  to use `MuseTokens`. Until then two token copies coexist (intentional, by
  ownership boundaries) — values match exactly, so no visual drift.
- **`dist/` is committed.** Regenerate via `npm run build` after any
  `tokens.json` edit; a stale `dist/` would be caught by `npm test` in CI.
- **Motion easing** uses Material-3 curves (`standard`, `emphasized`,
  `decelerate`); `emphasized` is the M3 emphasized-decelerate curve
  `cubic-bezier(0.05,0.7,0.1,1)`. Tune if a later motion spec diverges.
