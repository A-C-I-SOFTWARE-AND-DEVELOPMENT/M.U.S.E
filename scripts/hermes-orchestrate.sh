#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Hermes Orchestration Pipeline bootstrap

Usage:
  scripts/hermes-orchestrate.sh "<prompt>"
  scripts/hermes-orchestrate.sh --job-id <id> "<prompt>"
  scripts/hermes-orchestrate.sh --status <job-id>

This script creates a local job folder contract for prompt-first Hermes orchestration.
It does not bypass official tool authentication or automate unsupported subscription UIs.
USAGE
}

ROOT_DIR="$(pwd)"
JOB_ID=""
PROMPT=""
STATUS_ONLY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --job-id)
      JOB_ID="${2:-}"
      shift 2
      ;;
    --status)
      STATUS_ONLY="${2:-}"
      shift 2
      ;;
    *)
      if [[ -z "$PROMPT" ]]; then
        PROMPT="$1"
      else
        PROMPT="$PROMPT $1"
      fi
      shift
      ;;
  esac
done

slugify() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-72
}

json_escape() {
  local py
  py="$(command -v python3 || command -v python || true)"
  if [[ -z "$py" ]]; then
    echo "error: python3 (or python) is required for json_escape" >&2
    return 1
  fi
  "$py" -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))'
}

command_path() {
  command -v "$1" 2>/dev/null || true
}

if [[ -n "$STATUS_ONLY" ]]; then
  JOB_DIR=".hermes-orchestrator/jobs/$STATUS_ONLY"
  if [[ ! -d "$JOB_DIR" ]]; then
    echo "Job not found: $JOB_DIR" >&2
    exit 1
  fi
  cat "$JOB_DIR/status.json"
  exit 0
fi

if [[ -z "$PROMPT" ]]; then
  usage >&2
  exit 1
fi

if [[ -z "$JOB_ID" ]]; then
  JOB_ID="$(date +%Y%m%d-%H%M%S)-$(slugify "$PROMPT")"
fi

JOB_DIR=".hermes-orchestrator/jobs/$JOB_ID"
mkdir -p \
  "$JOB_DIR/shared-context" \
  "$JOB_DIR/workers/hermes-local" \
  "$JOB_DIR/workers/codex" \
  "$JOB_DIR/workers/claude-code" \
  "$JOB_DIR/workers/aider" \
  "$JOB_DIR/workers/goose" \
  "$JOB_DIR/workers/chatgpt-handoff" \
  "$JOB_DIR/merge" \
  "$JOB_DIR/github" \
  "$JOB_DIR/logs"

LOG_FILE="$JOB_DIR/logs/orchestrator.log"
{
  echo "[$(date -Is)] Created Hermes orchestration job $JOB_ID"
  echo "Root: $ROOT_DIR"
} >> "$LOG_FILE"

GIT_PATH="$(command_path git)"
GH_PATH="$(command_path gh)"
PYTHON_PATH="$(command_path python || command_path python3)"
NODE_PATH="$(command_path node)"
NPM_PATH="$(command_path npm)"
PNPM_PATH="$(command_path pnpm)"
UV_PATH="$(command_path uv)"
CODEX_PATH="$(command_path codex)"
CLAUDE_PATH="$(command_path claude)"
AIDER_PATH="$(command_path aider)"
GOOSE_PATH="$(command_path goose)"
TERMUX_INFO_PATH="$(command_path termux-info)"
TERMUX_WAKE_LOCK_PATH="$(command_path termux-wake-lock)"

PROMPT_JSON="$(printf '%s' "$PROMPT" | json_escape)"
cat > "$JOB_DIR/job.json" <<JSON
{
  "job_id": "$JOB_ID",
  "prompt": $PROMPT_JSON,
  "root_dir": "$ROOT_DIR",
  "created_at": "$(date -Is)",
  "mode": "prompt_first_local_orchestration",
  "public_exposure": "off",
  "posture": "trusted_local_with_self_protection"
}
JSON

cat > "$JOB_DIR/status.json" <<JSON
{
  "job_id": "$JOB_ID",
  "state": "created",
  "tools": {
    "git": "$GIT_PATH",
    "gh": "$GH_PATH",
    "python": "$PYTHON_PATH",
    "node": "$NODE_PATH",
    "npm": "$NPM_PATH",
    "pnpm": "$PNPM_PATH",
    "uv": "$UV_PATH",
    "codex": "$CODEX_PATH",
    "claude": "$CLAUDE_PATH",
    "aider": "$AIDER_PATH",
    "goose": "$GOOSE_PATH",
    "termux_info": "$TERMUX_INFO_PATH",
    "termux_wake_lock": "$TERMUX_WAKE_LOCK_PATH"
  },
  "next_action": "Open Hermes and run /hermes-orchestration-pipeline against this job folder."
}
JSON

