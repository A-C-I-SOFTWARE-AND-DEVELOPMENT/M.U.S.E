# G2 — CLI "Singularity" skin (the muse terminal redesign)

Builder grain **G2**. Adds a new **`singularity`** built-in CLI skin — the
muse terminal centerpiece — and makes it the **default** active skin. The
classic gold Hermes look is preserved, fully intact, as the opt-in **`caduceus`**
skin. The `default` built-in key is kept as the (gold) inheritance base so
existing skins and tests are unaffected.

- **Branch:** `claude/muse-cli-singularity-skin`
- **Base commit:** `9fa25b19e22d3f4c2d55aefb5773ab079424626b` (origin/main)
- **Design target:** [`docs/brand/muse-design-language.md`](../../brand/muse-design-language.md)
  — a white core blazing in the void, wrapped by one thin spectral ring with a
  single gap. White is the hero; the ring is the only spectral accent.

---

## Owned files

| File | Change |
|---|---|
| `hermes_cli/skin_engine.py` | New `singularity` + `caduceus` built-in skins; runtime default flipped to `singularity` (module `_active_skin_name` + `init_skin_from_config` fallback). |
| `hermes_cli/banner.py` | New `muse_WORDMARK` + `muse_GLYPH` Rich-markup art constants (muse block wordmark + ring/core glyph). |
| `cli.py` (branding strings only) | Welcome / help-header / goodbye fallbacks mirrored to muse the local `load_cli_config()` default `display.skin` → `singularity`. |
| `hermes_cli/config.py` (1 line) | `DEFAULT_CONFIG["display"]["skin"]` → `singularity`. **Out of the originally declared owned set**, but the *actual* runtime-default control points live in `cli.py`/`config.py`, not skin_engine — without this the launch banner stays gold. Single-token, collision-free. See "Residual risks". |
| `tests/hermes_cli/test_skin_engine.py` | Updated the 3 change-detector asserts that pinned the old default-skin *name* (no-skin / null / non-dict display → `singularity`); added positive coverage for `singularity`, `caduceus`, and `list_skins`. |
| `tests/test_cli_skin_integration.py` | Added a compact-banner test for the singularity default (muse branding + cyan border). |
| `docs/launch/muse-app/g2-cli-skin.md` | This snapshot. |

---

## What became the default

- **Runtime default active skin** is now **`singularity`** — a fresh,
  unconfigured `hermes` session shows the muse banner/branding/palette.
  Verified: `import cli; skin_engine.get_active_skin_name()` → `"singularity"`.
- **`caduceus`** is the classic gold Hermes skin, fully intact, available via
  `/skin caduceus` or `display.skin: caduceus`.
- The `default` built-in **key** is unchanged (still gold) — it remains the
  inheritance base every other skin's unspecified fields fall back to, and the
  explicit "classic" look that existing tests verify.
- Other presets (`ares`, `mono`, `slate`, `daylight`, `warm-lightmode`,
  `poseidon`, `sisyphus`, `charizard`) are untouched.

---

## `singularity` skin fields

**Palette** (Singularity tokens — white core in the void, one spectral ring):

| Field | Hex | Role |
|---|---|---|
| `banner_title` | `#FFFFFF` | the white core — brightest pixel |
| `banner_border` / ring start | `#7AE0FF` | spectral cyan |
| `ui_label` / ring end | `#B388FF` | spectral violet |
| `banner_accent` | `#7AE0FF` | section headers (cyan) |
| `banner_text` | `#EEF2F7` | near-white body (cedes peak to core) |
| `banner_dim` | `#AAB2C4` | signal-dim secondary text |
| `prompt` | `#FFFFFF` | prompt symbol blazes white |
| `status_bar_bg` | `#0B0D12` | void-2 raised surface |
| `status_bar_dim` | `#6B7388` | signal-mute |
| `ui_ok` / `ui_warn` / `ui_error` | `#5BE3A0` / `#F5C451` / `#FF5C63` | UI status only (never brand art) |

