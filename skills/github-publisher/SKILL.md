---
name: github-publisher
description: Safely prepare, validate, commit, push, and open GitHub pull requests from Hermes jobs.
---

# GitHub Publisher

## Purpose

Use this skill when a Hermes job needs to publish work to GitHub. It turns validated local changes into a branch, commit, push, and pull request while keeping the workflow reversible.

## Required Checks Before Publishing

Run or request equivalent checks:

```bash
git status --short
git branch --show-current
git diff --check
git diff --stat
git diff --name-only
```

Run a secret scan before commit:

```bash
git diff --cached -- . ':!.env' | grep -Ei 'api[_-]?key|secret|token|password|bearer|private[_-]?key' || true
git diff -- . ':!.env' | grep -Ei 'api[_-]?key|secret|token|password|bearer|private[_-]?key' || true
```

Block publishing if `.env`, private keys, generated credentials, or obvious secrets are staged.

## Branch Policy

Use branch-per-job:

```text
hermes/<job-id>
```

If the branch exists, ask whether to resume it or create a new suffix.

## Commit Policy

Commit only intentional files. Exclude:

- `.env`
- secret files
- local logs unless explicitly requested
- generated build directories
- APK binaries unless release packaging is explicitly requested
- worker scratch outputs unless they are documentation deliverables

## PR Body Template

```markdown
## Summary
- 

## Hermes Job
- Job ID: 
- Job folder: 

## Changes
- 

## Validation
- [ ] 

## Risk / Rollback
- Risk level: 
- Rollback: revert this PR or reset branch `...`

## Worker Inputs
- Hermes Local:
- Codex:
- Claude Code:
- Aider:
- ChatGPT handoff:
```

## Approval Gates

For private local mode:

- Auto-allow branch creation.
- Auto-allow local commit when validation passed and no secrets are present.
- Ask before push unless the user already approved publishing.
- Ask before opening PR unless the user already approved publishing.
- Never force-push without explicit approval.
- Never merge automatically unless explicitly requested.

## Output Format

- Current repo
- Current branch
- Files changed
- Validation results
- Secret scan result
- Proposed branch
- Commit message
- PR title/body
- Publish approval needed
