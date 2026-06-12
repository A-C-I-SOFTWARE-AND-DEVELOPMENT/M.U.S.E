#!/usr/bin/env bash
# Legacy entry point: scripts/hermes-ai-radar.sh was renamed to scripts/muse-ai-radar.sh
# (Hermes -> MUSE rename). Permanent forwarding stub.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/muse-ai-radar.sh" "$@"
