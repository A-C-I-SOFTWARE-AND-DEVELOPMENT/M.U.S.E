#!/usr/bin/env bash
#
# live-cockpit.sh — one-shot "live debug" of the JARVIS Prime Android app
# against a real Hermes cockpit gateway running on this machine.
#
# It prints the pairing token, starts `hermes cockpit serve`, waits for the
# port, smoke-tests every layer the app uses (health, an authed route, a 401,
# and the /v1/jarvis/chat NDJSON stream), then prints exactly how to point the
# app at it (emulator / USB+adb / LAN). Leaves the gateway running until Ctrl-C.
#
# Loopback-only by default. `--lan` binds all interfaces for a physical phone
# on the same Wi-Fi (exposes the agent endpoint — opt-in, with a warning).
#
# See apps/android/docs/LIVE_DEBUG.md for the full walkthrough.
#
# Usage:
#   scripts/dev/live-cockpit.sh            # serve on 127.0.0.1:8765 + smoke test
#   scripts/dev/live-cockpit.sh --lan      # bind 0.0.0.0 for a Wi-Fi phone
#   scripts/dev/live-cockpit.sh --port N   # use a different port
#   scripts/dev/live-cockpit.sh --smoke    # smoke-test an already-running gateway, then exit

set -euo pipefail

PORT=8765
LAN=0
SMOKE_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --lan) LAN=1 ;;
    --smoke) SMOKE_ONLY=1 ;;
    --port) PORT="${2:?--port needs a value}"; shift ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

if ! command -v hermes >/dev/null 2>&1; then
  echo "error: 'hermes' CLI not found. Install it first:" >&2
  echo "  pip install -e '.[all,dev]'   # from the repo root" >&2
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "error: 'curl' is required for the smoke test." >&2
  exit 1
fi

# The token is created on first use and persisted in ~/.hermes/cockpit/.
TOKEN="$(hermes cockpit token)"

smoke() {
  local base="http://127.0.0.1:${PORT}"
  echo "── smoke test against ${base} ───────────────────────────────"
  printf '1) GET  /v1/health (no auth)            -> '
  curl -fsS -o /dev/null -w '%{http_code}\n' "${base}/v1/health" || echo "UNREACHABLE"
  printf '2) GET  /v1/cockpit/runtime/status      -> '
  curl -fsS -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer ${TOKEN}" \
    "${base}/v1/cockpit/runtime/status" || echo "FAILED"
  printf '3) GET  status WITHOUT token (want 401) -> '
  curl -s -o /dev/null -w '%{http_code}\n' "${base}/v1/cockpit/runtime/status"
  echo   '4) POST /v1/jarvis/chat (first stream lines):'
  # `head` closes the pipe early (SIGPIPE on curl); tolerate it under pipefail.
  { curl -s -N -X POST -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
      -d '{"prompt":"Say hi in five words.","history":[]}' \
      "${base}/v1/jarvis/chat" | head -n 6 | sed 's/^/     /'; } || true
  echo "─────────────────────────────────────────────────────────────"
}

if [ "$SMOKE_ONLY" -eq 1 ]; then
  smoke
  exit 0
fi

HOST=127.0.0.1
SERVE_FLAGS=()
if [ "$LAN" -eq 1 ]; then
  HOST=0.0.0.0
  SERVE_FLAGS+=(--allow-external)
  echo "⚠️  --lan: binding 0.0.0.0 — the agent endpoint is reachable by anyone on your network."
fi

# Start the gateway in the background; stop it when this script exits.
hermes cockpit serve --host "$HOST" --port "$PORT" "${SERVE_FLAGS[@]}" &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

# Wait for the port to accept connections.
for _ in $(seq 1 40); do
  if curl -fsS -o /dev/null "http://127.0.0.1:${PORT}/v1/health" 2>/dev/null; then break; fi
  sleep 0.25
done

smoke

# Best-effort LAN IP for the Wi-Fi path.
lan_ip="<your-PC-LAN-IP>"
if command -v hostname >/dev/null 2>&1 && hostname -I >/dev/null 2>&1; then
  lan_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
elif command -v ipconfig >/dev/null 2>&1; then
  lan_ip="$(ipconfig getifaddr en0 2>/dev/null || echo "<your-PC-LAN-IP>")"
fi

cat <<EOF

Gateway is up on http://${HOST}:${PORT}
Pairing token: ${TOKEN}

Wire the JARVIS Prime app — Settings → Connection → endpoint + paste the token:
  • Android emulator on this PC : http://10.0.2.2:${PORT}
  • USB phone (run: adb reverse tcp:${PORT} tcp:${PORT}) : http://127.0.0.1:${PORT}
  • Phone on same Wi-Fi (needs --lan) : http://${lan_ip}:${PORT}

For real chat *prose* (not just the agent summary) run a local model:
  hermes models bootstrap        # or: ollama serve && ollama pull llama3.1

Press Ctrl-C to stop the gateway.
EOF

wait "$SERVER_PID"
