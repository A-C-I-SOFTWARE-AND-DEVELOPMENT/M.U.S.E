#!/usr/bin/env bash
# Nero cockpit — Pixel Streaming signalling server launcher (template).
#
# Thin wrapper over Epic's SignallingWebServer (PixelStreamingInfrastructure,
# matched to UE 5.6). Edit PS_INFRA to point at your checkout, then run on the
# host render node. This only starts the signalling/web tier; the UE render
# node is launched separately by run-render-node.sh (owner-gated).
#
# See deploy/pixelstreaming/README.md and
# docs/plans/2026-06-14-nero-fleet-streaming-pivot-addendum.md (owner-gated).
set -euo pipefail

# Path to your EpicGames/PixelStreamingInfrastructure checkout (UE 5.6 branch).
PS_INFRA="${PS_INFRA:-$HOME/PixelStreamingInfrastructure}"
PLAYER_PORT="${PLAYER_PORT:-80}"     # browser / thin-client player frontend
STREAMER_PORT="${STREAMER_PORT:-8888}"  # the UE render node connects here

start="$PS_INFRA/SignallingWebServer/platform_scripts/bash/start.sh"
if [[ ! -x "$start" ]]; then
  echo "error: SignallingWebServer not found at: $start" >&2
  echo "       set PS_INFRA to your PixelStreamingInfrastructure checkout." >&2
  exit 1
fi

echo "Starting Pixel Streaming signalling: player=:$PLAYER_PORT streamer=:$STREAMER_PORT"
exec "$start" \
  --HttpPort "$PLAYER_PORT" \
  --StreamerPort "$STREAMER_PORT"
