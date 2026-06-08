# Claude and Codex Handoff Workflow

This document defines the planned handoff workflow between Claude Code, Codex, Hermes, and MUSE. It is documentation only and does not change runtime behavior.

## Role Separation

Claude Code is the primary builder. Use Claude Code for implementation-heavy tasks, multi-file edits, refactors, and first-pass feature work when a scoped build packet exists.

Codex is the reviewer, bounded second pass, or narrow fix worker. Use Codex for contrarian code review, bug-focused patches, small corrections, test expansion, and implementation critique.

Hermes and MUSE coordinate the workflow, prepare packets, protect scope, run local verification, and produce the PR handoff.

## No Same-Branch Editing Conflict

Do not let Claude Code and Codex edit the same branch at the same time. One worker owns the branch at a time.

Safe patterns:

- Claude Code builds, commits or hands off, then Codex reviews.
- Codex reviews without editing, then returns findings.
- Codex applies a bounded fix after Claude Code is stopped and the file scope is explicit.
- Separate worktrees or branches are used when parallel implementation is truly needed.

Unsafe patterns:

- Two agents editing the same files simultaneously.
- Review and implementation happening without a clean diff boundary.
- A worker changing files outside the packet without owner approval.

## Build Packet Template

Use this packet before sending implementation work to Claude Code.

```text
BUILD PACKET
Repo:
Branch:
Goal:
Allowed files:
Disallowed files:
Non-goals:
Existing context:
Acceptance criteria:
Verification commands:
Owner gates:
Rollback plan:
Expected handoff:
```

Build packet requirements:

- State the exact repo and branch.
- List allowed and disallowed files.
- Name protected files, secrets, runtime boundaries, and non-goals.
- Include acceptance criteria before implementation starts.
- Include verification commands or explain why none apply.

## Review Packet Template

Use this packet before sending review work to Codex.

```text
REVIEW PACKET
Repo:
Branch:
Commit or diff under review:
Files to inspect:
Review goals:
Out of scope:
Known risks:
Verification already run:
Requested output:
Owner gates:
```

Review packet requirements:

- Review the diff, not the whole universe.
- Ask for severity-ranked findings.
- Distinguish blocking issues from nice-to-have improvements.
- Require evidence such as file paths, line references, command output, or reproducible reasoning.

## Local Verification

Hermes should run local verification after worker output when tools are available. Verification can include:

- targeted unit tests;
- lint or type checks;
- script execution;
- `git diff --check` for whitespace;
- focused content checks;
- changed-file and staged-file boundary checks.

If verification cannot run, the handoff must say why and list the unverified risk.

## PR Handoff Summary

Every PR handoff should include:

- summary;
- files changed;
- commits included;
- verification commands and results;
- non-goals;
- remaining risks;
- rollback plan;
- follow-up work.

## Rollback Plan

For documentation-only work, rollback is usually a revert commit or targeted file restoration. For runtime changes, the rollback plan must identify the exact commit, feature flag, config change, or file path to revert.

Do not merge, force-push, deploy, publish, or delete recovered sources unless owner approval explicitly allows that stage.
