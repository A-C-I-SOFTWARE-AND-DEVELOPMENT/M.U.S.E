# M.U.S.E architecture flow-chart

A polished, high-detail **conceptual flow chart** of the entire M.U.S.E
repository — every subsystem described in plain English, organized into twelve
top-to-bottom *planes* (surfaces → command center → governance → orchestration →
cognition → routing → capabilities → self-improvement → verification kernel →
federation → supporting fabric → execution substrate).

It is deliberately **conceptual**: no filenames and no source code, just what
each part of the system does and how data flows through it. The safety spine
(owner gates, verification gates, ledgers) is drawn across every layer.

## What it covers

The chart is data-driven from the architecture the repo already documents:
the machine-readable component registry, the dataflow and context-engineering
notes under `docs/architecture/`, plus a sweep of every top-level area
(`apps/`, `web/`, `gateway/`, `plugins/`, `tools/`, `skills/`, `optional-skills/`,
`optional-mcps/`, `hermes_cli/jarvis_prime/`, `axiom/`, `second_brain/`,
`enterprise/`, `design-system/`, `website/`, `locales/`, and more).

## Build it

The generator is tracked here; the rendered artifacts land in the git-ignored
`docs/_generated/flowchart/` tree (repo convention — heavy/generated outputs are
not committed).

```bash
# 1) generate the HTML poster
python3 scripts/diagrams/build_muse_flowchart.py

# 2) render it to a single-page vector PDF (crisp far beyond 4K)
node scripts/diagrams/render_flowchart.cjs \
  docs/_generated/flowchart/muse_architecture_flowchart.html \
  docs/_generated/flowchart/MUSE_Architecture_Flowchart.pdf
```

Requirements for the render step: Node.js with the `playwright` package and a
Chromium browser. If Playwright cannot find its browser, point it at one with
`PLAYWRIGHT_CHROMIUM=/path/to/chrome`.

## Why a vector PDF

`page.pdf()` emits a true vector document (selectable text, embedded fonts), so
the poster scales without limit — sharper than any fixed-resolution raster while
staying a fraction of the size. The page auto-sizes to the content so the whole
map is one page.

## Editing the content

Open `build_muse_flowchart.py`. The whole poster is a small data model:
`PLANES` is a list of `Plane`s, each with an accent color and a list of `Card`s
(title, description, optional tag chips, and an `owner-gated` badge). Add or edit
a card, re-run the two commands above, and the layout reflows automatically.
