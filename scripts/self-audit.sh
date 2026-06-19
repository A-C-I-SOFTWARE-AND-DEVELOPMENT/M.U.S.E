#!/usr/bin/env bash
# Quarterly self-audit sweep (REMAINING_WORK_PLAN Phase 5.3).
#
# Four checks, all hermetic and read-only:
#   1. compileall  — every Python file in the runtime byte-compiles
#   2. collect-only — the pytest suite collects without import errors
#   3. parse sweep  — every tracked YAML/JSON file parses
#   4. secrets grep — no obvious credential material in tracked files
#
# Exit 0 means all four are green. Run from the repo root:
#   bash scripts/self-audit.sh

set -u
cd "$(dirname "$0")/.."

FAILURES=0

step() { printf '\n== %s ==\n' "$1"; }

step "1/4 compileall"
if python -m compileall -q \
    hermes_cli gateway plugins tools agent cron acp_adapter axiom/axiom \
    scripts tests ./*.py; then
  echo "compileall: OK"
else
  echo "compileall: FAIL"
  FAILURES=$((FAILURES + 1))
fi

step "2/4 pytest collect-only"
if muse_AXIOM_GATES=0 python -m pytest tests/ -q --collect-only \
    --ignore=tests/integration --ignore=tests/e2e \
    -p no:cacheprovider > /tmp/self-audit-collect.log 2>&1; then
  tail -1 /tmp/self-audit-collect.log
  echo "collect-only: OK"
else
  tail -20 /tmp/self-audit-collect.log
  echo "collect-only: FAIL"
  FAILURES=$((FAILURES + 1))
fi

step "3/4 YAML/JSON parse sweep"
if git ls-files '*.yml' '*.yaml' '*.json' | python - <<'PYEOF'
import json
import sys

import yaml

bad = []
for path in (line.strip() for line in sys.stdin):
    if not path:
        continue
    try:
        with open(path, "r", encoding="utf-8") as fh:
            if path.endswith(".json"):
                json.load(fh)
            else:
                list(yaml.safe_load_all(fh))
    except Exception as exc:
        bad.append(f"{path}: {exc}")
for line in bad:
    print(line)
sys.exit(1 if bad else 0)
PYEOF
then
  echo "parse sweep: OK"
else
  echo "parse sweep: FAIL"
  FAILURES=$((FAILURES + 1))
fi

step "4/4 secrets grep"
# High-signal credential prefixes only; docs/templates teach with
# placeholders, so obvious examples are filtered.
PATTERN='(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}|sk-[A-Za-z0-9]{40,}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'
# Redaction code and its fixtures legitimately *contain* the patterns
# they scrub — they are the scanner's allowlist, not findings.
HITS=$(git grep -nIE "$PATTERN" -- \
    ':!*.lock' ':!package-lock.json' ':!tests/' ':!docs/' ':!*.md' \
    ':!agent/redact.py' ':!tools/tokenjuice/' \
    ':!apps/android/app/src/test/' \
    | grep -vE 'example|placeholder|EXAMPLE|redacted|XXXX|x{8}' || true)
if [ -n "$HITS" ]; then
  echo "$HITS"
  echo "secrets grep: FAIL"
  FAILURES=$((FAILURES + 1))
else
  echo "secrets grep: OK"
fi

printf '\n== self-audit: %s ==\n' "$([ "$FAILURES" -eq 0 ] && echo PASS || echo "FAIL (${FAILURES})")"
exit "$FAILURES"
