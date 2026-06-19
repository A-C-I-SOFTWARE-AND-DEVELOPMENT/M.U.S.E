# @muse/design-system

The **canonical source of craft** for muse One white core in the void,
wrapped by one thin spectral ring — *"one mind, many pathways."* This package
holds the design tokens (color, spacing, radius, type, elevation, motion, glyph
geometry) and a pure-Node generator that emits **platform artifacts** for both
the web cockpit and the Android app from a single file.

Web and Android render the **same** values because they both build from
[`tokens.json`](./tokens.json). Don't hand-pick a hex in either app — add it
here and regenerate.

## What's in the box

| File | Role |
|---|---|
| `tokens.json` | The canonical tokens. **Edit this**, nothing in `dist/`. |
| `scripts/generate.mjs` | Pure Node (zero deps) generator. |
| `dist/tokens.css` | Generated CSS custom properties (web). |
| `dist/Tokens.kt` | Generated Kotlin `object museTokens` (Compose). |
| `test/tokens.test.mjs` | Asserts the generated artifacts carry the exact Singularity hex on both targets. |

`dist/` is generated output — never edit it by hand. It is committed so
consumers don't need a Node toolchain just to read a color.

## Build & test

```bash
cd design-system
npm install        # no runtime deps; sets up the workspace
npm run build      # tokens.json -> dist/tokens.css + dist/Tokens.kt
npm test           # verifies the exact hex values landed on both targets
```

## Consume from the web

Import the generated stylesheet and use the custom properties:

```html
<link rel="stylesheet" href="../../design-system/dist/tokens.css" />
```

```css
.card {
  background: var(--void-3);          /* elevation: card */
  border: 1px solid var(--edge);
  border-radius: var(--radius-md);    /* 12px */
  color: var(--signal);
  padding: var(--space-4);            /* 16px */
}
.ring { background: var(--ring-grad); }
```

The existing cockpit aliases (`--radius`, `--sans`, `--mono`) are preserved, so
`dist/tokens.css` is a drop-in superset of the current
`gateway/cockpit/static/tokens.css`.

## Consume from Compose (Android)

Drop `dist/Tokens.kt` into the app's design-system module (package
`musedesignsystem`) and reference it:

```kotlin
import musedesignsystem.museTokens

Surface(
    color = museTokens.Color.void3,
    shape = RoundedCornerShape(museTokens.Radius.md),
) {
    Text(
        "muse",
        color = museTokens.Color.signal,
        fontSize = museTokens.Type.title.size,
    )
}
// Spectral ring: Brush.horizontalGradient(museTokens.ringGradientStops)
```

Colors are emitted as `androidx.compose.ui.graphics.Color(0xFF......)`, radii
and spacing as `.dp`, type sizes as `.sp`, durations as millisecond `Int`s, and
easing as cubic-bezier control-point `FloatArray`s.

## The rules these tokens encode

- **Three color roles max** in any composition: white core + the two ring stops.
  `--ok` / `--warn` / `--danger` are UI status colors and never appear in brand
  art.
- **Elevation is tonal, not shadow.** `flat → raised → card` lighten the void
  (`#050507 → #0b0d12 → #12151d`). No drop shadows (a brand *Don't*).
- **Spacing is a 4/8 grid** (4, 8, 12, 16, 24, 32, 48, 64).
- **Motion follows Material 3** — 150 / 250 / 350 ms with standard / emphasized
  / decelerate easing.
- **The glyph** is one white core + one spectral ring with a single gap, rotated
  `-32°`, round caps, `66 28` dasharray.

When tokens here and
[`docs/brand/muse-design-language.md`](../docs/brand/muse-design-language.md)
disagree, the design-language doc wins — update `tokens.json` to match it.
