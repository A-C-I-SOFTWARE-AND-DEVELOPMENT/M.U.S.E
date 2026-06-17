#!/usr/bin/env bash
# Tier 2 — checkpoint quality gate. Run at the end of a phase or before a push
# (via `/phase-complete` or a git pre-push hook). Targets first-party packages.
#
# Blocking gates (cause a nonzero exit):
#   - ruff check against the repo's configured rule set
#   - xenon complexity, ONLY when MUSE_QUALITY_STRICT=1 and xenon is installed
# Everything else is advisory: it writes a JSON/text report and never fails.
# This keeps the gate honest on a large, stdlib-heavy tree (no perpetual red).
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$ROOT"

# Default first-party package set (no src/ layout in this repo).
QUALITY_PATHS="${QUALITY_PATHS:-agent tools hermes_cli gateway tui_gateway cron acp_adapter providers second_brain}"
read -r -a PATHS <<< "$QUALITY_PATHS"

OUT="docs/_generated/health"
mkdir -p "$OUT"
fail=0

run() { command -v "$1" >/dev/null 2>&1; }

# --- Ruff (BLOCKING: repo-configured rules only; do not widen) ---------------
if run ruff; then
  ruff check --output-format=json "${PATHS[@]}" > "$OUT/ruff.json" 2>/dev/null || true
  if ! ruff check "${PATHS[@]}" > "$OUT/ruff.txt" 2>&1; then
    fail=1
  fi
else
  echo "ruff not installed" > "$OUT/ruff.txt"
fi

# --- ty (ADVISORY: matches repo lint.yml, which runs ty exit-zero) -----------
if run ty; then
  ty check "${PATHS[@]}" > "$OUT/ty.txt" 2>&1 || true
else
  echo "ty not installed" > "$OUT/ty.txt"
fi

# --- Security (ADVISORY) -----------------------------------------------------
if run bandit; then
  bandit -r "${PATHS[@]}" -f json -o "$OUT/bandit.json" -q 2>/dev/null || true
fi

# --- Complexity / maintainability (radon ADVISORY; xenon optional gate) ------
if run radon; then
  radon cc "${PATHS[@]}" -j > "$OUT/radon_cc.json" 2>/dev/null || true
  radon mi "${PATHS[@]}" -j > "$OUT/radon_mi.json" 2>/dev/null || true
fi
if run xenon; then
  if [ "${MUSE_QUALITY_STRICT:-0}" = "1" ]; then
    xenon --max-absolute B --max-modules A --max-average A "${PATHS[@]}" \
      > "$OUT/xenon.txt" 2>&1 || fail=1
  else
    xenon --max-absolute B --max-modules A --max-average A "${PATHS[@]}" \
      > "$OUT/xenon.txt" 2>&1 || true
  fi
fi

# --- Docstring coverage (ADVISORY) -------------------------------------------
if run interrogate; then
  interrogate -q "${PATHS[@]}" > "$OUT/interrogate.txt" 2>&1 || true
fi

# --- Architecture contracts (ADVISORY unless an .importlinter exists) --------
if run lint-imports && [ -f .importlinter ]; then
  if [ "${MUSE_QUALITY_STRICT:-0}" = "1" ]; then
    lint-imports > "$OUT/import_linter.txt" 2>&1 || fail=1
  else
    lint-imports > "$OUT/import_linter.txt" 2>&1 || true
  fi
fi

# --- Dead code (ADVISORY) ----------------------------------------------------
if run vulture; then
  vulture "${PATHS[@]}" --min-confidence 80 > "$OUT/vulture.txt" 2>&1 || true
fi

# --- Task-marker inventory (ADVISORY) ----------------------------------------
if run rg; then
  rg -n "TODO|FIXME|BUG|HACK|XXX" "${PATHS[@]}" > "$OUT/todos.txt" 2>/dev/null || true
fi

# --- Machine-readable summary ------------------------------------------------
QUALITY_PATHS="$QUALITY_PATHS" GATE_FAIL="$fail" \
  python "$(dirname "$0")/summarize_health.py" || true

if [ "$fail" -ne 0 ]; then
  echo "muse-quality: checkpoint gate FAILED (see $OUT/)." 1>&2
else
  echo "muse-quality: checkpoint gate passed (reports in $OUT/)."
fi
exit "$fail"
