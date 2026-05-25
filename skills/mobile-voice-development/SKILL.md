---
name: mobile-voice-development
description: "Route mobile voice coding tasks."
version: 1.0.0
author: Jeremiah Echerd + Hermes Agent
license: MIT
platforms: [linux, termux, macos, windows]
---

# Mobile Voice Development

Mobile Voice Development turns rough ideas from jogging, walking, driving breaks, trucking work, Slack, or Termux into clean task packets that can be resumed later in focused mode.

The goal is not to code from a voice dump. The goal is to capture intent, preserve momentum, route the work, and avoid overwhelming Jeremiah while he is moving.

## When to Use

Use this skill when:

- Jeremiah says he is jogging, walking, driving, traveling, or moving.
- The message appears dictated, rough, emotional, or multi-idea.
- Slack or Termux is being used as a mobile command surface.
- A mobile thought should become a clean task title, short summary, and next focused action.
- The work should resume later in focused mode.

Do not use this skill when:

- Jeremiah explicitly requests focused technical depth now.
- A precise code edit is already approved and scoped.
- The request requires immediate repo inspection.
- The action is destructive, secret-bearing, deploy-related, merge-related, or owner-gated.
- The user asked only for exact command output.

## Prerequisites

Capture what is available without forcing a long clarification loop:

- Raw intent.
- Mobile context: jogging, walking, driving break, Slack, Termux, travel, or away from desk.
- Product, repo, or domain if mentioned.
- Main idea.
- Urgency.
- Risky action implied by the request.
- Whether focused expansion is requested now or later.

If required context is missing, make a reasonable short assumption or turn it into a focused-mode question.

## How to Run

1. Preserve the raw intent.
2. Extract the main idea.
3. Create a clean task title.
4. Summarize in plain language.
5. Identify likely mode, agent, or specialist.
6. Recommend a worker only if implementation is likely.
7. Defer risky or owner-gated actions.
8. Produce the next focused action.
9. Save durable memory only if the fact will still matter later.

## Quick Reference

Primary Hermes tool surface for mobile capture (use these from inside the Hermes runtime — no shelling out required):

- `skill_view` → load `mobile-voice-development` to ground the capture flow, then respond in the short format below.
- `delegate_task` → hand the raw dump to a Mobile Voice sub-agent when the parent session is busy or the capture should run isolated.
- `memory` → persist the clean task title, raw intent, and next focused action so focused-mode can resume later.
- `send_message` → relay the captured packet back to the originating channel (Slack thread, Discord DM, etc.) without leaving Hermes.
- `clarify` → ask one tight follow-up only when the capture is unsalvageable; otherwise prefer a short assumption.

Default short response:

```text
Captured idea:
Clean task title:
Short summary:
Recommended agent:
Recommended worker:
Next focused action:
```

JARVIS subcommands (issued as user messages inside any Hermes-attached surface — Slack, Discord, desktop, or Termux):

```text
JARVIS capture: <raw idea>
JARVIS focused: <task title or captured idea>
JARVIS build: <repo and task>
JARVIS critic: <idea or plan>
JARVIS strategy: <decision or product direction>
JARVIS review: <PR, diff, plan, or file set>
JARVIS remember: <durable fact>
JARVIS forget: <memory to remove>
JARVIS correct: <old belief> -> <new belief>
```

The Hermes runtime classifies the mode from the prefix and routes through the tools above; you do not need to invoke a shell to dispatch them.

### Termux fallback (mobile shell)

Only when Jeremiah is on Termux without an active Hermes session attached — typically a cold start from a phone — fall back to the `hermes` CLI directly:

```bash
cd /data/data/com.termux/files/home/hermes-agent
hermes "JARVIS capture: <raw idea>"
```

```bash
cd /data/data/com.termux/files/home/hermes-agent
hermes "JARVIS focused: <task title>"
```

This launches a fresh Hermes runtime, which then routes through the same tool surface listed above. Prefer reattaching to an existing session over spawning a new one when bandwidth or battery is tight.

## Procedure

### Jogging or Walking Capture

- Keep the response short.
- Do not ask Jeremiah to review many files.
- Do not dump long code or diffs.
- Capture the strongest useful signal.
- End with a focused-mode next action.

### Short Response Mode

Use six fields or fewer. Avoid:

- long code blocks
- full diffs
- multi-page plans
- secrets handling
- merge, deploy, or publish instructions
- complicated command sequences

### Focused Mode Expansion

When Jeremiah later says `JARVIS focused: <task>`, expand into:

- Mission.
- Context.
- Assumptions.
- Recommended agent or specialist.
- Recommended worker.
- Files likely affected if repo is known.
- Acceptance criteria.
- Verification plan.
- Rollback plan.
- Owner gates.

Focused mode can be longer and technical.

### Task Packet Output

Use this packet when a capture needs to be resumed later:

```markdown
# Mobile Capture Task Packet

## Clean Task Title
## Raw Intent
## Short Summary
## Product / Repo
## Recommended Mode
## Recommended Agent
## Recommended Worker
## Why This Matters
## Non-Goals
## Questions for Focused Mode
## Next Focused Action
```

### Owner-Gated Mobile Requests

Never execute these from vague mobile voice input:

- deploy
- merge
- push
- publish
- spend money
- create account
- OAuth or credential changes
- DNS changes
- app store submission
- destructive deletes
- legal, compliance, security, health, financial, or regulated claims
- expose, store, or transmit secrets

Instead respond:

```text
Captured. This needs focused-mode authorization before action.
```

When authorization is later granted, record:

```text
Yes, with authorization.
```

## Pitfalls

- Turning a voice dump into a long essay. Fix: use the six-field short response.
- Asking Jeremiah to review diffs while moving. Fix: defer to focused mode.
- Treating temporary emotion as durable memory. Fix: capture the useful signal only.
- Running risky commands from rough speech. Fix: require focused authorization.
- Losing raw intent while over-structuring. Fix: preserve raw intent in the packet.
- Coding before focused-mode scope is clear. Fix: produce a build packet later.

## Verification

A mobile capture is complete when:

- Raw intent is preserved.
- The clean task title is specific.
- The short summary is plain-language.
- Recommended route is useful but not overbuilt.
- No long code dumps appear while Jeremiah is moving.
- Risky actions are deferred.
- The next focused action makes it easy to resume later.
