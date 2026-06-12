#!/bin/bash
# ============================================================================
# JARVIS Prime proactive tick
# ============================================================================
# Runs one proactive cycle of JARVIS Prime. Idempotent and quiet by default —
# only emits notifications when something material has changed since the last
# run (new CI failure on a watched PR, newly-blocked orchestrator job, daily
# briefing window).
#
# Recommended cron (10-minute cadence; disabled by default):
#
#   */10 * * * * /path/to/scripts/jarvis-prime-tick.sh >> /tmp/jarvis-tick.log 2>&1
#
# Opt-in via ~/.hermes/config.yaml:
#
#   jarvis_prime:
#     proactive_tick: enabled
#     briefing_window: "08:00 America/Toronto"
#     notify_via: telegram   # or slack, email, none
#
# Environment overrides:
#   JARVIS_NOTIFY_VIA       — telegram | slack | email | none (default: none)
#   JARVIS_BRIEFING_WINDOW  — HH:MM TZ (default: 08:00 America/Toronto)
#   JARVIS_TICK_ENABLED     — set to "1" to force-enable
# ============================================================================

set -u

NOTIFY_VIA="${JARVIS_NOTIFY_VIA:-none}"
BRIEFING_WINDOW="${JARVIS_BRIEFING_WINDOW:-08:00 America/Toronto}"
ENABLED_ARG=""
if [ "${JARVIS_TICK_ENABLED:-0}" = "1" ]; then
    ENABLED_ARG="--enabled"
fi

# Pick the right python — prefer the venv interpreter if Hermes is installed.
PYTHON_BIN="python"
if [ -x "${HERMES_HOME:-$HOME/.hermes}/.venv/bin/python" ]; then
    PYTHON_BIN="${HERMES_HOME:-$HOME/.hermes}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
fi

exec "$PYTHON_BIN" -m muse_cli.jarvis_prime tick \
    --notify-via "$NOTIFY_VIA" \
    --briefing-window "$BRIEFING_WINDOW" \
    $ENABLED_ARG
