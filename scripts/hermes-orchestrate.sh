#!/usr/bin/env bash
# hermes-orchestrate.sh
#
# Phase 03 foundation scaffold for the Hermes orchestration pipeline.
# This script only emits the job-folder contract; it does not run any
# external model tools yet. The controller that fills in the artifacts
# arrives in a later phase.

set -euo pipefail

# ---------------------------------------------------------------------
# Python detection
#   Don't hardcode `python` — many distros only ship `python3`. Detect
#   `python3` first, fall back to `python`, and use the detected binary
#   for all JSON escaping below.
# ---------------------------------------------------------------------
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "hermes-orchestrate: error: neither python3 nor python found on PATH" >&2
    exit 1
fi

json_escape() {
    "${PYTHON_BIN}" -c 'import json,sys; sys.stdout.write(json.dumps(sys.stdin.read()))'
}

json_string_list() {
    "${PYTHON_BIN}" -c '
import json, os, sys
raw = os.environ.get("HERMES_ORCH_LIST", "")
items = [line for line in raw.split("\n") if line.strip()]
sys.stdout.write(json.dumps(items))
'
}

# ---------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------
ROOT_DIR=".hermes-orchestrator"
MODE="audit"
JOB_ID=""
TRUSTED_LOCAL="false"
MISSION=""
ACTION="run"   # run | help | status | list

WORKERS=(
    "hermes-local"
    "claude-code-windows"
    "codex"
    "aider"
    "goose"
    "chatgpt-handoff"
)
VALID_MODES=("plan" "research" "audit" "build" "validate" "publish")
PHASE_TAG="03-foundation"

PHASE_FILES=(
    "research"
    "planning"
    "approval"
    "implementation"
    "validation"
    "publish"
)

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
usage() {
    cat <<'EOF'
hermes-orchestrate.sh — Phase 03 foundation scaffold

USAGE
  bash scripts/hermes-orchestrate.sh [flags] "<mission text>"
  bash scripts/hermes-orchestrate.sh --help
  bash scripts/hermes-orchestrate.sh --list
  bash scripts/hermes-orchestrate.sh --status <job-id>

FLAGS
  --help               Print this help and exit.
  --list               List existing jobs under <root>/jobs and exit.
  --status <job-id>    Print status.json for a job and exit.
  --job-id <id>        Use this job id instead of an auto-generated one.
  --root <path>        Override orchestrator root (default: .hermes-orchestrator).
  --mode <m>           One of: plan | research | audit | build | validate | publish
                       (default: audit).
  --trusted-local      Mark the job as locally trusted (trusted_local=true
                       in job.json). Future phases use this to skip extra
                       confirmation prompts before mutating local state.

POSITIONAL
  Any non-flag argument is treated as the mission text. Quote multi-word
  missions: "Refactor the gateway config loader".

INVOCATION STYLES
  As a script:     bash scripts/hermes-orchestrate.sh "..."
  Make executable: chmod +x scripts/hermes-orchestrate.sh
                   ./scripts/hermes-orchestrate.sh "..."

WHAT THIS PHASE DOES
  Creates the full job-folder contract under <root>/jobs/<job-id>/ with
  empty / templated artifacts so later phases can plug a real controller
  on top of a stable shape. No external model tools are invoked here.

FOLDER CONTRACT (per job)
  job.json                          shared-context/repo-map.md
  mission.md                        shared-context/evidence.md
  status.json                       shared-context/constraints.md
  decision-ledger.md                shared-context/user-profile.md
  queue.json                        shared-context/tool-detection.json
  checkpoints/                      phases/{research,planning,approval,
  workers/<worker>/prompt.md          implementation,validation,publish}.md
  workers/<worker>/output.md        merge/council-review.md
  workers/<worker>/patch.diff       merge/scorecard.json
  workers/<worker>/status.json      merge/conflict-report.md
  validation/                       merge/final-plan.md
  github/branch.txt                 merge/final-patch.diff
  github/commit-message.txt         deploy/
  github/pr-title.txt               logs/orchestrator.log
  github/pr-body.md

WORKERS REGISTERED
  hermes-local, claude-code-windows, codex, aider, goose, chatgpt-handoff
EOF
}

is_valid_mode() {
    local candidate="$1"
    local m
    for m in "${VALID_MODES[@]}"; do
        [[ "${m}" == "${candidate}" ]] && return 0
    done
    return 1
}

