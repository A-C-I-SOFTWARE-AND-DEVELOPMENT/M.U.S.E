---
name: implementation-workflow
description: Safe repo inspection, scoped editing, implementation, validation, and reporting. The default workflow for any code-bearing task. Use when the request is to actually change code in the current repo.
---

# Implementation Workflow

## Use when

- The request is to write or change production code.
- A plan or design from another agent needs to be turned into a diff.

## Procedure

### 1. Inspect

- Read every file you intend to change and its immediate neighbors.
- Read `package.json` / `pyproject.toml` / equivalent for scripts and deps.
- Read any `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `.editorconfig`.
- Identify the existing pattern for the change (state, errors, styling,
  data access) and follow it.

### 2. Plan (one paragraph, in chat)

State the goal, the files you will touch, the public API changes (if any),
the validation you will run, and the rollback path.

### 3. Edit (scoped)

- Touch only files the task requires.
- No new dependencies unless required; justify if added.
- No drive-by refactors. No speculative abstractions.
- No comments explaining WHAT; only WHY when non-obvious.

### 4. Validate (mandatory before "done")

Run, in order:

1. Install / lockfile check.
2. Typecheck.
3. Lint.
4. Tests.
5. Build.

Capture exit code and the last ~20 lines of output for each.

### 5. Report

```
## Task
## Files read
## Files changed (path + one-line reason)
## Diff summary
## Validation
- install: <cmd> → <result>
- typecheck: ...
- lint: ...
- tests: ...
- build: ...
## Limitations / skipped checks (with reason)
## Owner-only follow-ups
```

## Hard rules

- No edits to files not yet read.
- No "done" without validation evidence.
- No bypassing pre-commit hooks unless the owner explicitly instructed.
- No invented file paths, function names, or imports.
- Secrets stay in env vars; never in source.
