---
name: developer-ux-command-center
description: Design and review Hermes UI/UX as a local developer command center for orchestration, Android, Termux, and GitHub workflows.
---

# Developer UX Command Center

## Purpose

Use this skill to design, audit, and improve Hermes UI/UX for local development. Hermes should feel like the best developer command center: one prompt launches work, active workers are visible, evidence is inspectable, diffs are understandable, validation is clear, and GitHub publishing is controlled.

## Product Thesis

Hermes is not just chat. Hermes is a cockpit for local autonomous development.

The user should always be able to answer:

- What is Hermes doing?
- Which worker is doing it?
- What files are being changed?
- What evidence was used?
- What tests passed or failed?
- What will be committed?
- How do I stop, approve, retry, or rollback?

## Core Screens

### 1. Prompt Command Center

Required elements:

- Primary prompt box
- Mode selector: Plan, Audit, Build, Debug, Review, Publish
- Worker preset: Auto, Local Only, Codex + Hermes, Claude Review, Full Parallel
- Repo selector
- Privacy/autonomy toggle: Safe, Trusted Local, YOLO with warnings
- Run button
- Recent jobs list

### 2. Worker Dashboard

Required elements:

- Worker cards for Hermes Local, Codex, Claude Code, Aider, Goose, ChatGPT Handoff, GitHub
- Status: idle, queued, running, blocked, needs handoff, failed, complete
- Current step
- Last log line
- Output artifact links
- Diff size
- Quality score
- Retry/stop/open controls

### 3. Job Folder Browser

Required elements:

- Mission
- Shared context
- Worker prompts
- Worker outputs
- Patches
- Logs
- Merge review
- Validation output
- GitHub PR body

### 4. Diff and Merge Review

Required elements:

- Changed file list
- Worker-by-worker comparison
- Conflict report
- Final selected patch
- Risk notes
- Accept/reject controls

### 5. Validation Gate

Required elements:

- Commands run
- Pass/fail status
- Test output
- Secret scan result
- APK/build result if applicable
- Manual QA checklist

### 6. GitHub Publisher

Required elements:

- Current repo
- Current branch
- New branch name
- Files to commit
- Commit message
- PR title
- PR body
- Push approval
- Open PR approval

### 7. Android / Termux Control Panel

Required elements:

- Backend status
- Termux package detection
- Wake lock status
- Hermes gateway status
- Local API URL
- Logs
- Start/stop/restart controls

## UX Rules

- Never hide worker state.
- Never make GitHub publishing feel automatic unless the user enabled trusted publishing.
- Every long-running job needs visible progress.
- Every blocking issue needs a single clear next action.
- Prefer artifact links over long walls of logs.
- Let the user inspect and copy every worker prompt.
- Keep phone UX thumb-friendly: large buttons, short status labels, collapsible detail panels.

## Output Format

When reviewing UI/UX, return:

- UX verdict
- Missing screens
- Missing controls
- Risky interactions
- Best next UI changes
- Android-specific improvements
- Acceptance criteria
- Manual QA checklist
