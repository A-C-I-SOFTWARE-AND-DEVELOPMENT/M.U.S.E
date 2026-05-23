#!/usr/bin/env bash
# Hermes orchestrator entry point.
#
# Fans out 6 workers in parallel via sandboxed git worktrees, scores their
# proposals, runs the 5 validation gates, and emits a publishable
# artifact under .hermes/publish/.
#
# This wrapper is intentionally thin — the policy lives in
# hermes_cli/orchestrator.py so it can be tested. The script's job is to
# normalize the invocation surface and fail loudly if the environment is
# misconfigured.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: hermes-orchestrate.sh [--task FILE | --prompt TEXT] [--repo PATH]
                              [--out DIR] [--publish (dry-run|live)]

Options:
  --task FILE         JSON file with {title, prompt, metadata?}.
  --prompt TEXT       Inline prompt (used when --task is omitted).
  --repo PATH         Repository root (default: current working directory).
  --out DIR           Output directory (default: <repo>/.hermes/runs).
  --publish MODE      dry-run (default) or live. Live also requires
                      HERMES_PUBLISH_LIVE=1 in the environment.
  -h, --help          Show this help and exit.

Exit codes:
  0   success — at least one proposal passed all gates.
  2   bad invocation (missing/conflicting flags).
  3   environment problem (python or git missing, repo not found).
  4   no proposal passed all gates.
EOF
}

# --- argument parsing -------------------------------------------------
TASK_FILE=""
PROMPT_TEXT=""
REPO_ROOT="$(pwd)"
OUT_DIR=""
PUBLISH_MODE="dry-run"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task)    TASK_FILE="${2:-}"; shift 2 ;;
    --prompt)  PROMPT_TEXT="${2:-}"; shift 2 ;;
    --repo)    REPO_ROOT="${2:-}"; shift 2 ;;
    --out)     OUT_DIR="${2:-}"; shift 2 ;;
    --publish) PUBLISH_MODE="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)         echo "unknown flag: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -n "${TASK_FILE}" && -n "${PROMPT_TEXT}" ]]; then
  echo "use --task OR --prompt, not both" >&2
  exit 2
fi

if [[ -z "${TASK_FILE}" && -z "${PROMPT_TEXT}" ]]; then
  echo "must provide --task or --prompt" >&2
  exit 2
fi

if [[ ! -d "${REPO_ROOT}" ]]; then
  echo "repo path not a directory: ${REPO_ROOT}" >&2
  exit 3
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not on PATH" >&2
  exit 3
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git not on PATH; orchestrator falls back to copy-mode but warns" >&2
fi

case "${PUBLISH_MODE}" in
  dry-run|live) ;;
  *) echo "publish mode must be dry-run or live, got: ${PUBLISH_MODE}" >&2; exit 2 ;;
esac

if [[ "${PUBLISH_MODE}" == "live" && "${HERMES_PUBLISH_LIVE:-0}" != "1" ]]; then
  echo "live publish requested but HERMES_PUBLISH_LIVE!=1; staying dry-run" >&2
  PUBLISH_MODE="dry-run"
fi

if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR="${REPO_ROOT}/.hermes/runs"
fi
mkdir -p "${OUT_DIR}"

# --- driver ----------------------------------------------------------
PY_SCRIPT=$(cat <<'PYEOF'
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["HERMES_REPO_ROOT"])

from hermes_cli.arbiter import decide
from hermes_cli.github_publisher import publish
from hermes_cli.merge_engine import merge
from hermes_cli.orchestrator import Orchestrator, Task, make_task, write_result
from hermes_cli.scoring import rank
from hermes_cli.validation_gates import run_gates

repo_root = Path(os.environ["HERMES_REPO_ROOT"]).resolve()
out_dir = Path(os.environ["HERMES_OUT_DIR"]).resolve()
publish_mode = os.environ["HERMES_PUBLISH_MODE"]
task_file = os.environ.get("HERMES_TASK_FILE", "")
prompt_text = os.environ.get("HERMES_PROMPT", "")

if task_file:
    spec = json.loads(Path(task_file).read_text())
    task = Task(
        task_id=spec.get("task_id") or os.urandom(6).hex(),
        title=spec.get("title") or spec.get("prompt", "")[:80],
        prompt=spec.get("prompt", ""),
        repo_root=repo_root,
        metadata=spec.get("metadata", {}),
    )
else:
    task = make_task(prompt_text, repo_root=repo_root)

orchestrator = Orchestrator(repo_root=repo_root)
result = orchestrator.run(task)
orchestrator.cleanup()

run_path = out_dir / f"run-{task.task_id}.json"
write_result(result, run_path)

decision = decide(result.proposals)
artifact = merge(decision, task_title=task.title)
report = run_gates(artifact)

(out_dir / f"gates-{task.task_id}.json").write_text(
    json.dumps(report.to_dict(), indent=2, sort_keys=True)
)

if not report.passed:
    print(json.dumps({"status": "rejected", "gates": report.to_dict()}, indent=2))
    sys.exit(4)

publish_out = repo_root / ".hermes" / "publish"
result_pub = publish(
    artifact,
    report,
    repo=os.environ.get("HERMES_REPO_SLUG", "local/dry-run"),
    out_dir=publish_out,
    dry_run=(publish_mode == "dry-run"),
)
print(json.dumps({
    "status": "ok",
    "run": str(run_path),
    "publish": result_pub.to_dict(),
    "ranked": [{"worker": r.worker_name, "score": s.total} for r, s in rank(result.proposals)],
}, indent=2))
PYEOF
)

export HERMES_REPO_ROOT="${REPO_ROOT}"
export HERMES_OUT_DIR="${OUT_DIR}"
export HERMES_PUBLISH_MODE="${PUBLISH_MODE}"
export HERMES_TASK_FILE="${TASK_FILE}"
export HERMES_PROMPT="${PROMPT_TEXT}"

python3 -c "${PY_SCRIPT}"
