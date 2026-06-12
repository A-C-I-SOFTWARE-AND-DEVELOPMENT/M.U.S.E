#!/usr/bin/env bash
# Legacy entry point: scripts/hermes-10-10-smoke.sh was renamed to scripts/muse-10-10-smoke.sh
# (Hermes -> MUSE rename). Permanent forwarding stub.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/muse-10-10-smoke.sh" "$@"
