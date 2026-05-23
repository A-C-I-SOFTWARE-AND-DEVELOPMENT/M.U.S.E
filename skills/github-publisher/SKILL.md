---
name: github-publisher
description: "Promote a Hermes orchestration job's github/ artifacts (branch, commit message, PR title, PR body) into a real branch and pull request. Phase-02-aware: the artifacts exist but must not be pushed until later phases populate merge/."
version: 0.2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [orchestration, github, publishing, pr, private-local]
    related_skills:
      - hermes-orchestration-pipeline
      - aos-full-agent-team
      - model-router
      - decision-quality-gate
      - developer-ux-command-center
      - self-improvement-loop
      - best-coding-tool-mission
    related_docs:
      - docs/orchestration/hermes-orchestration-pipeline.md
      - docs/orchestration/decision-ledger.md
      - docs/orchestration/self-improvement-loop.md
      - docs/github-integration.md
---

# GitHub publisher

This skill turns a job's `github/` folder into a branch + draft PR. It
is the bridge between the orchestration pipeline and the GitHub plugin
documented at `docs/github-integration.md`.

## Phase-02 reality check

In Phase 02, `scripts/hermes-orchestrate.sh` emits four files under
every job's `github/` folder with templated content:

```
.hermes-orchestrator/jobs/<job-id>/github/
├── branch.txt              # default: hermes/<mode>/<job-id>
├── commit-message.txt
├── pr-title.txt
└── pr-body.md
```

These are **scaffold templates only**. The `pr-body.md` explicitly
warns "do not merge a PR generated from this template until later
phases populate the merge/ artifacts." Respect that warning. In
particular, do not:

- push the branch named in `branch.txt`,
- run `git commit -F github/commit-message.txt`,
- call `mcp__github__create_pull_request` with `github/pr-title.txt`
  and `github/pr-body.md`.

When the controller exists in the next phase, this skill will own the
push + PR creation flow described below.

## Future workflow (informative, not active in Phase 02)

When `merge/final-patch.diff` and `merge/final-plan.md` carry real
content, the publish path is:

1. **Sanity-check the job folder.** Required: a non-empty
   `merge/final-patch.diff`, a populated `merge/final-plan.md`, and
   all four files under `github/`.
2. **Apply the patch on a fresh branch.**
   ```bash
   branch="$(cat .hermes-orchestrator/jobs/<id>/github/branch.txt)"
   git switch -c "${branch}"
   git apply .hermes-orchestrator/jobs/<id>/merge/final-patch.diff
   ```
3. **Commit using the scaffolded message.**
   ```bash
   git commit -F .hermes-orchestrator/jobs/<id>/github/commit-message.txt
   ```
4. **Push the branch with upstream tracking.**
   ```bash
   git push -u origin "${branch}"
   ```
   On network errors, retry up to 4 times with exponential backoff
   (2s, 4s, 8s, 16s) — same policy the rest of the project uses.
5. **Open a draft PR via the GitHub MCP server.** Use
   `mcp__github__create_pull_request` with:
   - `title` = contents of `github/pr-title.txt`
   - `body` = contents of `github/pr-body.md`
   - `draft` = `true`
   - `base` = the repo's default branch unless the job's
     `constraints.md` says otherwise
6. **Record the PR URL** by appending a row to `decision-ledger.md`
   and updating `status.json` to `state: "published"`.

The native GitHub plugin (`plugins/github_assistant/`) covers the same
ground for users who prefer Hermes tools over MCP; the choice is the
user's, documented in `docs/github-integration.md`.

## Why a draft, always

- Phase-02 templates ship with a warning banner; making the PR draft
  by default prevents anyone from merging a scaffold by accident.
- The user expects to review the council synthesis before the PR
  flips to ready-for-review. The draft state is the natural pause
  point.

## Safety rails carried over from `github-integration.md`

- Never push to `main` / `master` directly. Always create the branch
  named in `branch.txt`.
- Never force-push from this skill. If a branch already exists, fail
  loud and surface the existing branch to the user.
- Never pass the GitHub PAT into the prompt. The plugin / MCP server
  reads it from the environment; the skill never sees it.
- Never bypass `pre-commit` hooks with `--no-verify`. If a hook fails,
  the council review missed something — surface the failure.

## What this skill never does

- It never runs in Phase 02. The artifacts are scaffolds; pushing them
  would create empty branches and misleading PRs.
- It never edits `merge/final-patch.diff` or `merge/final-plan.md`.
  Those come from council synthesis. The publisher only consumes
  them.
- It never invents a branch name. If `branch.txt` is missing or
  empty, fail and tell the user the orchestrator scaffolded a broken
  job.

## Where this fits in the larger system

`github-publisher` is the **publication channel** for the whole
orchestration stack. It does not decide *what* to publish — it
consumes artifacts produced by upstream skills:

- The job folder contract comes from
  [`hermes-orchestration-pipeline`](../hermes-orchestration-pipeline/SKILL.md).
- The worker / model that produced the patch was picked by
  [`model-router`](../model-router/SKILL.md) (registry:
  [`docs/ai-intelligence/model-registry.yaml`](../../docs/ai-intelligence/model-registry.yaml)).
- The decision to publish at all is gated by
  [`decision-quality-gate`](../decision-quality-gate/SKILL.md), which
  appends a row to `decision-ledger.md` (template:
  [`docs/orchestration/decision-ledger.md`](../../docs/orchestration/decision-ledger.md)).
- The publish is recorded with its **undo path** by
  [`best-coding-tool-mission`](../best-coding-tool-mission/SKILL.md)'s
  reversibility rules (Principle 7) — see `publish.md` in the job
  folder.
- After the publish, [`self-improvement-loop`](../self-improvement-loop/SKILL.md)
  records the outcome and feeds the scorecard back into routing.

## Posture: private and local-first

The publisher inherits the same posture as the rest of the pipeline:

- The PAT is read from the environment by the
  [`github_assistant` plugin](../../plugins/github_assistant/) — the
  skill never sees it and never logs it.
- Writes are gated by `github.allow_writes: true` and the repo
  allowlist in `~/.hermes/config.yaml`.
- The Android APK cockpit can trigger this skill but never bypasses
  the gates — the cockpit drives the same on-disk contract the CLI
  uses (see [`docs/hermes-local-orchestrator.md`](../../docs/hermes-local-orchestrator.md)).

## How to invoke

```text
/reload-skills                              # after editing skills
/github-publisher <job-id>                  # publish a job's github/* artifacts
/hermes-orchestration-pipeline <job-id>     # upstream: scaffold + drive a job
/decision-quality-gate <decision-id>        # upstream: gate the publish decision
```
