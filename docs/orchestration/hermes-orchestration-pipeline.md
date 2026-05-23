# Hermes Orchestration Pipeline

## Executive Summary

The Hermes Orchestration Pipeline turns Hermes into a prompt-first local development command center.

Instead of asking the user to manually choose every model, tool, or workflow, Hermes should:

1. Accept one prompt.
2. Classify the job.
3. Detect available local tools.
4. Create a durable job folder.
5. Generate worker-specific prompts.
6. Run or hand off to available official workers.
7. Collect outputs.
8. Score and merge results.
9. Validate locally.
10. Prepare GitHub publishing.

The design is local-first and private-workflow friendly. It minimizes public/SaaS friction while keeping self-protection controls that matter for autonomous local tooling.

## Competitive Feature Targets

Hermes should combine the developer-loved parts of leading agentic coding products:

| Pattern | Hermes Implementation |
| --- | --- |
| Local GUI/API cockpit | Android APK and TUI control Hermes backend jobs |
| CLI parity | `hermes`, `hermes --tui`, gateway, and script flows share artifacts |
| Repo map | `shared-context/repo-map.md` per job |
| Git-native edits | branch-per-job and optional worker worktrees |
| Model routing | `model-router` skill chooses the best worker mix |
| Worker adapters | Codex, Claude Code, Aider, Goose, Hermes Local, ChatGPT handoff |
| Markdown checks | `.hermes/checks/*.md` quality gates in a later phase |
| Skills/prompt library | Hermes skills become slash-invocable workflows |
| Provider setup | APK/TUI should show detected tools and missing setup |
| Always-on loop | Hermes gateway/cron can resume jobs and notify the user |

## Current Hermes Primitives

Hermes already has the key primitives needed for this feature:

- Toolsets for terminal, process, file operations, memory, session search, code execution, delegation, cron, and kanban.
- A skill system that turns `SKILL.md` files into slash-invocable prompt workflows.
- A central command registry that can expose future `/orchestrate` commands.
- TUI, CLI, gateway, and messaging surfaces.
- Existing background, queue, goal, kanban, cron, and gateway capabilities.

The first implementation therefore uses skills, docs, and a bootstrap script instead of invasive core changes.

## Job Folder Contract

Every prompt becomes a job under:

```text
.hermes-orchestrator/jobs/<job-id>/
```

Each job contains:

```text
job.json
mission.md
status.json
shared-context/
  repo-map.md
  evidence.md
  constraints.md
  user-preferences.md
workers/
  hermes-local/
  codex/
  claude-code/
  aider/
  goose/
  chatgpt-handoff/
merge/
  council-review.md
  scorecard.json
  conflict-report.md
  final-plan.md
  final-patch.diff
github/
  branch.txt
  commit-message.txt
  pr-title.txt
  pr-body.md
logs/
  orchestrator.log
```

## Worker Roles

### Hermes Local

Always included. Responsible for repo inspection, local command execution, test validation, Git state, secret scan, and publishing preparation.

### Codex

Use for implementation-heavy code edits, test repair, feature wiring, and narrow coding packets when official local Codex tooling is installed and authenticated.

### Claude Code

Use for architecture, complex reasoning, refactor review, risk review, code review, and high-impact decisions when official Claude Code tooling is installed and authenticated.

### Aider

Use for git-native patching, repo-map guided edits, and tight lint/test loops when installed.

### Goose

Use for local CLI/desktop agent workflows, extension-driven experiments, and repeatable recipe-style automation when installed.

### ChatGPT Handoff

Use for product thinking, UX critique, writing, launch messaging, and prompt refinement when no official local automation path is available.

## Routing Rules

Use these routing defaults:

| Task Type | Primary Worker | Reviewer |
| --- | --- | --- |
| Fast code edit | Codex or Aider | Hermes Local |
| Complex architecture | Claude Code | Hermes Council |
| Android/APK workflow | Hermes Local | Claude Code |
| Termux/local setup | Hermes Local | Developer UX Command Center |
| Release or PR | Hermes Local + GitHub Publisher | Assurance/Risk |
| UX/product | ChatGPT Handoff + Developer UX | Hermes Council |
| Security/risk | Assurance/Risk | Contrarian Review |
| Documentation | Hermes Local or ChatGPT Handoff | Hermes Council |

## Local Tool Detection

`scripts/hermes-orchestrate.sh` detects:

```text
git
gh
python
node
npm
pnpm
uv
codex
claude
aider
goose
termux-info
termux-wake-lock
```

Detection results are written into `status.json`.

## Android APK UX

The Android APK should act as a cockpit for the Hermes backend, not as the entire agent runtime.

Recommended screens:

1. Prompt Command Center
2. Worker Dashboard
3. Job Folder Browser
4. Diff and Merge Review
5. Validation Gate
6. GitHub Publisher
7. Android / Termux Control Panel

