# FU-D6: TUI light-theme rebrand to Singularity (Wave D G6)

- **Status:** in-review
- **Risk class:** behavior-change (light-terminal visuals only; dark default byte-identical)
- **Branch:** `claude/fu-d6-tui-polish` · **Base:** `main` @ `e283d39ea`
- **PR:** #440 (draft)
- **Owner-gate required to merge?** yes — changes default runtime visuals on light terminals; awaiting `Yes, with authorization.`

## Intent (one paragraph)

`LIGHT_THEME` in the TUI was still gold-era: label/session chrome `#7A5A0F`,
completion highlight mixed toward `#A0651C`, statusWarn `#8B6914`, a warm-brown
prompt ink, and **no banner art at all** (empty `bannerLogo`/`bannerHero`).
This grain rebuilds the light palette on Singularity-light per
`docs/brand/muse-design-language.md` — primary ink `#12151D`; accent/label/
prompt deep cyan `#2E7DA0` (derived from ring-1 `#7AE0FF`); session chrome
deep violet `#6B4FA3` (derived from ring-2 `#B388FF`, ~6.4:1 contrast on
white); neutral cool-gray selection backgrounds (`#DCE3EE`); **statusWarn
`#946300`** — a deliberate readable amber (~5.2:1 on white), chosen over the
gold-ish `#8A6D1C` family so nothing reads as brand gold — and ships the muse
wordmark + core/ring glyph for light terminals with `#12151D` fill, keeping
the cyan→violet spectral ring stops (they read fine on white). A consistency
pass moves the last hard-coded Hermes/Nous brand strings in `branding.tsx` and
`helpHint.tsx` onto theme brand tokens (new `brand.tagline` token, mapped in
`fromSkin` via `branding.tagline`). `thinking.tsx` was audited and already
fully themed — zero changes needed.

**Dark default proven byte-identical:** `DARK_THEME.bannerLogo`,
`DARK_THEME.bannerHero`, and `DARK_THEME.color` compared `===` against
`origin/main` via tsx — all `true` (the banner art was parameterized into
`museWordmark(fill)` / `museGlyph(core, expansion, tagline)` builders that
reproduce the dark strings exactly).

## Owned files (the ONLY files this task may write)

- `ui-tui/src/theme.ts`
- `ui-tui/src/components/helpHint.tsx`
- `ui-tui/src/components/branding.tsx`
- `ui-tui/src/components/thinking.tsx` (audited — no change required)
- `ui-tui/src/__tests__/theme.test.ts` (see deviation note below)
- `docs/launch/followups/fu-d6-tui-polish.md` (this snapshot)

> Deviation note: `theme.test.ts` was **already failing on base** (3 tests)
> with stale gold-era assertions (`brand.name === 'Hermes Agent'`,
> `primary === '#FFD700'`, `error === '#ef5350'`) plus a `fromSkin` empty-skin
> parity gap (`sessionBorder` fell back to `muted` instead of the theme
> default). Since validation requires a green `npm test` and this file is the
> test for the owned `theme.ts`, it was updated alongside: assertions moved to
> Singularity values, the `fromSkin` session-chrome fallback fixed in
> `theme.ts` (`hasSkinColors ? muted : d.color.sessionLabel/Border` — skins
> keep their coherent muted fallback; an empty skin now reproduces the default
> theme exactly), and two new guards added (no gold-era hexes anywhere in
> `LIGHT_THEME.color`; light banner lockup present with ink fill + both ring
> stops).

## Plan (bounded steps)

1. Read `theme.ts` fully; confirm `DARK_THEME` already Singularity. ✅
2. Parameterize wordmark/glyph builders; dark output byte-identical. ✅
3. Rebuild `LIGHT_THEME` (no `7A5A0F`/`A0651C`/`8B6914`/warm-brown ink). ✅
4. Ship light `bannerLogo`/`bannerHero` (`#12151D` fill, ring stops kept). ✅
5. Consistency pass: `branding.tsx` + `helpHint.tsx` brand strings → tokens
   (`brand.name`, new `brand.tagline`); verify `thinking.tsx` themes. ✅
6. Validate, snapshot, draft PR. ✅

## Validation

- `cd ui-tui && npm ci` → clean, 0 vulnerabilities
- `npx tsc -p tsconfig.json --noEmit` → clean (TSC_CLEAN)
- `npm test` (vitest) → **800 passed | 11 failed (74 files)** — the 11
  failures are markdown/layout/virtual-history tests proven **identical on
  clean base** (`git stash` → same 11 fail) and pre-date this grain; they stem
  from the locally-built `@hermes/ink` dist, not theme. Net delta vs base:
  **−3 failures (theme.test.ts now 31/31 green), 0 new failures.**
- `npx vitest run src/__tests__/theme.test.ts` → 31 passed (31)
- grep proof → zero `7A5A0F|A0651C|8B6914` matches in `LIGHT_THEME` / any
  `ui-tui/src` source (sole remaining match is the new test's guard regex —
  the enforcement, not a remnant)
- DARK_THEME byte-identity vs `origin/main` (tsx compare) → bannerLogo ✅
  bannerHero ✅ color ✅
- `python3 scripts/scan_secrets.py --base origin/main` → exit 0
  ("ok: no high-confidence secrets")

## Residual / follow-on

- The 11 pre-existing vitest failures (markdown wrap, CJK table alignment,
  virtual-history offset cache, cursor-drift) are environment/`@hermes/ink`
  dist drift and belong to a separate grain.
- `helpHint.tsx` hotkey descriptions in `content/hotkeys.js` (not owned here)
  were not audited for brand strings.
- Light banner art reuses the dark glyph's mid-gradient ring hexes verbatim
  per the work order ("ring colors kept, they read fine on white"); if an
  accessibility pass later wants deeper ring stops on white, derive them in
  `museGlyph` — single touch point now.
