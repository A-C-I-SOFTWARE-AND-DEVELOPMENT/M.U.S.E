#!/usr/bin/env bash
# Legacy entry point: scripts/hermes-mobile-workspace-init.sh was renamed to scripts/muse-mobile-workspace-init.sh
# (Hermes -> MUSE rename). Permanent forwarding stub.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/muse-mobile-workspace-init.sh" "$@"
