#!/usr/bin/env bash
# Provision the M.U.S.E. (hermes-agent) dev environment inside a devcontainer /
# GitHub Codespace. Mirrors CI and the web SessionStart hook:
#   uv pip install -e ".[all,dev]"   (fallback: pip)
#
# Idempotent and non-interactive. This sets up a DEV environment — it does NOT
# start a gateway. Codespaces is not a 24/7 host (see .devcontainer/README.md);
# run the always-on gateway on a VPS (docs/deploy/vps-deployment-guide.md).
set -euo pipefail

cd "${CONTAINER_WORKSPACE_FOLDER:-$(pwd)}"

echo "→ Installing M.U.S.E. dev dependencies (.[all,dev]) …"
if ! command -v uv >/dev/null 2>&1; then
  echo "→ Installing uv …"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

if command -v uv >/dev/null 2>&1; then
  uv pip install --system -e ".[all,dev]"
else
  python -m pip install -e ".[all,dev]"
fi

# Local-only dev home so experiments never touch a real ~/.hermes.
mkdir -p "${HERMES_HOME:-$PWD/.hermes-dev}"

echo ""
echo "✓ M.U.S.E. dev environment ready."
echo "  Sanity check:   muse doctor"
echo "  Run tests:      uv run pytest -q"
echo "  Lint:           uv run ruff check ."
echo ""
echo "  NOTE: this Codespace is for development, not 24/7 hosting — it suspends"
echo "        when idle. Deploy the always-on gateway on a VPS:"
echo "        docs/deploy/vps-deployment-guide.md + scripts/vps-harden-longhorizon.sh"
