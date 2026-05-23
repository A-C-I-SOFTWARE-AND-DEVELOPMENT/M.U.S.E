---
name: github-publisher
description: "Promote a Hermes orchestration job's github/ artifacts (branch, commit message, PR title, PR body) into a real branch and pull request. Phase-03-aware: the artifacts exist but must not be pushed until later phases populate merge/, validation/, and deploy/."
version: 0.3.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [orchestration, github, publishing, pr]
    related_skills:
      - hermes-orchestration-pipeline
      - model-router
      - developer-ux-command-center
---

# GitHub publisher

This skill turns a job's `github/` folder into a branch + draft PR. It
is the bridge between the orchestration pipeline and the GitHub plugin
documented at `docs/github-integration.md`.

## Phase-03 reality check

In Phase 03, `scripts/hermes-orchestrate.sh` emits four files under
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

## Future workflow (informative, not active in Phase 03)

When `merge/final-patch.diff`, `merge/final-plan.md`, and the local
validation gates in `validation/` carry real content, the publish
path is:

1. **Sanity-check the job folder.** Required: a non-empty
   `merge/final-patch.diff`, a populated `merge/final-plan.md`, a
   passing `validation/summary.json`, and all four files under
   `github/`.
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
7. **Write deploy artifacts** (release notes draft, rollout plan,
   post-merge smoke checklist) into `deploy/`. The publisher only
   reaches this step after the PR is merged and the `publish` stage
   is complete.

The native GitHub plugin (`plugins/github_assistant/`) covers the same
ground for users who prefer Hermes tools over MCP; the choice is the
user's, documented in `docs/github-integration.md`.

## Why a draft, always

- Phase-03 templates ship with a warning banner; making the PR draft
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

- It never runs in Phase 03. The artifacts are scaffolds; pushing them
  would create empty branches and misleading PRs.
- It never edits `merge/final-patch.diff` or `merge/final-plan.md`.
  Those come from council synthesis. The publisher only consumes
  them.
- It never invents a branch name. If `branch.txt` is missing or
  empty, fail and tell the user the orchestrator scaffolded a broken
  job.
