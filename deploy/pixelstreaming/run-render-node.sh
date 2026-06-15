#!/usr/bin/env bash
# Nero cockpit — UE5 render node launcher (template, OWNER-GATED).
#
# Launches the cooked SynapseObservatory app (Nero theme) as a Pixel Streaming
# render node that connects to a running signalling server. Spawning the render
# process is an outward-facing, resource-spending action and a change to the
# master plan's locked delivery model, so it is gated: the script refuses to run
# unless MUSE_PS_ALLOW_SPAWN=1 is set explicitly (mirrors MUSE_UE5_ALLOW_SPAWN).
#
# Usage:
#   MUSE_PS_ALLOW_SPAWN=1 deploy/pixelstreaming/run-render-node.sh \
#       /path/to/Synapse.exe ws://<host>:8888
#
# See deploy/pixelstreaming/README.md and
# docs/plans/2026-06-14-nero-fleet-streaming-pivot-addendum.md.
set -euo pipefail

APP="${1:-}"
SIGNAL_URL="${2:-ws://127.0.0.1:8888}"
RES="${PS_RES:-1920x1080}"

if [[ "${MUSE_PS_ALLOW_SPAWN:-0}" != "1" ]]; then
  cat >&2 <<'MSG'
refusing to launch a render node: owner gate not set.
This starts a GPU render process and streams the cockpit off-machine.
Re-run with MUSE_PS_ALLOW_SPAWN=1 once the Pixel Streaming pivot is authorized.
MSG
  # Print the command that WOULD run, so it is reviewable without spawning.
  echo "would run: ${APP:-<app>} -PixelStreaming2URL=$SIGNAL_URL -RenderOffscreen -ResX=${RES%x*} -ResY=${RES#*x}" >&2
  exit 2
fi

if [[ -z "$APP" || ! -x "$APP" ]]; then
  echo "error: pass the path to a runnable Synapse build as arg 1." >&2
  exit 1
fi

echo "Launching Nero render node → $SIGNAL_URL (res $RES)"
exec "$APP" \
  -PixelStreaming2URL="$SIGNAL_URL" \
  -RenderOffscreen \
  -ResX="${RES%x*}" -ResY="${RES#*x}" \
  -Unattended -stdout
