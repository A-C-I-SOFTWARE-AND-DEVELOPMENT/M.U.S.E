#!/usr/bin/env bash
# Hermes 10/10 release smoke — a fast, repeatable ship gate.
#
# Runs the cheap, high-signal checks an operator (or CI) can use to decide the
# 10/10 build is safe to ship:
#   1. ruff lint (the repo's enforced gate; format is checked per-PR on the diff)
#   2. the 10/10 release-readiness doctor (hard safety/correctness gates)
#   3. a fast, launch-critical test slice (readiness + plugins + orchestration)
#
# It is NOT the full suite (see scripts/run_tests.sh / CI for that). Exit code
# is 0 only when every step passes. Run from anywhere:
#     scripts/hermes-10-10-smoke.sh
set -uo pipefail

cd "$(dirname "$0")/.." || exit 2
fail=0
step() { printf '\n\033[1m── %s ──\033[0m\n' "$*"; }

# Prefer `uv run` for ruff (matches CI); fall back to a bare ruff on PATH.
RUFF=(uv run ruff)
command -v uv >/dev/null 2>&1 || RUFF=(ruff)

step "ruff — lint"
if "${RUFF[@]}" check .; then
  echo "ruff: clean"
else
  echo "ruff: FAILED"; fail=1
fi

step "hermes doctor --10-10 — release-readiness gates"
# Call the doctor in-process so the smoke does not depend on the `hermes`
# entry point being on PATH. Exits non-zero on a hard (safe-to-ship) gate.
if python -c "
import sys
from muse_cli.release_readiness_doctor import run_10_10_doctor
report = run_10_10_doctor()
print(report.render())
sys.exit(0 if report.ok else 1)
"; then
  echo "doctor: safe to ship"
else
  echo "doctor: NOT safe to ship — a hard gate failed"; fail=1
fi

step "fast test slice — readiness + plugins + orchestration"
# Override addopts so this runs without the xdist/timeout plugins the fast
# slice does not need; the full suite still runs under CI.
if python -m pytest -q -o addopts="" \
    tests/test_release_readiness_doctor.py \
    tests/test_action_executors.py \
    tests/plugins/test_vercel_plugin.py \
    tests/plugins/test_supabase_plugin.py \
    tests/plugins/memory/test_supabase_memory.py \
    tests/test_orchestrator_commands.py; then
  echo "fast tests: passed"
else
  echo "fast tests: FAILED"; fail=1
fi

printf '\n'
if [ "$fail" -eq 0 ]; then
  printf '\033[1;32mSMOKE PASSED ✓\033[0m  — safe-to-ship gates green.\n'
  printf 'See `hermes doctor --10-10` warnings for the remaining 10/10 punch list.\n'
else
  printf '\033[1;31mSMOKE FAILED ✗\033[0m  — fix the failing step(s) above.\n'
fi
exit "$fail"