generate_job_id() {
    local stamp rand
    stamp="$(date -u +%Y%m%d-%H%M%S)"
    rand="$("${PYTHON_BIN}" -c 'import secrets,sys; sys.stdout.write(secrets.token_hex(3))')"
    printf '%s-%s-%s' "${MODE}" "${stamp}" "${rand}"
}

write_file() {
    local path="$1"
    mkdir -p "$(dirname "${path}")"
    cat >"${path}"
}

# ---------------------------------------------------------------------
# Flag parsing
# ---------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            ACTION="help"
            shift
            ;;
        --list)
            ACTION="list"
            shift
            ;;
        --status)
            ACTION="status"
            shift
            if [[ $# -eq 0 ]]; then
                echo "hermes-orchestrate: --status requires a <job-id>" >&2
                exit 2
            fi
            JOB_ID="$1"
            shift
            ;;
        --job-id)
            shift
            if [[ $# -eq 0 ]]; then
                echo "hermes-orchestrate: --job-id requires a value" >&2
                exit 2
            fi
            JOB_ID="$1"
            shift
            ;;
        --root)
            shift
            if [[ $# -eq 0 ]]; then
                echo "hermes-orchestrate: --root requires a path" >&2
                exit 2
            fi
            ROOT_DIR="$1"
            shift
            ;;
        --mode)
            shift
            if [[ $# -eq 0 ]]; then
                echo "hermes-orchestrate: --mode requires a value" >&2
                exit 2
            fi
            MODE="$1"
            shift
            ;;
        --trusted-local)
            TRUSTED_LOCAL="true"
            shift
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do
                if [[ -z "${MISSION}" ]]; then MISSION="$1"; else MISSION="${MISSION} $1"; fi
                shift
            done
            ;;
        -*)
            echo "hermes-orchestrate: unknown flag: $1" >&2
            echo "Run with --help for usage." >&2
            exit 2
            ;;
        *)
            if [[ -z "${MISSION}" ]]; then MISSION="$1"; else MISSION="${MISSION} $1"; fi
            shift
            ;;
    esac
done

# ---------------------------------------------------------------------
# Non-run actions
# ---------------------------------------------------------------------
case "${ACTION}" in
    help)
        usage
        exit 0
        ;;
    list)
        jobs_dir="${ROOT_DIR}/jobs"
        if [[ ! -d "${jobs_dir}" ]]; then
            echo "hermes-orchestrate: no jobs directory at ${jobs_dir}"
            exit 0
        fi
        found=0
        for d in "${jobs_dir}"/*/; do
            [[ -d "${d}" ]] || continue
            found=1
            printf '%s\n' "$(basename "${d}")"
        done
        if [[ ${found} -eq 0 ]]; then
            echo "hermes-orchestrate: no jobs found in ${jobs_dir}"
        fi
        exit 0
        ;;
    status)
        status_path="${ROOT_DIR}/jobs/${JOB_ID}/status.json"
        if [[ ! -f "${status_path}" ]]; then
            echo "hermes-orchestrate: no job '${JOB_ID}' under ${ROOT_DIR}/jobs/" >&2
            exit 1
        fi
        cat "${status_path}"
        exit 0
        ;;
esac

# ---------------------------------------------------------------------
# Run a new job (scaffold only — no external model tools invoked)
# ---------------------------------------------------------------------
if ! is_valid_mode "${MODE}"; then
    echo "hermes-orchestrate: invalid --mode '${MODE}'. Choose from: ${VALID_MODES[*]}" >&2
    exit 2
fi

if [[ -z "${MISSION}" ]]; then
    echo "hermes-orchestrate: a mission string is required (or pass --help)." >&2
    exit 2
fi

if [[ -z "${JOB_ID}" ]]; then
    JOB_ID="$(generate_job_id)"
fi

JOB_DIR="${ROOT_DIR}/jobs/${JOB_ID}"

if [[ -d "${JOB_DIR}" ]]; then
    echo "hermes-orchestrate: job '${JOB_ID}' already exists at ${JOB_DIR}" >&2
    exit 1
fi

mkdir -p "${JOB_DIR}"

now_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mission_json="$(printf '%s' "${MISSION}" | json_escape)"
mode_json="$(printf '%s' "${MODE}" | json_escape)"
job_id_json="$(printf '%s' "${JOB_ID}" | json_escape)"
created_json="$(printf '%s' "${now_utc}" | json_escape)"
phase_json="$(printf '%s' "${PHASE_TAG}" | json_escape)"
workers_json="$(HERMES_ORCH_LIST="$(printf '%s\n' "${WORKERS[@]}")" json_string_list)"

# job.json
write_file "${JOB_DIR}/job.json" <<EOF
{
  "job_id": ${job_id_json},
  "mode": ${mode_json},
  "mission": ${mission_json},
  "trusted_local": ${TRUSTED_LOCAL},
  "created_at": ${created_json},
  "phase": ${phase_json},
  "workers": ${workers_json}
}
EOF

# mission.md
write_file "${JOB_DIR}/mission.md" <<EOF
# Mission — ${JOB_ID}

- Mode: \`${MODE}\`
- Created (UTC): ${now_utc}
- Trusted local: ${TRUSTED_LOCAL}

## Mission

${MISSION}
EOF

# status.json
write_file "${JOB_DIR}/status.json" <<EOF
{
  "job_id": ${job_id_json},
  "mode": ${mode_json},
  "state": "scaffolded",
  "phase": ${phase_json},
  "current_stage": "research",
  "created_at": ${created_json},
  "updated_at": ${created_json},
  "workers": ${workers_json}
}
EOF

# decision-ledger.md
write_file "${JOB_DIR}/decision-ledger.md" <<EOF
# Decision ledger — ${JOB_ID}

Append-only log of orchestration decisions. Phase 03 seeds the first
entry; later phases append to it.

| Timestamp (UTC) | Actor | Decision | Rationale |
|---|---|---|---|
| ${now_utc} | orchestrator | scaffold-job | Created Phase 03 job folder contract for mode \`${MODE}\`. |
EOF

# queue.json — orchestrator dispatch queue (placeholder)
write_file "${JOB_DIR}/queue.json" <<EOF
{
  "job_id": ${job_id_json},
  "phase": ${phase_json},
  "version": 1,
  "pending": [],
  "in_flight": [],
  "completed": [],
  "failed": []
}
EOF

# checkpoints/ — append-only durable resume points (placeholder)
mkdir -p "${JOB_DIR}/checkpoints"
write_file "${JOB_DIR}/checkpoints/README.md" <<EOF
# Checkpoints — ${JOB_ID}

Append-only resume points for the orchestrator. Each checkpoint is a
single JSON file named \`<utc-timestamp>-<stage>.json\` that captures
enough state for a restart to pick up where the last run left off.

Phase 03 only creates this directory; the controller in a later phase
populates checkpoints as stages complete.
EOF

# shared-context/
write_file "${JOB_DIR}/shared-context/repo-map.md" <<EOF
# Repo map — ${JOB_ID}

Top-level layout of the repository scoped to what matters for this
mission. Populated by later phases.
EOF

write_file "${JOB_DIR}/shared-context/evidence.md" <<EOF
# Evidence — ${JOB_ID}

Files read, commands run, and observations gathered while working the
mission. Populated by later phases.
EOF

write_file "${JOB_DIR}/shared-context/constraints.md" <<EOF
# Constraints — ${JOB_ID}

Hard limits the orchestrator must respect (security, scope, branch,
do-not-touch paths). Populated by later phases.
EOF

write_file "${JOB_DIR}/shared-context/user-profile.md" <<EOF
# User profile — ${JOB_ID}

Style, formatting, tooling, and communication preferences carried over
from user history. Populated by later phases.
EOF

# tool-detection.json — what's actually installed on this host
write_file "${JOB_DIR}/shared-context/tool-detection.json" <<EOF
{
  "job_id": ${job_id_json},
  "phase": ${phase_json},
  "detected_at": null,
  "workers": {
    "hermes-local": {"available": null, "evidence": null},
    "claude-code-windows": {"available": null, "evidence": null},
    "codex": {"available": null, "evidence": null},
    "aider": {"available": null, "evidence": null},
    "goose": {"available": null, "evidence": null},
    "chatgpt-handoff": {"available": null, "evidence": null}
  }
}
EOF

# phases/ — one markdown file per stage of the pipeline
for stage in "${PHASE_FILES[@]}"; do
    write_file "${JOB_DIR}/phases/${stage}.md" <<EOF
# Stage: ${stage} — ${JOB_ID}

_Empty._ Phase 03 only scaffolds this file; the controller in a later
phase populates the ${stage} stage notes.
EOF
done

# workers/<worker>/...
for worker in "${WORKERS[@]}"; do
    worker_json="$(printf '%s' "${worker}" | json_escape)"

    write_file "${JOB_DIR}/workers/${worker}/prompt.md" <<EOF
# Prompt for ${worker} — ${JOB_ID}

- Mode: \`${MODE}\`
- Worker: \`${worker}\`

## Mission

${MISSION}

## Notes

Phase 03 only scaffolds this prompt; no worker is dispatched yet.
EOF

    write_file "${JOB_DIR}/workers/${worker}/output.md" <<EOF
# Output from ${worker} — ${JOB_ID}

_Empty._ Phase 03 only scaffolds this file; no worker has run yet.
EOF

    : >"${JOB_DIR}/workers/${worker}/patch.diff"

    write_file "${JOB_DIR}/workers/${worker}/status.json" <<EOF
{
  "worker": ${worker_json},
  "job_id": ${job_id_json},
  "state": "not_started",
  "phase": ${phase_json},
  "created_at": ${created_json},
  "updated_at": ${created_json}
}
EOF
done

# merge/
write_file "${JOB_DIR}/merge/council-review.md" <<EOF
# Council review — ${JOB_ID}

Synthesis of worker outputs with explicit agreements and disagreements.
Populated by later phases.
EOF

write_file "${JOB_DIR}/merge/scorecard.json" <<EOF
{
  "job_id": ${job_id_json},
  "phase": ${phase_json},
  "workers": ${workers_json},
  "scores": {}
}
EOF

write_file "${JOB_DIR}/merge/conflict-report.md" <<EOF
# Conflict report — ${JOB_ID}

Per-file conflicts between worker patches with the chosen resolution
strategy. Populated by later phases.
EOF

write_file "${JOB_DIR}/merge/final-plan.md" <<EOF
# Final plan — ${JOB_ID}

The merged plan that survives council review. Populated by later phases.
EOF

: >"${JOB_DIR}/merge/final-patch.diff"

# validation/ — local validation gate artifacts (tests, lint, smoke runs)
mkdir -p "${JOB_DIR}/validation"
write_file "${JOB_DIR}/validation/README.md" <<EOF
# Validation — ${JOB_ID}

Outputs from the local validation gates: test runs, lint/type checks,
smoke runs, and any task-specific checks pinned in the mission. The
controller writes one file per validator (\`pytest.txt\`, \`ruff.txt\`,
\`mypy.txt\`, ...) plus a \`summary.json\` that the publisher reads
before opening a PR.

Phase 03 only creates this directory.
EOF

# github/
write_file "${JOB_DIR}/github/branch.txt" <<EOF
hermes/${MODE}/${JOB_ID}
EOF

write_file "${JOB_DIR}/github/commit-message.txt" <<EOF
chore(orchestrator): scaffold job ${JOB_ID}

Phase 03 foundation only — no implementation yet.
EOF

write_file "${JOB_DIR}/github/pr-title.txt" <<EOF
[orchestrator] ${MODE}: ${JOB_ID}
EOF

write_file "${JOB_DIR}/github/pr-body.md" <<EOF
## Summary

Scaffolded by \`hermes-orchestrate.sh\` for job \`${JOB_ID}\` in mode
\`${MODE}\`. Phase 03 only emits the folder contract; the controller
that fills these artifacts runs in a later phase.

## Mission

${MISSION}

## Notes

- Worker outputs, council review, and final patch are still empty
  templates.
- Do not merge a PR generated from this template until later phases
  populate the \`merge/\` artifacts.
EOF

# deploy/ — post-publish deploy artifacts (release notes, deploy plan)
mkdir -p "${JOB_DIR}/deploy"
write_file "${JOB_DIR}/deploy/README.md" <<EOF
# Deploy — ${JOB_ID}

Post-publish deploy artifacts: release notes draft, rollout plan,
post-merge smoke checklist, and any environment-specific deploy
metadata. The publisher only reaches here when the PR has been merged
and the mission's \`publish\` stage is complete.

Phase 03 only creates this directory.
EOF

# logs/
mkdir -p "${JOB_DIR}/logs"
{
    printf '[%s] orchestrator: scaffold start (mode=%s, trusted_local=%s)\n' \
        "${now_utc}" "${MODE}" "${TRUSTED_LOCAL}"
    printf '[%s] orchestrator: created job folder %s\n' \
        "${now_utc}" "${JOB_DIR}"
    for worker in "${WORKERS[@]}"; do
        printf '[%s] orchestrator: registered worker %s (state=not_started)\n' \
            "${now_utc}" "${worker}"
    done
    printf '[%s] orchestrator: scaffold complete\n' "${now_utc}"
} >"${JOB_DIR}/logs/orchestrator.log"

echo "Job ${JOB_ID} scaffolded at ${JOB_DIR}"
echo "Mode: ${MODE}"
echo "Workers: ${WORKERS[*]}"
echo "Phase: ${PHASE_TAG} (no external model tools were invoked)"
