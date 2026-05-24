#!/usr/bin/env bash
# Safe workspace initializer for Hermes mobile / Termux / CLI workflows.
#
# This script does not authenticate Codex, Claude Code, or any provider by itself.
# It captures the current workspace, checks optional tools, and prints realistic
# next steps so multiple CLIs can be launched from the same repo directory.

set -euo pipefail

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

note() {
  printf '==> %s\n' "$*"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

WORKSPACE="$(pwd -P)"

[ -d "$WORKSPACE/.git" ] || fail "run this from the root of a git workspace: $WORKSPACE"
require_cmd git

note "Hermes workspace binding"
printf 'workspace=%s\n' "$WORKSPACE"
printf 'branch=%s\n' "$(git branch --show-current 2>/dev/null || printf 'unknown')"
printf 'remote=%s\n' "$(git remote get-url origin 2>/dev/null || printf 'none')"

cat <<'INFO'

Authentication boundaries:
- Hermes provider API keys belong in environment variables or supported config files, never in git.
- Codex and Claude Code each use their own supported login/API-key flow.
- A ChatGPT/Claude subscription does not automatically become an API key inside this repo.

Optional CLI checks:
INFO

for tool in hermes codex claude adb termux-info; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '  found:   %s -> %s\n' "$tool" "$(command -v "$tool")"
  else
    printf '  missing: %s\n' "$tool"
  fi
done

cat <<INFO

Recommended launch pattern:
1. Keep every agent/coder in this workspace:
   cd "$WORKSPACE"

2. Verify Hermes locally:
   hermes doctor

3. Authenticate external coding CLIs using the command supported by your installed version:
   codex --help
   claude --help

4. Run Codex/Claude Code from the same workspace after authentication.

Android note:
- This repository currently has no native Android module or foreground service.
- Termux can run the CLI workflow directly.
- ADB-triggered Android service workflows require a real Android app module first.
INFO
