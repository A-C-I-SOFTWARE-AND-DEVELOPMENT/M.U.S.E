# G2b — Refine the muse terminal glyph

**Grain:** G2b (swarm follow-up to G2's CLI "singularity" skin).
**Branch:** `claude/muse-cli-singularity-glyph`
**Base branch:** `claude/muse-cli-singularity-skin` (G2, cumulative).
**Base commit:** `9b9db6f514b8e8c3947e04344ed77360a418bdae`
**Owned files (only):**
- `hermes_cli/banner.py` — ONLY the `muse_GLYPH` constant (ring + core art).
- `docs/launch/muse-app/g2b-glyph.md` — this snapshot.

Nothing else touched. `muse_WORDMARK`, the skins, `cli.py`, the comment
header, and the two text tiers below the glyph were left byte-for-byte
unchanged. `git diff --stat` = `hermes_cli/banner.py | 22 +++----` (1 file,
9 insertions / 13 deletions), confined to the `muse_GLYPH` string.

## Intent

G2 shipped a core+ring glyph whose **core rendered off-center-feeling** and
whose **ring was lumpy/ragged** (the lower-left was torn open with stray
fragments instead of one clean gap). This grain replaces ONLY the ring+core
art with a clean, symmetric, concentric octagonal ring, core dead-center,
and a single clean gap at the lower-right — keeping the same Rich-markup
string format and the two brand text tiers underneath.

## The new `muse_GLYPH` art (Rich markup)

```
muse_GLYPH = """           [#8DC3FF]╭[/][#90BEFF]─[/][#93B9FF]─[/][#96B4FF]─[/][#9AAFFF]─[/][#9DAAFF]─[/][#A0A5FF]╮[/]
        [#84D1FF]╭[/][#87CCFF]─[/][#8AC8FF]╯[/]       [#A3A0FF]╰[/][#A69CFF]─[/][#AA97FF]╮[/]
      [#7DDBFF]╭[/][#80D6FF]─[/][#84D1FF]╯[/]           [#AA97FF]╰[/][#AD92FF]─[/][#B08DFF]╮[/]
     [#7AE0FF]╭[/][#7DDBFF]╯[/]               [#B08DFF]╰[/][#B388FF]╮[/]
     [#7AE0FF]│[/]        [bold #FFFFFF]◉[/]        [#B388FF]│[/]
     [#7AE0FF]╰[/][#7DDBFF]╮[/]               [#B08DFF]╭[/][#B388FF]╯[/]
      [#7DDBFF]╰[/][#80D6FF]─[/][#84D1FF]╮[/]           [#AA97FF]╭[/][#AD92FF]─[/][#B08DFF]╯[/]
        [#84D1FF]╰[/][#87CCFF]─[/][#8AC8FF]╮[/]
           [#8DC3FF]╰[/][#90BEFF]─[/][#93B9FF]─[/][#96B4FF]─[/][#9AAFFF]─[/][#9DAAFF]─[/][#A0A5FF]╯[/]

        [#AAB2C4]Multi-Use Synaptic Entity[/]
         [dim #8B93A6]One mind, many pathways.[/]"""
```

## How it satisfies each requirement

1. **Symmetric & concentric** — a clean octagonal ring built from
   `╭╮╰╯─│`. Per-row left/right midpoints are exactly `14.0` for every
   non-gap row, and the top/bottom halves mirror exactly (row `i` extent ==
   row `8-i` extent).
2. **Core dead-center** — bold `#FFFFFF` `◉` at (row 4, col 14). Ring
   horizontal extent is cols 5..23 → midpoint `14.0`; vertical extent rows
   0..8 → midpoint `4.0`. Core offset = `0.0` on both axes.
3. **One clean gap at the lower-right** — the lower-right shoulder (row 7's
   right `╭─╯`) is the single break in the ring; everything else stays
   closed and symmetric.
4. **Gradient left→right cyan→violet** — each ring character is colored by
   its horizontal column, linearly interpolated from `#7AE0FF` (leftmost,
   col 5) to `#B388FF` (rightmost, col 23). **19 distinct interpolated
   stops** (requirement: ≥4). Matte — no glow/bold on the ring; bold is
   reserved for the white core.
5. **Compact** — 9 ring rows; max rendered line width (including the text
   tiers) = 33 cols, well within an 80-col terminal.

## Centering-check output (PASS)

Throwaway check: strip Rich markup via
`Text.from_markup(muse_GLYPH).plain`, isolate the ring region (everything
above the first blank line), compute per-row + overall left/right extents,
locate the `◉`/`●` core, and assert the core column is within ±1 of the
horizontal center and its row within ±1 of the vertical center.

```
=== ring region ===
 0|           ╭─────╮|
 1|        ╭─╯       ╰─╮|
 2|      ╭─╯           ╰─╮|
 3|     ╭╯               ╰╮|
 4|     │        ◉        │|
 5|     ╰╮               ╭╯|
 6|      ╰─╮           ╭─╯|
 7|        ╰─╮|
 8|           ╰─────╯|

ring left extent : 5
ring right extent: 23
h-center (col)   : 14.0
v-center (row)   : 4.0
core char        : '◉'
core (row, col)  : (4, 14)
ring rows        : 9
core col offset  : 0.0  (must be <= 1)
core row offset  : 0.0  (must be <= 1)

=== per-row midpoint symmetry about h-center ===
row0: lo=11 hi=17 mid= 14.0 SYM
row1: lo= 8 hi=20 mid= 14.0 SYM
row2: lo= 6 hi=22 mid= 14.0 SYM
row3: lo= 5 hi=23 mid= 14.0 SYM
row4: lo= 5 hi=23 mid= 14.0 SYM
row5: lo= 5 hi=23 mid= 14.0 SYM
row6: lo= 6 hi=22 mid= 14.0 SYM
row7: lo= 8 hi=10 mid=  9.0 (gap/asym)   <- the intentional lower-right gap
row8: lo=11 hi=17 mid= 14.0 SYM

max rendered line width (incl. text tiers): 33  (must be <= 80)

RESULT: PASS
```

Gradient stop count (ring chars only, excluding `#FFFFFF` core and the two
text-tier colors):

```
distinct ring gradient stops: 19 (requirement: >=4)
leftmost color : #7AE0FF
contains #7AE0FF (cyan)  : True
contains #B388FF (violet): True
```

## Rendered text (captured)

`uv run python -c "from rich.console import Console; from hermes_cli import banner; Console().print(banner.muse_GLYPH)"`:

```
           ╭─────╮
        ╭─╯       ╰─╮
      ╭─╯           ╰─╮
     ╭╯               ╰╮
     │        ◉        │
     ╰╮               ╭╯
      ╰─╮           ╭─╯
        ╰─╮
           ╰─────╯

        Multi-Use Synaptic Entity
         One mind, many pathways.
```

## Validation

- `uv run ruff check hermes_cli/banner.py` → **All checks passed!**
- `uv run pytest tests/hermes_cli/test_skin_engine.py tests/test_cli_skin_integration.py -q`
  → **49 passed in 2.76s** (only an art constant changed, as expected).

## Residual risks

- **Box-drawing arc glyphs** (`╭╮╰╯`) require a font/terminal with those
  rounded-corner code points (U+256D–U+2570). Fonts lacking them fall back
  to a tofu box; the previous glyph used the same characters, so this is no
  regression. The straight `─│` segments degrade gracefully everywhere.
- **Centering is column-based, not cell-aspect-based.** Terminal cells are
  ~2:1 (taller than wide), so the octagon reads as a slightly squat circle —
  intentional and unchanged in kind from G2; it cannot be made a perfect
  circle in a character grid.
- The gradient is keyed to absolute column position (5..23). The leading
  indentation that positions the glyph is fixed; if a future grain re-indents
  the whole block, regenerate the per-column gradient so the leftmost ring
  char stays `#7AE0FF`.
- No PR / no merge per grain scope — orchestrator gates the merge.
