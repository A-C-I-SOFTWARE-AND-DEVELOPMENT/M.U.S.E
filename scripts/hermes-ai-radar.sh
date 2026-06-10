#!/usr/bin/env bash
# Hermes AI improvement radar — local review hook.
#
# What this script does:
#   - prints a clear banner
#   - creates .hermes-orchestrator/ai-radar/ if it doesn't exist
#   - writes a timestamped radar request file (JSON) describing this run
#   - detects whether the `hermes` CLI is available on PATH
#   - tells the user to run `/ai-improvement-radar` inside Hermes
#
# What this script does NOT do (deliberately):
#   - it does NOT scrape subscription apps
#   - it does NOT bypass official restrictions, auth walls, or rate limits
#   - it does NOT edit docs/ai-intelligence/* policy artifacts
#   - it does NOT call non-official APIs
#
# The actual radar work — fetching official sources, extracting actionable
# features, and producing the radar report — is done by the Hermes skill
# at skills/ai-improvement-radar/SKILL.md, invoked via /ai-improvement-radar.
#
# Usage:
#   scripts/hermes-ai-radar.sh
#   scripts/hermes-ai-radar.sh --tools claude-code,codex,aider
#   scripts/hermes-ai-radar.sh --since 2026-01-01
#   scripts/hermes-ai-radar.sh --effort high

set -euo pipefail

# ── Locate repo root ────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Defaults ────────────────────────────────────────────────────────────────
TOOLS="claude-code,codex,aider,goose,continue,openhands,openclaw,gemini,jules,antigravity"
SINCE=""
EFFORT="medium"

# ── Parse args ──────────────────────────────────────────────────────────────
while [ "$#" -gt 0 ]; do
  case "$1" in
    --tools)
      TOOLS="${2:-}"
      shift 2
      ;;
    --tools=*)
      TOOLS="${1#*=}"
      shift
      ;;
    --since)
      SINCE="${2:-}"
      shift 2
      ;;
    --since=*)
      SINCE="${1#*=}"
      shift
      ;;
    --effort)
      EFFORT="${2:-medium}"
      shift 2
      ;;
    --effort=*)
      EFFORT="${1#*=}"
      shift
      ;;
    -h|--help)
      sed -n '2,30p' "$0"
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      echo "see: $0 --help" >&2
      exit 2
      ;;
  esac
done

# ── Banner ──────────────────────────────────────────────────────────────────
BAR="================================================================"
printf '\n%s\n' "$BAR"
printf '  Hermes AI Improvement Radar\n'
printf '  Tracks AI coding-tool improvements and recommends routing-policy updates.\n'
printf '  Skill: skills/ai-improvement-radar/SKILL.md\n'
printf '  Docs:  docs/ai-intelligence/ai-improvement-radar.md\n'
printf '%s\n\n' "$BAR"

# ── Prepare output dir ──────────────────────────────────────────────────────
RADAR_DIR="$REPO_ROOT/.hermes-orchestrator/ai-radar"
mkdir -p "$RADAR_DIR"

if [ ! -f "$RADAR_DIR/README.md" ]; then
  cat > "$RADAR_DIR/README.md" <<'RADAR_README'
# Hermes AI radar runs

This directory holds per-run artifacts produced by the AI improvement radar:

- `<timestamp>-request.json` — written by `scripts/hermes-ai-radar.sh`,
  describes the radar request (which tools, since-date, effort).
- `<timestamp>-radar.md` — written by the Hermes skill at
  `skills/ai-improvement-radar/SKILL.md` when invoked via the
  `/ai-improvement-radar` slash command inside Hermes.

These files are the audit trail behind any change to:

- `docs/ai-intelligence/model-registry.yaml`
- `docs/ai-intelligence/model-routing-policy.md`
- `docs/ai-intelligence/tool-capability-matrix.md`

Do not edit these files by hand. Re-run the radar instead.
RADAR_README
fi

# ── Compute timestamp (portable ISO-like, filename-safe) ────────────────────
TS="$(date -u +"%Y-%m-%dT%H-%M-%SZ")"
REQUEST_FILE="$RADAR_DIR/${TS}-request.json"

