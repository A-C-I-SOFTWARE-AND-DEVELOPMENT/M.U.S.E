# Slack Mobile Command Policy

## Purpose

Slack is the mobile command layer for MUSE. It should let Jeremiah capture ideas, request focused planning, start build preparation, ask for critique, route reviews, and manage durable memory without requiring a desktop session.

This policy defines command patterns and safety expectations. It does not implement Slack runtime behavior by itself.

## Principles

1. Keep mobile responses short by default.
2. Convert rough speech into clean task packets.
3. Do not dump long code or diffs into mobile threads.
4. Do not run destructive commands from vague Slack input.
5. Route judgment through AOS Council when needed.
6. Route implementation through Claude Code or Codex workflows when focused.
7. Use memory only for durable facts, preferences, lessons, and project direction.
8. Require owner authorization for high-risk actions.

## Command Pattern

Use:

```text
MUSE <command>: <payload>
```

Commands:

- capture
- focused
- build
- critic
- strategy
- review
- remember
- forget
- correct

## MUSE Capture

Purpose:
Capture rough ideas while Jeremiah is moving.

Command:

```text
MUSE capture: <raw idea>
```

Expected mode:
Mobile Voice Mode.

Expected response:

```text
Captured idea:
Clean task title:
Short summary:
Recommended agent:
Recommended worker:
Next focused action:
```

Example:

```text
MUSE capture: HazMat Command needs an audit trail for OCR confidence and who approved each shipping paper correction.
```

Expected routing:

- Recommended agent: HazMat Command Specialist
- Recommended worker: Claude Code Builder after focused scoping

## MUSE Focused

Purpose:
Expand a captured idea into a focused plan.

Command:

```text
MUSE focused: <task title or captured idea>
```

Expected mode:
Operator Mode or Strategy Mode.

Expected response:

```text
Mission:
Context:
Assumptions:
Recommended agent:
Recommended worker:
Acceptance criteria:
Verification plan:
Next action:
```

## MUSE Build

Purpose:
Prepare a Builder Mode packet for code work.

Command:

```text
MUSE build: repo=<repo> task=<task>
```

Expected mode:
Builder Mode.

Expected response:

```text
Mission understood:
Repo root:
Risk class:
Agents selected:
Worker selected:
Build/review plan:
Files likely affected:
Verification plan:
Rollback plan:
Next action:
```

Rules:

- Confirm repo root before edits.
- Use Claude Code as primary builder.
- Use Codex as reviewer or bounded fix worker.
- Do not let Claude Code and Codex edit the same branch simultaneously.
- Require tests or an explicit reason tests were not run.

## MUSE Critic

Purpose:
Challenge an idea or plan.

Command:

```text
MUSE critic: <idea or plan>
```

Expected mode:
Critic Mode.

Expected response:

```text
What I hear you saying:
My honest take:
Strongest objection:
What is fixable:
What may be fatal:
Better version:
Next action:
```

Rules:

- Do not automatically agree.
- Name weak logic clearly.
- Offer a stronger alternative if possible.

## MUSE Strategy

Purpose:
Think through product, career, business, monetization, positioning, or partner decisions.

Command:

```text
MUSE strategy: <decision or topic>
```

Expected mode:
Strategy Mode.

Expected response:

```text
What I hear you saying:
My honest take:
Strategic tradeoff:
Best path:
What not to do yet:
Next action:
```

## MUSE Review

Purpose:
Route a plan, PR, diff, or product decision through review.

Command:

```text
MUSE review: <PR, diff, file, plan, or decision>
```

Expected mode:
Operator Mode, Critic Mode, or Builder Mode depending on payload.

Possible routing:

- AOS Council for judgment
- Contrarian Reviewer for critique
- Codex Reviewer for code review
- QA Release Gate for release readiness
- Security / Compliance Reviewer for risky surfaces

## MUSE Remember

Purpose:
Save durable memory.

Command:

```text
MUSE remember: <durable fact>
```

Save only:

- durable decisions
- product direction
- preferences
- repeated mistakes
- successful prompts
- repo-specific lessons
- career positioning
- routing improvements

Do not save:

- secrets
- credentials
- API keys
- temporary emotions
- one-off task progress
- stale PR numbers
- raw private dumps

## MUSE Forget

Purpose:
Remove stale or wrong memory.

Command:

```text
MUSE forget: <memory or belief to remove>
```

Expected behavior:

- identify the memory
- remove it if available
- confirm removal plainly

## MUSE Correct

Purpose:
Replace stale memory or a bad assumption.

Command:

```text
MUSE correct: <old belief> -> <new belief>
```

Expected behavior:

- acknowledge correction
- update memory if durable
- avoid repeating the stale belief

## Owner-Gated Commands

Slack commands must not directly execute high-risk actions without explicit owner authorization.

Owner-gated actions:

- spend money
- post publicly
- create third-party account
- OAuth
- production deploy
- DNS change
- main-branch merge
- package publish
- app store submission
- legal/compliance/security/health/financial/regulated claim

When authorized, record:

```text
Yes, with authorization.
```

If not authorized, respond:

```text
Captured. This needs focused-mode authorization before action.
```

## Response Length Policy

Mobile command responses should be short unless Jeremiah explicitly asks for focused mode.

Default max shape:

- one short heading
- six short fields or fewer
- no long code blocks
- no full diffs
- no multi-page plans

Focused mode can be longer.

## Examples

### Capture

```text
MUSE capture: Nourish should explain why a meal suggestion fits my goals without sounding medical.
```

Expected:

```text
Captured idea: explain meal suggestions safely.
Clean task title: Add non-medical meal rationale copy.
Short summary: Nourish should explain recommendations without making health claims.
Recommended agent: Nourish Product Specialist.
Recommended worker: Docs Update Worker first, Claude Code later if UI changes are needed.
Next focused action: Draft safe copy patterns and claim boundaries.
```

### Build

```text
MUSE build: repo=hermes-agent task=add jarvis context audit script
```

Expected:

```text
Mission understood: add MUSE context audit script.
Repo root: confirm before edits.
Risk class: medium-low.
Agents selected: MUSE Code Operator.
Worker selected: Claude Code Builder, Codex Reviewer after diff.
Build/review plan: inspect paths, add script, run py_compile, run audit.
Files likely affected: scripts/jarvis_context_audit.py.
Verification plan: py_compile, script run, git diff --check.
Rollback plan: remove script.
Next action: focused repo inspection.
```

### Critic

```text
MUSE critic: I want to add every recovered AOS agent as always active.
```

Expected:

```text
What I hear you saying: you want maximum agent coverage.
My honest take: bad idea; it recreates swarm noise.
Strongest objection: always-active agents should be small and predictable.
What is fixable: keep specialists on demand.
Better version: small active council plus verified routing presets.
Next action: update registry verification to prevent swarm activation.
```
