#!/usr/bin/env bash
# Legacy entry point: scripts/hermes-termux-doctor.sh was renamed to scripts/muse-termux-doctor.sh
# (Hermes -> MUSE rename). Permanent forwarding stub.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/muse-termux-doctor.sh" "$@"
