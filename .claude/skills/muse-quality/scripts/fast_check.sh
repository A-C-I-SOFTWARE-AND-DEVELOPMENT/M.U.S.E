#!/usr/bin/env bash
# Tier 1 — fast per-edit check. Called by the PostToolUse(Edit|Write) hook with
# the changed file path as $1. Must be sub-second and must NEVER stall or block
# the agent: it always exits 0.
#
# Report-only by default (does not edit the file behind the agent's back). Set
# MUSE_QUALITY_AUTOFIX=1 to enable `ruff check --fix` on the changed file.
set -uo pipefail

f="${1:-}"
[ -n "$f" ] || exit 0
case "$f" in
  *.py) ;;
  *) exit 0 ;;
esac
[ -f "$f" ] || exit 0

command -v ruff >/dev/null 2>&1 || exit 0

mkdir -p docs/_generated 2>/dev/null || true

if [ "${MUSE_QUALITY_AUTOFIX:-0}" = "1" ]; then
  # Only fixes the repo's configured rules (pyproject [tool.ruff.lint]).
  ruff check --fix --quiet "$f" >/dev/null 2>&1 || true
fi

# Report (to stderr → visible to Claude on a PostToolUse hook) without blocking.
ruff check "$f" 1>&2 || true

# Informational task-marker delta (scans for the usual annotation tokens).
if command -v rg >/dev/null 2>&1; then
  rg -n "TODO|FIXME|BUG|HACK|XXX" "$f" >> docs/_generated/todo_delta.log 2>/dev/null || true
fi

exit 0
