---
name: codex-claude-synergy-workflow
description: One-prompt workflow that coordinates Claude Code and Codex (or any second coder) — planner, implementer, verifier — with handoffs, verification, and merge gates. Use when a change is large enough that planning, implementing, and verifying should be different sessions.
---

# Codex ⇄ Claude Synergy Workflow

## Use when

- The owner wants "Claude + Codex" or "two AI coders" on one change.
- A previous solo run drifted from plan or rubber-stamped a broken change.
- A change is large enough that separation of roles is worth the overhead.

## Roles

1. **Planner** (Claude, this skill) — produces the Task Packet.
2. **Implementer** (Codex or a different Claude session) — executes the
   packet, returns the Return Envelope.
3. **Verifier** (a different session from planner and implementer) —
   re-runs the validation, cross-checks the envelope, approves or rejects.
4. **Owner** — merges only on verifier approval.

## Task Packet schema (planner produces)

```
goal: <one sentence>
branch: <branch name>
files_allowed: [<paths>]
files_forbidden: [<paths>]
acceptance_criteria:
  - <executable check 1>
  - <executable check 2>
validation_commands:
  - install: <cmd>
  - typecheck: <cmd>
  - lint: <cmd>
  - test: <cmd>
  - build: <cmd>
rollback_plan: <how to undo>
```

## Return Envelope schema (implementer produces)

```
files_changed: [<paths>]   # must be subset of files_allowed
diff: <patch or summary>
validation_results:
  - install: <exit code, last lines>
  - typecheck: ...
  - lint: ...
  - test: ...
  - build: ...
acceptance_checklist:
  - <criterion>: <pass/fail with evidence>
unresolved: [<items needing planner re-issue>]
```

## Verifier procedure

1. Confirm `files_changed ⊆ files_allowed`. If not, REJECT.
2. Re-run every validation command locally. Do not trust reported exit
   codes.
3. Walk acceptance criteria; each must have evidence.
4. APPROVE, REQUEST_CHANGE (with specific items), or REJECT (with reason).

## Output

```
## Goal
## Roles assigned
## Planner prompt (copy/paste)
\`\`\`
<planner prompt>
\`\`\`

## Implementer prompt (copy/paste)
\`\`\`
<implementer prompt, with Task Packet schema and the actual packet>
\`\`\`

## Verifier prompt (copy/paste)
\`\`\`
<verifier prompt, with Return Envelope schema>
\`\`\`

## Owner checklist before merge
- [ ] Verifier APPROVED
- [ ] CI green on the branch
- [ ] Rollback plan documented in PR body
```

## Hard rules

- Planner and verifier MUST be different sessions.
- Implementer MUST NOT touch files outside `files_allowed`.
- Verifier MUST re-execute validation commands.
- No step is "done" without evidence the next step can consume.
