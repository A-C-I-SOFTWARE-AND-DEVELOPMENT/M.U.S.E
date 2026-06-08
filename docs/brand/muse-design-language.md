# M.U.S.E. visual design language

> The captured "ways" — the rubric every M.U.S.E. surface (banner, glyph,
> favicons, cockpit, slides, social cards) is held to. It distills the design
> craft of **Google Material 3**, **Microsoft Fluent 2**, and **AAA game /
> Unreal Engine 5 (Lumen)** key-art into a small, enforceable set of rules,
> grounded in our **Singularity** palette. When a new surface needs art, start
> here. When two surfaces disagree, this file wins.

The brand in one line: **a white core that blazes in the void, wrapped by one
thin spectral ring — "one mind, many pathways."**

---

## 1. Palette (Singularity)

The single source of truth is [`gateway/cockpit/static/tokens.css`](../../gateway/cockpit/static/tokens.css).
Art uses only these roles — **three color roles max** in any composition
(white + the two ring stops); everything else is value (light vs dark).

| Token | Hex | Role in art |
|---|---|---|
| `--void` | `#050507` | the field. Full-bleed background, always. |
| `--core` | `#FFFFFF` | the hero. The luminous core; nothing outshines it. |
| `--ring-1` | `#7AE0FF` | spectral **cyan** — the ring's start stop. |
| `--ring-2` | `#B388FF` | spectral **violet** — the ring's end stop. |
| `--signal` | `#E8ECF4` | brightest body text. |
| `--signal-dim` | `#AAB2C4` | secondary text (acronym expansion). |
| `--signal-mute` | `#6B7388` | tertiary text. |
| `#EEF2F7` | near-white | wordmark fill (see the value ladder, §4). |
| `#8B93A6` | — | tagline / motto text. |

The cool-white bloom tints (`#E0F8FF`, `#D4F2FF`, `#F2FBFF`) are **derived
glows**, not brand colors — they exist only inside the core's bloom so it reads
cool. `--ok` / `--warn` / `--danger` are UI status colors and **never** appear
in brand art.

---

## 2. The mark (glyph)

One **white core** in the void, encircled by **one thin spectral ring** with a
single gap — the cockpit mark, reused verbatim. The canonical geometry lives in
[`gateway/cockpit/static/index.html`](../../gateway/cockpit/static/index.html)
(the animated header `svg`); the static forms scale that same construction:

| Surface | viewBox | ring `r` / `stroke` / `dasharray` | core `r` |
|---|---|---|---|
| Cockpit header | 48 | 15 / 1.6 / `66 28` | 3.1 |
| Banner | (1145×232) | 62 / 6.5 / `273 116` | 12.5 |
| App icon / favicon | 512 | 150 / 24 / `780 162` | 46 |

Always rotated `-32°` so the gap sits lower-right. The ring is drawn with a
left→right `#7AE0FF → #B388FF` linear gradient and **round** line caps.

---

## 3. The wordmark

**"M.U.S.E."** is a **bespoke geometric monoline** — hand-drawn `<path>`
letterforms, **not a font** (only generic fonts are installed in CI, so a font
would render differently or box-out on other machines). Rules:

- **Weight:** stroke ≈ **17% of cap height** (e.g. `15` on an `88` cap). Medium-
  bold. **Never thin** — thin strokes disintegrate on a dark field.
- **Caps & joins:** `round` everywhere, echoing the ring's caps.
- **Optical corrections (Google/MS):** round forms **overshoot** the flat ones
  — the `U` bowl and `S` terminals dip ~2px below the `M`/`E` baseline; the `S`
  top bowl is a hair smaller than the bottom; periods are baseline-aligned and
  sized to balance the heavier strokes (not tiny dots).
- **Tracking:** generous and even. Let the glyph and the wordmark breathe (≥ one
  core-diameter of space between them).

---

## 4. The banner — composition & the value ladder

Canonical source: [`assets/banner.svg`](../../assets/banner.svg) → rendered to
[`assets/banner.png`](../../assets/banner.png). This is the README lead and the
social card.

- **Canvas** `viewBox 0 0 1145 232`; rendered **@4× → 4580×928**. README embeds
  it at `width="100%"`, so the ratio is the only thing that matters.
- **Three tiers, optically centered** under the lockup:
  1. wordmark **M.U.S.E.** (hero)
  2. `MULTI-USE SYNAPTIC ENTITY` — the expansion, `#AAB2C4`, tracked uppercase
  3. `One mind, many pathways.` — the tagline/motto, `#8B93A6`, sentence case
