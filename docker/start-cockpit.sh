#!/bin/bash
# Container entrypoint for a HOSTED, single-tenant muse cockpit (one container
# per user on the fleet host — see docs/deploy/hosted-fleet.md).
#
# The critical constraint (gateway/cockpit/handlers.py): agentic execute lanes
# are DISABLED when the cockpit binds a non-loopback host. So we always bind the
# cockpit to 127.0.0.1 INSIDE the container (execute lanes stay enabled) and
# expose it to the container's published port with a loopback→published socat
# hop in the SAME network namespace. The reverse proxy on the host (Caddy) then
# terminates TLS and routes /u/<slug>/* to this container's published port.
#
#   browser ──https──> Caddy (host) ──> 127.0.0.1:<published> (container)
#                                         └─ socat ─> 127.0.0.1:8765 (cockpit, loopback)
#
# Env:
#   COCKPIT_PORT      loopback port the cockpit binds inside the container (8765)
#   COCKPIT_PUB_PORT  port socat listens on for the published mapping (8766)
#   HERMES_COCKPIT_AGENT=full  (set in compose) — full agent lane on
#   HERMES_BOOTSTRAP_MODELS=1  — wire model routes from ~/.hermes/.env on boot
set -euo pipefail

COCKPIT_PORT="${COCKPIT_PORT:-8765}"
COCKPIT_PUB_PORT="${COCKPIT_PUB_PORT:-8766}"

# The container is the sandbox; the cockpit stays loopback so execute lanes work.
# --agent full is also honored via HERMES_COCKPIT_AGENT=full (set in compose).
muse cockpit serve --host 127.0.0.1 --port "${COCKPIT_PORT}" --agent full &
COCKPIT_PID=$!

# Wait for the cockpit to answer before exposing it.
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${COCKPIT_PORT}/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Loopback → published hop. Keeps the cockpit's own bind on 127.0.0.1 (execute
# lanes enabled) while making it reachable on the container's published port.
socat "TCP-LISTEN:${COCKPIT_PUB_PORT},fork,reuseaddr,bind=0.0.0.0" \
      "TCP:127.0.0.1:${COCKPIT_PORT}" &
SOCAT_PID=$!

# Propagate termination to both children.
trap 'kill "${COCKPIT_PID}" "${SOCAT_PID}" 2>/dev/null || true' TERM INT
wait -n "${COCKPIT_PID}" "${SOCAT_PID}"
# If either dies, take the container down so the orchestrator restarts it.
kill "${COCKPIT_PID}" "${SOCAT_PID}" 2>/dev/null || true
