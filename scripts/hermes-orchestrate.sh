#!/usr/bin/env bash
# Thin shell wrapper around the Hermes orchestrator CLI.
#
# Usage examples:
#   hermes-orchestrate.sh run "fix the readme typo" --worker hermes_local
#   hermes-orchestrate.sh list
#   hermes-orchestrate.sh show 20260101-120000-fix-readme-typo-abcd
#   hermes-orchestrate.sh publish <job_id> --branch foo --execute
#
# Refuses to run from a non-git directory and refuses to publish onto a
# protected base unless overridden.

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
repo_root="$(cd -- "${script_dir}/.." >/dev/null 2>&1 && pwd)"

python_bin="${HERMES_PYTHON:-python3}"

if ! command -v "${python_bin}" >/dev/null 2>&1; then
  echo "hermes-orchestrate: python interpreter not found: ${python_bin}" >&2
  exit 127
fi

cd "${repo_root}"

exec "${python_bin}" -m hermes_cli.orchestrator_commands "$@"