# ── Detect hermes CLI ───────────────────────────────────────────────────────
HERMES_BIN=""
if command -v hermes >/dev/null 2>&1; then
  HERMES_BIN="$(command -v hermes)"
elif [ -x "$REPO_ROOT/hermes" ]; then
  HERMES_BIN="$REPO_ROOT/hermes"
fi

# ── Detect git context (best-effort, never fatal) ───────────────────────────
GIT_BRANCH=""
GIT_COMMIT=""
if command -v git >/dev/null 2>&1 && [ -d "$REPO_ROOT/.git" ]; then
  GIT_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  GIT_COMMIT="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || true)"
fi

# ── Build CSV→JSON-array for tools ──────────────────────────────────────────
TOOLS_JSON=""
IFS=',' read -ra _tool_arr <<< "$TOOLS"
for t in "${_tool_arr[@]}"; do
  t_trim="$(printf '%s' "$t" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  [ -z "$t_trim" ] && continue
  if [ -z "$TOOLS_JSON" ]; then
    TOOLS_JSON="\"$t_trim\""
  else
    TOOLS_JSON="$TOOLS_JSON, \"$t_trim\""
  fi
done

# ── Write request file ──────────────────────────────────────────────────────
{
  printf '{\n'
  printf '  "schema": "hermes-ai-radar-request/v1",\n'
  printf '  "timestamp": "%s",\n' "$TS"
  printf '  "requested_by": "%s",\n' "${USER:-unknown}"
  printf '  "host": "%s",\n' "$(hostname 2>/dev/null || echo unknown)"
  printf '  "repo_root": "%s",\n' "$REPO_ROOT"
  printf '  "git_branch": "%s",\n' "$GIT_BRANCH"
  printf '  "git_commit": "%s",\n' "$GIT_COMMIT"
  printf '  "tools": [%s],\n' "$TOOLS_JSON"
  printf '  "since": "%s",\n' "$SINCE"
  printf '  "effort": "%s",\n' "$EFFORT"
  printf '  "hermes_cli_detected": %s,\n' "$( [ -n "$HERMES_BIN" ] && echo true || echo false )"
  printf '  "hermes_cli_path": "%s",\n' "$HERMES_BIN"
  printf '  "output_report_expected_at": ".hermes-orchestrator/ai-radar/%s-radar.md",\n' "$TS"
  printf '  "rules": [\n'
  printf '    "Prefer official docs, official repos, release notes, and changelogs.",\n'
  printf '    "Reputable engineering sources count as corroboration, not primary.",\n'
  printf '    "Mark unverified claims as unverified; do not act on them.",\n'
  printf '    "Do not update routing policy based on hype.",\n'
  printf '    "Extract only actionable features.",\n'
  printf '    "Recommend updates only; never edit policy artifacts from this script.",\n'
  printf '    "Do not scrape subscription apps or bypass official restrictions."\n'
  printf '  ]\n'
  printf '}\n'
} > "$REQUEST_FILE"

# ── Tell the user what happens next ─────────────────────────────────────────
printf 'wrote radar request: %s\n\n' "${REQUEST_FILE#"$REPO_ROOT"/}"

printf 'next: run the radar skill from inside Hermes:\n\n'
printf '    /ai-improvement-radar\n\n'

if [ -n "$HERMES_BIN" ]; then
  printf 'detected hermes CLI at: %s\n' "$HERMES_BIN"
  printf 'start a session with:\n\n'
  printf '    %s\n\n' "$HERMES_BIN"
  printf 'then type:  /ai-improvement-radar\n\n'
else
  printf 'note: `hermes` CLI was not found on PATH.\n'
  printf '      install with:\n'
  printf '        curl -fsSL https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/main/scripts/install.sh | bash\n'
  printf '      or run the skill from any Hermes-compatible agent that has loaded\n'
  printf '      skills/ai-improvement-radar/SKILL.md.\n\n'
fi

printf 'expected report path on completion:\n'
printf '    .hermes-orchestrator/ai-radar/%s-radar.md\n\n' "$TS"

printf 'remember:\n'
printf '  - this script does NOT scrape subscription apps.\n'
printf '  - this script does NOT edit policy artifacts.\n'
printf '  - changes to docs/ai-intelligence/* require human review of the radar report.\n\n'
