#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  M.U.S.E Voice - Launcher (for git-bash/WSL)
# ─────────────────────────────────────────────────────────────

HERMES_PY="/c/Users/Echer/AppData/Local/hermes/M.U.S.E/venv/Scripts/python.exe"
if [ ! -f "$HERMES_PY" ]; then
    HERMES_PY="/c/Users/Echer/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  ════════════════════════════════════════════"
echo "    M.U.S.E Voice Assistant"
echo "  ════════════════════════════════════════════"
echo ""
echo "  Python: $HERMES_PY"
echo "  URL:    http://127.0.0.1:9120"
echo ""

"$HERMES_PY" "$SCRIPT_DIR/server.py"
