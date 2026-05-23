---
name: model-router
description: Classify development prompts and select the best local, CLI, and handoff workers for Hermes orchestration.
---

# Model Router

## Purpose

Use this skill to decide which models, CLIs, tools, and local workers should handle a Hermes job. The goal is high-quality output with minimal wasted work.

Do not send the same full prompt to every worker. Split the work by strength.

## Inputs

Collect or infer:

- User objective
- Repository path and type
- Task category
- Risk level
- Time sensitivity
- Required artifacts
- Available local tools
- Existing tests and validation commands
- Whether GitHub publishing is requested

## Tool Detection

Prefer checking with local commands:

```bash
command -v git || true
command -v gh || true
command -v python || true
command -v node || true
command -v npm || true
command -v pnpm || true
command -v uv || true
command -v codex || true
command -v claude || true
command -v aider || true
command -v goose || true
command -v termux-info || true
command -v termux-wake-lock || true
```

## Task Classification

Classify the task as one or more of:

- `audit`
- `architecture`
- `build`
- `debug`
- `refactor`
- `release`
- `documentation`
- `android-apk`
- `termux-local`
- `github-publish`
- `product-ux`
- `security-risk`
- `research`

## Routing Rules

### Hermes Local

Always include Hermes Local for:

- Repo evidence
- File inspection
- Terminal commands
- Test execution
- Git status/diff
- Secret scan
- Final validation
- GitHub publish preparation

### Codex

Use Codex when the task is:

- implementation-heavy
- file-edit heavy
- test-repair oriented
- straightforward bug fixing
- API wiring
- UI component implementation

Route Codex narrow tasks with clear files, acceptance criteria, and validation commands.

### Claude Code

Use Claude Code when the task requires:

- architecture review
- multi-file reasoning
- risk review
- complex refactor planning
- design critique
- correctness review
- final code review

### Aider

Use Aider when the task benefits from:

- git-native local patching
- repo-map guided edits
- iterative lint/test repair
- small-to-medium implementation loops

### Goose

Use Goose when the task benefits from:

- local desktop/CLI agent workflow
- extensions
- provider experiments
- local command automation
- recipe-style repeatability

### ChatGPT Handoff

Use ChatGPT handoff for:

- high-level product thinking
- UX critique
- launch messaging
- prompt refinement
- strategy
- comparison reports
- non-code writing

If there is no official local automation path, write a handoff prompt and mark the worker as `handoff-required`.

## Risk Rules

For high-risk work, always include:

- Hermes Local evidence
- Assurance/Risk review
- Contrarian review
- Validation commands
- Rollback notes
- GitHub publish approval gate

High-risk signals include:

- auth
- secrets
- payments
- destructive commands
- filesystem-wide operations
- public deployment
- APK permissions
- background services
- GitHub push/merge

## Output Format

Return:

- Task classification
- Available tools detected
- Selected workers
- Worker rationale
- Worker prompts to create
- Expected artifacts
- Validation commands
- GitHub approval requirements