cat > "$JOB_DIR/mission.md" <<EOF
# Hermes Orchestration Job: $JOB_ID

## User Prompt

$PROMPT

## Objective

Use Hermes as the command center. Classify the task, create shared evidence, route work to available workers, collect outputs, score quality, merge results, validate, and prepare GitHub publishing.
EOF

if [[ -n "$GIT_PATH" && -d .git ]]; then
  {
    echo "# Repo Map"
    echo
    echo "## Git"
    echo
    echo '```text'
    git branch --show-current || true
    git status --short || true
    echo '```'
    echo
    echo "## Top-level files"
    echo
    echo '```text'
    find . -maxdepth 2 -type f \
      -not -path './.git/*' \
      -not -path './.venv/*' \
      -not -path './venv/*' \
      -not -path './node_modules/*' \
      | sort | head -300
    echo '```'
  } > "$JOB_DIR/shared-context/repo-map.md"
else
  echo "# Repo Map\n\nNo git repository detected at $ROOT_DIR." > "$JOB_DIR/shared-context/repo-map.md"
fi

cat > "$JOB_DIR/shared-context/constraints.md" <<'EOF'
# Constraints

- Use official local tools only.
- Do not proxy or scrape subscription-only app UIs.
- Do not commit secrets.
- Do not edit `.env`.
- Do not run destructive commands without explicit approval.
- Keep changes reversible.
- Prefer branch-per-job.
- Require validation before GitHub publish.
EOF

write_worker_prompt() {
  local worker="$1"
  local role="$2"
  local file="$JOB_DIR/workers/$worker/prompt.md"
  cat > "$file" <<EOF
# Worker: $worker

## Role

$role

## Mission

$PROMPT

## Shared Context

Read:

- ../../mission.md
- ../../shared-context/repo-map.md
- ../../shared-context/constraints.md

## Required Output

Write results to this worker folder:

- output.md
- patch.diff, if code changes are produced
- status.json

## Rules

- Keep scope narrow.
- State assumptions.
- Do not touch secrets.
- Include validation commands.
- Include rollback notes.
EOF
}

write_worker_prompt "hermes-local" "Inspect the repo, build evidence, run safe local commands, validate outputs, and prepare GitHub publishing artifacts."
write_worker_prompt "codex" "Implement focused code changes when official Codex CLI is installed and authenticated. Otherwise provide a copy/paste handoff prompt."
write_worker_prompt "claude-code" "Perform architecture review, complex refactor reasoning, risk review, and final code review when official Claude Code tooling is available. Otherwise provide a copy/paste handoff prompt."
write_worker_prompt "aider" "Perform git-native patching and lint/test repair loops when Aider is installed. Otherwise provide a copy/paste handoff prompt."
write_worker_prompt "goose" "Run local desktop/CLI extension workflows or recipe-style agent tasks when Goose is installed. Otherwise provide a copy/paste handoff prompt."
write_worker_prompt "chatgpt-handoff" "Provide high-level product, UX, strategy, prompt refinement, and final review handoff text for manual use when needed."

cat > "$JOB_DIR/merge/council-review.md" <<'EOF'
# Council Review

Pending worker outputs.

## Review Checklist

- Correctness
- Completeness
- Testability
- Maintainability
- Repo fit
- Risk control
- UX quality
- Jeremiah-fit
EOF

cat > "$JOB_DIR/github/pr-body.md" <<EOF
## Summary
- Pending Hermes orchestration output.

## Hermes Job
- Job ID: $JOB_ID
- Job folder: $JOB_DIR

## Validation
- [ ] Pending

## Risk / Rollback
- Revert this PR or reset the branch created for this job.
EOF

cat <<EOF
Created Hermes orchestration job:
  $JOB_DIR

Detected tools written to:
  $JOB_DIR/status.json

Next:
  1. Open Hermes.
  2. Run: /hermes-orchestration-pipeline Continue job $JOB_ID using $JOB_DIR
  3. Or inspect prompts under: $JOB_DIR/workers/*/prompt.md
EOF
