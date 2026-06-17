#!/usr/bin/env bash
# Tier 3 — heavy documentation + diagram build. Preferred home is CI (clean
# Ubuntu runner where Graphviz/LaTeX/Java "just work"). Runs locally too, but
# every tool is guarded with `command -v` and skipped gracefully when absent —
# so on Termux/minimal installs it degrades to whatever is present (typically
# pyreverse Mermaid output only).
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$ROOT"

QUALITY_PATHS="${QUALITY_PATHS:-agent tools hermes_cli gateway tui_gateway cron acp_adapter providers second_brain}"
read -r -a PATHS <<< "$QUALITY_PATHS"

DIAG="docs/_generated/diagrams"
OWN="docs/_generated/ownership"
mkdir -p "$DIAG" "$OWN"

run() { command -v "$1" >/dev/null 2>&1; }
have_dot() { command -v dot >/dev/null 2>&1; }

# --- UML / package diagrams --------------------------------------------------
# Mermaid first (no Graphviz needed; embeds in Markdown, works on Termux).
if run pyreverse; then
  pyreverse -o mmd -p MUSE "${PATHS[@]}" -d "$DIAG" 2>/dev/null || true
  if have_dot; then
    pyreverse -o dot -p MUSE "${PATHS[@]}" -d "$DIAG" 2>/dev/null || true
  fi
fi

# --- Import graph + cycles ---------------------------------------------------
if run pydeps && have_dot; then
  for p in "${PATHS[@]}"; do
    [ -d "$p" ] || continue
    pydeps "$p" --max-bacon=2 --cluster -T svg \
      -o "$DIAG/imports_${p//\//_}.svg" --noshow 2>/dev/null || true
  done
fi

# --- Call graph (AST-based) --------------------------------------------------
if run code2flow; then
  code2flow "${PATHS[@]}" -o "$DIAG/callgraph.svg" 2>/dev/null || true
fi

# --- Render any leftover dot to SVG -----------------------------------------
if have_dot; then
  for d in "$DIAG"/*.dot; do
    [ -e "$d" ] || continue
    dot -Tsvg "$d" -o "${d%.dot}.svg" 2>/dev/null || true
  done
fi

# --- Ownership / evolution ---------------------------------------------------
if run git-of-theseus-analyze; then
  git-of-theseus-analyze . --outdir "$OWN" 2>/dev/null || true
fi

# --- Sphinx HTML + PDF (only if a docs/conf.py exists) -----------------------
if run sphinx-build && [ -f docs/conf.py ]; then
  sphinx-build -b html docs docs/_build/html 2>/dev/null || true
  if run latexmk && [ -f docs/Makefile ]; then
    ( cd docs && make latexpdf ) 2>/dev/null || true
  elif run sphinx-build; then
    # Pure-Python PDF fallback (WeasyPrint), no LaTeX required.
    sphinx-build -b simplepdf docs docs/_build/pdf 2>/dev/null || true
  fi
fi

echo "muse-quality: build_docs complete. Artifacts under docs/_generated/ and docs/_build/."
