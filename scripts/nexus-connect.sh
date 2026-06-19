#!/usr/bin/env bash
# nexus-connect — thin wrapper around `python3 -m hermes_cli.nexus_connect`.
#
# Make sure this file is executable:
#     chmod +x scripts/nexus-connect.sh
#
# Then run from the repo root:
#     ./scripts/nexus-connect.sh [--base-url URL] [--device-name NAME]
exec python3 -m hermes_cli.nexus_connect "$@"
