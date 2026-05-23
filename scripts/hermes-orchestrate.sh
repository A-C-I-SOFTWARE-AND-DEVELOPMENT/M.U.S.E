#!/usr/bin/env bash
#
# scripts/hermes-orchestrate.sh
#
# Phase 10 documentation stub.
#
# The real `hermes orchestrate` entry point is the subject of the next
# implementation PR. See:
#
#   docs/orchestration/final-hermes-orchestration-integration-report.md
#   docs/orchestration/NEXT_PHASE_IMPLEMENTATION_PROMPT.md
#
# Once the next PR lands, this file will be replaced with:
#
#   exec python -m hermes_cli.orchestrator "$@"
#
# For now it prints status and exits 0 so callers (and CI) can detect
# that the stub is present without crashing.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
report="docs/orchestration/final-hermes-orchestration-integration-report.md"
prompt="docs/orchestration/NEXT_PHASE_IMPLEMENTATION_PROMPT.md"

cat <<EOF
hermes-orchestrate.sh — Phase 10 documentation stub

The real \`hermes orchestrate\` entry point is not implemented yet.

Read first:
  ${repo_root}/${report}
  ${repo_root}/${prompt}

To bootstrap the real entry point, open a fresh Claude Code session on
branch \`claude/hermes-orchestrate-entry-point-<suffix>\` and paste the
fenced block from \`${prompt}\`.

This stub intentionally exits 0 so it can be wired into smoke checks
without breaking them.
EOF

exit 0
