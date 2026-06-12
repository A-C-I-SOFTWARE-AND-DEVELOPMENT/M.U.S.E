#!/usr/bin/env bash
# Legacy entry point: setup-hermes.sh was renamed to setup-muse.sh
# (Hermes -> MUSE rename). This permanent forwarding stub keeps old
# bookmarks, docs, and curl|bash invocations working.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/setup-muse.sh" "$@"