**Branding:**

- `agent_name`: `muse`
- `welcome`: `Welcome to muse — one mind, many pathways. Type your message or /help for commands.`
- `help_header`: `✦ muse Commands`
- `goodbye`: `Goodbye. ◯`
- `response_label`: ` ◉ muse `
- `prompt_symbol`: `❯` (rendered white/cyan)
- `tool_prefix`: `│`

**Tagline / sub (banner tiers):** `Multi-Use Synaptic Entity` + `One mind, many pathways.`

**Art:** `banner_logo` = the muse block wordmark; `banner_hero` = the ring +
core glyph + the two tagline tiers (matte cyan→violet ring, single gap at
lower-right, pure-white core `◉`; no glow on the ring — honors the value ladder
core → wordmark → expansion → motto → void).

---

## Rendered banner (singularity forced, plain text)

Captured via `build_welcome_banner()` with the singularity skin active (the real
banner render entrypoint), markup stripped:

```
███╗   ███╗   ██╗   ██╗   ███████╗   ███████╗
████╗ ████║   ██║   ██║   ██╔════╝   ██╔════╝
██╔████╔██║   ██║   ██║   ███████╗   █████╗
██║╚██╔╝██║   ██║   ██║   ╚════██║   ██╔══╝
██║ ╚═╝ ██║██╗╚██████╔╝██╗███████║██╗███████╗██╗
╚═╝     ╚═╝╚═╝ ╚═════╝ ╚═╝╚══════╝╚═╝╚══════╝╚═╝

╭─────────────────────────────── Hermes Agent v0.14.0 (2026.5.16) · upstream 9fa25b19 ───────────────────────────────╮
│                                                Available Tools                                                     │
│                         ╭─────╮                file: read_file                                                     │
│                     ╭──╯     ╰──╮                                                                                  │
│                  ╭─╯           ╰─╮             Available Skills                                                    │
│                ╭╯               ╰╮             general: deep-research                                              │
│               ╭╯                 ╰╮            jarvis: jarvis-prime                                                │
│               │                   │                                                                                │
│               │         ◉         │            1 tools · 2 skills · /help for commands                            │
│                         │                                                                                          │
│                        ╰╮                                                                                          │
│                ╰╮                ╭                                                                                 │
│                  ╰─╮           ╭─╯                                                                                 │
│                     ╰──╮     ╭──╯                                                                                  │
│                         ╰─────╯                                                                                    │
│                                                                                                                    │
│               Multi-Use Synaptic Entity                                                                            │
│                One mind, many pathways.                                                                            │
│                                                                                                                    │
│  claude-opus-4 · 200K context · Nous Research                                                                      │
│               /home/user/project                                                                                   │
│               Session: muse-001                                                                                    │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

Truecolor spot-check (RGB sampled from the ANSI render): wordmark uniform
near-white `(238,242,247)`; ring sweeps cyan `(122,224,255)` → violet
`(172,146,255)` left→right; core `◉` pure bold white `(255,255,255)`; tagline
tiers in signal-dim `(170,178,196)` / dim `(139,147,166)`. Panel border + accents
cyan `#7AE0FF`. Legible, columns aligned, no broken/garbled art, no leftover
"HERMES" in the art (the "Hermes Agent v…" in the title is the version label,
which is out of scope — see residual risks).

Compact (narrow-terminal) banner with singularity active:

```
╔════════════════════════════════════════════════════════════════════════════════════════╗
║ muse - AI Agent Framework                                                       ║
║ Hermes Agent v0.14.0 (test) · upstream abc12345                                     ║
╚════════════════════════════════════════════════════════════════════════════════════════╝
```

(border + title in `#7AE0FF` / `#FFFFFF`.)

---

## Validation