### Prompt Command Center

Controls:

- Prompt input
- Mode selector: Plan, Audit, Build, Debug, Review, Publish
- Worker preset: Auto, Local Only, Full Parallel
- Repo selector
- Autonomy: Safe, Trusted Local, YOLO with warnings
- Run button
- Recent jobs

### Worker Dashboard

Each worker card should show:

- Status
- Current task
- Last log line
- Output artifact
- Patch size
- Quality score
- Retry / stop / open controls

### GitHub Publisher

Show:

- Current repo
- Current branch
- Files changed
- Secret scan status
- Validation status
- Commit message
- PR title/body
- Push/PR approval controls

## Private Local Mode

For Jeremiah's use case, Hermes should not over-optimize for public SaaS security. It should reduce friction around:

- multi-user RBAC
- enterprise SSO
- public auth flows
- multi-tenant isolation
- public webhook exposure

But it should keep local self-protection:

- branch-per-job
- checkpoints
- command logs
- secret scan before commit
- destructive command approval
- GitHub push approval
- rollback notes

Suggested posture:

```yaml
mode: trusted_local
autonomy: high
public_exposure: off
destructive_commands: approve
github_push: approve
secret_commit: block
force_push: block
```

## First-Pass Usage

Create a job folder:

```bash
scripts/hermes-orchestrate.sh "Audit this repo and prepare a local-first orchestration plan"
```

Then open Hermes and run:

```text
/hermes-orchestration-pipeline Continue the job in .hermes-orchestrator/jobs/<job-id>
```

Reload skills if needed:

```text
/reload-skills
```

## Future Slash Commands

A later core integration should add:

```text
/orchestrate <prompt>
/orchestrator status [job-id]
/orchestrator open <job-id>
/orchestrator resume <job-id>
/orchestrator publish <job-id>
```

Minimal implementation path:

1. Add `CommandDef` entries in `hermes_cli/commands.py`.
2. Add handlers in `cli.py`.
3. Optionally expose gateway handlers in `gateway/run.py`.
4. Move script logic into `hermes_cli/orchestrator.py`.
5. Add tests for job folder generation and command parsing.

## Validation Commands

Recommended checks after adding orchestration files:

```bash
python -m py_compile hermes_cli/*.py || true
bash -n scripts/hermes-orchestrate.sh
scripts/hermes-orchestrate.sh --help
scripts/hermes-orchestrate.sh "test orchestration job"
find .hermes-orchestrator/jobs -maxdepth 3 -type f | sort | head -100
```

## APK Audit Pack

When auditing an APK locally:

```bash
mkdir -p apk-audit
cp app-debug.apk apk-audit/
cd apk-audit
sha256sum app-debug.apk > sha256.txt
apktool d app-debug.apk -o decoded-apk
jadx -d jadx-out app-debug.apk
aapt dump badging app-debug.apk > badging.txt
aapt dump permissions app-debug.apk > permissions.txt
grep -R "http://" -n jadx-out decoded-apk || true
grep -R "API_KEY\|SECRET\|TOKEN\|PASSWORD\|Bearer" -n jadx-out decoded-apk || true
grep -R "android:exported=\"true\"" -n decoded-apk || true
grep -R "WebView\|addJavascriptInterface\|setJavaScriptEnabled" -n jadx-out || true
```

For Hermes APK specifically, verify:

- Foreground service support
- Termux intent support
- Backend status screen
- Job dashboard
- Worker dashboard
- GitHub publisher screen
- Logs screen
- Secret scan before push
- Wake-lock controls
- Start/stop/restart controls

## Roadmap

### Phase 1: Prompt/skill layer

- `hermes-orchestration-pipeline` skill
- `model-router` skill
- `github-publisher` skill
- `developer-ux-command-center` skill
- bootstrap script
- docs

### Phase 2: Core job controller

- `hermes_cli/orchestrator.py`
- job status commands
- worker adapter interface
- scorecard logic

### Phase 3: Worker adapters

- Codex adapter
- Claude Code adapter
- Aider adapter
- Goose adapter
- ChatGPT handoff adapter
- Hermes Local adapter

### Phase 4: UI/APK integration

- Prompt Command Center
- Worker Dashboard
- Job Folder Browser
- Validation Gate
- GitHub Publisher
- Termux Control Panel

### Phase 5: Quality engine

- `.hermes/checks/*.md`
- diff scoring
- regression checks
- UX checks
- private-local safety checks

## Definition of Done

Hermes is competitive when a developer can:

1. Open Hermes.
2. Enter one prompt.
3. Watch selected workers run.
4. Inspect evidence, diffs, and logs.
5. Approve a validated merge.
6. Push a GitHub PR.
7. Resume the job later from phone or desktop.