- **The value ladder (the rule that makes it read "premium"):** brightness
  descends in clear steps so the eye lands on the core first.

  ```
  incandescent core  (#FFFFFF + bloom)   ← the single brightest point
  wordmark           (#EEF2F7, ~95%)     ← near-white, cedes the peak to the core
  expansion          (#AAB2C4)
  tagline            (#8B93A6)
  void               (#050507)
  ```

  The wordmark is **near-white, not pure white**, on purpose: the emissive core
  must own the brightest pixel (an Unreal/Lumen rule). The drop is imperceptible
  as "grey" but decisive for depth.

---

## 5. The lighting recipe — "Cinematic synthesis"

This is the chosen look (V2, refined). **Google's discipline in layout and type,
AAA/UE5's light on the core — and nowhere else.**

- **Volumetric bloom on the WHITE CORE ONLY.** Built from **stacked cool-white
  radial-gradient halos** (≈4 radii: bright-tight center → wide-faint edge) plus
  one tight **high-emissive "core punch"** so the core blazes like a real light
  source. Deterministic — no renderer-specific filters required.
- **The ring is matte.** Saturated spectral gradient, **never** bloomed or
  glowed. (Emissive core + matte ring = the depth read; if everything glows,
  nothing does.)
- **One** broad **atmospheric depth pool** behind the lockup. One. Not a stack
  of washes.
- **Cool-white bloom tint** (`#E0F8FF` family) so the glow reads cool against
  the warm-neutral white core.
- **Crisp matte wordmark** — zero glow on the letters.

`cairosvg` does support `feGaussianBlur` / `feSpecularLighting` if ever needed,
but the canonical banner deliberately uses **layered gradients** (portable,
exact, fast) instead of filters.

---

## 6. Do / Don't

**Do**
- Keep **white the hero**; spectral color is a *sparing accent* (≤ ~20% of the
  surface — essentially just the ring).
- Bloom **only** the core; keep the ring matte.
- Use **value**, not effects, for hierarchy.
- Give it **generous negative space**.
- Render at **≥4×** and **visually verify** every render (the design loop).
- Draw the wordmark as **bespoke vector paths** (font-independent).

**Don't**
- ❌ lens flare, chromatic aberration, dirt/grunge, fake scanlines.
- ❌ drop shadows (use tonal/value elevation instead).
- ❌ glow or "neon" the ring.
- ❌ thin wordmark weights on the dark field.
- ❌ more than three color roles.
- ❌ `<text>` + web fonts for the wordmark in shipped art.

---

## 7. Behavior at small sizes

The glyph must survive **16px**. The favicon
([`website/static/img/favicon.svg`](../../website/static/img/favicon.svg)) keeps
the core bloom **tight** so the ring stays a distinct circle and the icon never
collapses into a bright blob. Verified at 16 / 32 / 180 px. The wordmark and the
text tiers are **banner-only** — never shrink them into an icon.

---

## 8. Production pipeline

Code-native and deterministic. Only generic fonts exist in CI, so the wordmark
is vector and the small text uses Liberation Sans (a safe generic).

```bash
# Banner: edit assets/banner.svg, then re-render @4×
uvx --from cairosvg cairosvg assets/banner.svg -o assets/banner.png \
    --output-width 4580 --output-height 928 -b "#050507"

# Glyph rasters from website/static/img/favicon.svg
uvx --from cairosvg cairosvg website/static/img/favicon.svg \
    -o website/static/img/apple-touch-icon.png --output-width 180 --output-height 180
#  …repeat for 32 / 16 / logo (512); favicon.ico is built from a 64px render via Pillow.
```

Always **Read the rendered PNG back and eyeball it** before committing — and
spot-check pixels (`bg ≈ (5,5,7)`, `core ≈ (255,255,255)`, ring ends ≈
`#7AE0FF` / `#B388FF`).

---

## 9. Explorations & file map

The three aesthetic options built for selection are preserved as the record of
the decision (V2, refined, was chosen):
[`assets/banner-explorations/`](../../assets/banner-explorations/) —
`banner-v1-refined.svg` (restraint), `banner-v2-synthesis.svg` →
`banner-v2-refined.svg` (chosen), `banner-v3-cinematic.svg`, plus
`comparison.png`.

| Asset | Source | Used by |
|---|---|---|
| `assets/banner.svg` → `assets/banner.png` | bespoke SVG | README lead, social card |
| `website/static/img/favicon.svg` | bespoke SVG | favicons, app icon, navbar logo |
| `website/static/img/{favicon-16,-32,apple-touch-icon,logo}.png`, `favicon.ico` | rendered | the docs site |
| `web/public/favicon.ico` | rendered | the web app |
| `website/static/img/muse-banner.png` | = `assets/banner.png` | Docusaurus `themeConfig.image` |
| `gateway/cockpit/static/{index.html, tokens.css}` | code | the live cockpit + palette source |