| Check | Command | Result |
|---|---|---|
| Lint (hermes_cli) | `uv run ruff check hermes_cli/` | **All checks passed** |
| Lint (cli.py + touched tests) | `uv run ruff check cli.py tests/hermes_cli/test_skin_engine.py tests/test_cli_skin_integration.py` | **All checks passed** |
| Types | `uv run ty check hermes_cli/skin_engine.py hermes_cli/banner.py hermes_cli/config.py` | **No NEW diagnostics** — `skin_engine.py` clean; the 4 `banner.py` + 30 `config.py` diagnostics are all pre-existing (verified against `origin/main`: same set, located in untouched code — `banner.build_welcome_banner` signature defaults, `config.py` lines ≥3246). |
| Tests | `uv run pytest -p no:xdist -o addopts="" tests/hermes_cli/test_skin_engine.py tests/test_cli_skin_integration.py tests/hermes_cli/test_banner.py tests/agent/test_onboarding.py tests/cli/test_cli_init.py tests/cli/test_cli_light_mode.py` | **142 passed** |
| Runtime default | `python -c "import cli; import hermes_cli.skin_engine as se; print(se.get_active_skin_name())"` | `singularity` |

(`uv run pytest` requires `uv sync --extra dev` first; the base venv lacks
`rich`/`yaml`. xdist/timeout addopts are disabled in the targeted run because the
plugin args don't apply to a hand-picked selection.)

---

## Design-language conformance

- **White is the hero** — `banner_title` and the core `◉` are pure `#FFFFFF`; the
  wordmark is near-white `#EEF2F7` so the core owns the brightest pixel (the
  Unreal/Lumen value-ladder rule).
- **One thin spectral ring, matte** — drawn in box-drawing arcs, left→right
  `#7AE0FF → #B388FF` gradient, single gap at the lower-right. **No glow / neon**
  on the ring.
- **≤3 color roles** in the art (cyan + violet ring stops + white core); the rest
  is value.
- **Value ladder** core → wordmark → expansion (`#AAB2C4`) → motto (`#8B93A6`) →
  void.
- **No gaudy effects** — no lens flare, drop shadows, scanlines, or ring glow.

---

## Residual risks

1. **`config.py` + `cli.py` `display.skin` default edits are outside the
   originally declared owned set.** The grain brief pointed at `skin_engine.py`
   for "make it the default," but the *effective* runtime default is the
   `display.skin` value in `cli.py::load_cli_config()`'s local `defaults` dict
   and `config.py::DEFAULT_CONFIG`; the skin_engine module default/`init_*`
   fallback is overridden by that config at launch. Both edits are single-token
   (`"default"` → `"singularity"`) with no logic change and near-zero collision
   surface, but a reviewer should confirm no parallel grain also edits those two
   lines. If a collision exists, this grain (later-starting on those files)
   should rebase per the swarm conflict rule.
2. **Version label still reads "Hermes Agent v…".** `banner.format_banner_version_label()`
   hardcodes `"Hermes Agent v{VERSION}"`. It is brand-facing but lives in a path
   gated by banner tests (`test_banner.py` asserts `"Hermes Agent v"`; integration
   tests patch it) and is arguably product-name versioning, not skin branding —
   left unchanged to avoid scope creep + test breakage. A follow-up could make it
   skin-aware (`agent_name`-derived) if muse should own the version line too.
3. **Test edits in `tests/hermes_cli/test_skin_engine.py` +
   `tests/test_cli_skin_integration.py`** were required because the prior tests
   were change-detectors pinning the old default-skin *name*. The gold-value tests
   (which `set_active_skin("default")` / `load_skin("default")` explicitly) are
   untouched and still green, since `default` stays gold.
4. **Glyph at very narrow widths.** The wordmark only prints when the terminal is
   ≥95 cols (existing `build_welcome_banner` gate); below that the compact banner
   (muse + cyan border) shows instead. The ring hero renders inside the panel
   at all widths but is most legible ≥110 cols. No regression vs the prior
   caduceus hero, which had the same gate.
