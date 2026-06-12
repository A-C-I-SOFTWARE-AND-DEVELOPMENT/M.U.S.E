#!/usr/bin/env bash
# Legacy entry point: scripts/hermes-orchestrate.sh was renamed to scripts/muse-orchestrate.sh
# (Hermes -> MUSE rename). Permanent forwarding stub.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/muse-orchestrate.sh" "$@"
