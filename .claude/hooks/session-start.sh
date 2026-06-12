#!/bin/bash
# SessionStart hook for Claude Code on the web.
#
# Provisions the hermes-agent dev environment so `hermes`, `run_agent`, the
# test suite, ruff, and `hermes doctor` work out of the box. Without this, a
# fresh web container has no dependencies installed (python-dotenv missing ->
# run_agent / muse_cli.main fail to import, pytest hits collection errors).
#
# Synchronous, idempotent, non-interactive. Mirrors CI (.github/workflows/
# tests.yml uses `uv pip install -e ".[all,dev]"`).
set -euo pipefail

# Only run in the remote (Claude Code on the web) environment.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Prefer uv (fast, respects uv.lock); fall back to pip if uv is unavailable.
if command -v uv >/dev/null 2>&1; then
  uv pip install --system -e ".[all,dev]" >/tmp/hermes-session-start.log 2>&1
else
  python -m pip install -e ".[all,dev]" >/tmp/hermes-session-start.log 2>&1
fi

echo "hermes-agent dependencies installed (.[all,dev])."
