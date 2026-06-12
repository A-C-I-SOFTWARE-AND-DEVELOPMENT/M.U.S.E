#!/usr/bin/env bash
# Legacy entry point: scripts/hermes-termux-service.sh was renamed to scripts/muse-termux-service.sh
# (Hermes -> MUSE rename). Permanent forwarding stub.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/muse-termux-service.sh" "$@"
