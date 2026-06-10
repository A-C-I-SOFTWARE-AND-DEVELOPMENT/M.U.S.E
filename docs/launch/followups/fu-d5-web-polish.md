# FU-D5: Web cockpit — Singularity default theme + focus/motion/empty-state polish (Wave D G5)

- **Status:** in-review
- **Risk class:** behavior-change (pre-authorized in the Wave-D ledger — default theme flips to `muse`)
- **Branch:** `claude/fu-d5-web-polish` · **Base:** `main` @ `e283d39ea`
- **PR:** #TBD (draft)
- **Owner-gate required to merge?** yes — default-theme behavior change; pre-authorized in the Wave-D ledger, merge is still orchestrator/owner-driven (builder never self-merges).

## Intent (one paragraph)

The web cockpit had no Singularity brand theme — the default was the legacy
"Hermes Teal" lens. This grain adds the brand-canonical `muse` ("Singularity")
preset (void `#050507`, signal `#e8ecf4`, white core hero, cool spectral glow,
status warn/danger/ok pinned to `#f5c451`/`#ff5c63`/`#5be3a0`, radius
`0.75rem`, tonal elevation, no shadows) sourced from the FROZEN
`design-system/tokens.json`, registers it first, and makes it the default
active theme on installs with no explicit `dashboard.theme` (Hermes Teal stays
fully selectable; an explicit config choice is never overridden). It also adds
a theme-aware global `:focus-visible` outline, motion custom props mirroring
`tokens.json` motion plus a `prefers-reduced-motion` guard, a brand-spec
`EmptyStateCard` (icon in a matte 1px hairline circle + title + helper +
optional CTA) adopted on the three bare empty states (Sessions / Cron / Logs),
and a CSS-only sidebar NavLink hover/active micro-interaction.

## Owned files (the ONLY files this task may write)

- `web/src/themes/presets.ts`
- `web/src/index.css`
- `web/src/components/EmptyStateCard.tsx` (new)
- `web/src/pages/SessionsPage.tsx`
- `web/src/pages/CronPage.tsx`
- `web/src/pages/LogsPage.tsx`
- `hermes_cli/web_server.py`
- `tests/hermes_cli/test_web_server.py`
- `docs/launch/followups/fu-d5-web-polish.md` (this snapshot)

> Disjoint from every other in-flight Wave-D task per the ledger ownership map.
> No collisions discovered mid-flight.

## Plan (bounded steps)

1. Read `presets.ts` / `types.ts` / `context.tsx` / `index.css` fully; honor the preset schema exactly. ✅
2. Add `museTheme` ("Singularity") preset; register FIRST in `BUILTIN_THEMES`; Hermes Teal untouched and selectable. ✅
3. Backend sync: `_BUILTIN_DASHBOARD_THEMES` head entry + `GET /api/dashboard/themes` default `active` → `"muse"` (explicit config still wins). ✅
4. `index.css`: `@layer base` `:focus-visible` outline off `--midground-base`; `--dur-fast`/`--dur-std`/`--ease-standard` motion props; `prefers-reduced-motion: reduce` zeroing transitions/animations. ✅
5. New `EmptyStateCard.tsx` (theme-var styling only; matte hairline icon circle, no glow/shadow); adopted on SessionsPage, CronPage, LogsPage. ✅
6. CSS-only sidebar micro-interaction targeting the existing `aside nav ul li a` structure (`aria-current="page"` for active) — zero JSX changes. ✅
7. Tests: new `TestBuiltinDashboardThemes` (muse first / Teal selectable / default active muse / explicit config wins). ✅

## Validation

- `cd web && npm ci && npm run build` → ✅ green (`✓ built in 12.32s`)
- `cd web && npm run lint` → 21 problems (17 errors, 4 warnings) — **byte-identical to base `main`** (pre-existing `react-hooks`/`react-refresh` findings); zero new findings in owned files' changed lines
- `uv run ruff check hermes_cli/web_server.py tests/hermes_cli/test_web_server.py` → ✅ All checks passed
- `uv run ty check hermes_cli/web_server.py` → 17 diagnostics — **identical count to base `main`** (no new diagnostics)
- `uv run --extra all --extra dev pytest tests/hermes_cli/test_web_server.py -o addopts="" -q` → ✅ 149 passed
- `python3 scripts/scan_secrets.py --base origin/main` → ✅ exit 0

## Residual / follow-on

- The frontend's pre-API fallback strings in `web/src/themes/context.tsx`
  (localStorage default `"default"`, unknown-name fallback) are intentionally
  untouched — that file is not owned by this grain. Practical effect: on a
  brand-new install the very first paint before `/api/dashboard/themes`
  responds may briefly show Hermes Teal, then persist `muse`. A later grain
  owning `context.tsx` can flip those literals to `"muse"`.
- Other pages with richer existing empty states (Skills, Profiles, Plugins,
  Models) were out of scope (grain capped adoption at 3 bare pages).
- `colorOverrides.success` is pinned to brand `ok` `#5be3a0` in addition to
  the two overrides named in the grain — the slot exists and brand law lists
  all three status colors; trivially revertable if the reviewer prefers the
  literal minimum.
