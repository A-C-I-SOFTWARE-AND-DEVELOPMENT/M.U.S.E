---
name: hermes-orchestration-pipeline
description: Run a prompt-first, local-first multi-worker development pipeline from inside Hermes.
---

# Hermes Orchestration Pipeline

## Purpose

Use this skill when the user wants Hermes to turn one prompt into a full local development workflow: classify the task, choose the best worker mix, create a job folder, prepare prompts, run available official local tools, collect outputs, score quality, merge the best work, validate locally, and prepare GitHub publishing.

Hermes is the command center. External tools such as Codex CLI, Claude Code, Aider, Goose, GitHub CLI, or ChatGPT handoff are workers. Do not let any worker become the source of truth until Hermes has reviewed and validated its output.

## Operating Principle

Every prompt becomes a job. Every job has a folder. Every worker has a folder. Every output is scored. Every merge is validated. Every publish is reversible.

## Job Folder Contract

Create jobs under:

```text
.hermes-orchestrator/jobs/<job-id>/
```

Recommended structure:

```text
.hermes-orchestrator/jobs/<job-id>/
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
      prompt.md
      output.md
      patch.diff
      status.json
    codex/
      prompt.md
      output.md
      patch.diff
      status.json
    claude-code/
      prompt.md
      output.md
      patch.diff
      status.json
    aider/
      prompt.md
      output.md
      patch.diff
      status.json
    goose/
      prompt.md
      output.md
      status.json
    chatgpt-handoff/
      prompt.md
      output.md
      status.json
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

## Required Workflow

1. Mission brief
   - Restate the user's objective.
   - Classify the task type: audit, build, debug, refactor, architecture, release, documentation, Android/APK, Termux, GitHub PR, or mixed.
   - Identify expected deliverables.

2. Evidence bundle
   - Inspect the repository before making claims.
   - Build `shared-context/repo-map.md` and `shared-context/evidence.md`.
   - Record current branch, dirty state, test commands, package managers, app entry points, and docs.

3. Worker routing
   - Use Hermes Local for evidence, local file operations, tests, validation, Git, and GitHub publishing.
   - Use Codex for implementation-heavy coding tasks when official Codex tooling is detected.
   - Use Claude Code for architecture, cross-file reasoning, refactor plans, code review, and high-risk design decisions when official Claude Code tooling is detected.
   - Use Aider for git-native patching, repo-map-assisted edits, lint/test repair loops, and tight local implementation loops when installed.
   - Use Goose for local desktop/CLI agent workflows, extension-driven work, and provider experiments when installed.
   - Use ChatGPT handoff for product thinking, writing, prompt refinement, launch copy, and high-level review when no direct official local automation is available.

4. Prompt generation
   - Write a `prompt.md` for each selected worker.
   - Include mission, repo evidence, constraints, exact deliverables, files to inspect, files likely to edit, validation commands, and what not to change.
   - Avoid sending every worker the same vague prompt. Route the correct slice of the work to the correct worker.

5. Parallel execution
   - Prefer isolated folders or git worktrees for workers that edit code.
   - If a worker cannot be executed automatically, create a copy/paste handoff prompt and mark `status.json` as `handoff-required`.
   - Do not pretend to control subscription apps through unsupported automation.

6. Collection and scoring
   - Collect each worker's output, patch, changed-file list, test output, and self-review.
   - Score outputs using correctness, completeness, testability, maintainability, repo fit, risk, UX quality, and Jeremiah-fit.

7. Merge loop
   - Compare worker outputs.
   - Detect conflicts.
   - Keep the best ideas and reject weak or unsafe changes.
   - Produce `merge/council-review.md`, `merge/conflict-report.md`, and `merge/final-plan.md`.

8. Validation
   - Run the smallest useful checks first.
   - Prefer existing project commands from README, AGENTS.md, pyproject, package.json, Gradle files, or docs.
   - Run secret scans before commit.
   - Record validation results in the job folder.

9. GitHub publishing
   - Create or use a branch per job.
   - Commit only validated, intentional files.
   - Prepare a PR title/body.
   - Require explicit approval before push or PR creation unless the user has already granted that approval.

10. Retrospective
   - Record what worked, which worker performed best, what failed, and what Hermes should remember next time.

## Output Format

When invoked, produce:

- Executive verdict
- Task classification
- Available local tools
- Selected workers
- Job folder path
- Evidence reviewed
- Worker prompt plan
- Merge/quality plan
- Validation commands
- GitHub publish plan
- Risks and rollback notes

## Quality Scorecard

Score worker outputs from 0 to 10:

```json
{
  "correctness": 0,
  "completeness": 0,
  "testability": 0,
  "maintainability": 0,
  "repo_fit": 0,
  "risk_control": 0,
  "ux_quality": 0,
  "jeremiah_fit": 0
}
```

## Private Local Mode

For Jeremiah's private local workflow, use `trusted_local` posture:

- Reduce friction around public auth, multi-tenant isolation, RBAC, and enterprise SaaS controls.
- Keep self-protection: branch-per-job, checkpoints, command logs, secret scan before commit, destructive command approval, and rollback notes.
- Never commit `.env` or secrets.
- Never force-push unless explicitly approved.

## UX Requirement

The product experience should feel like a developer command center:

- One prompt starts a job.
- The user can see active workers, statuses, logs, patches, validation, and GitHub publish state.
- Every step has a visible artifact in the job folder.
- The Android APK should be a cockpit for the Hermes backend, not a replacement for the backend.
