# Mobile Voice Development Workflow

## Purpose

Mobile Voice Development turns rough speech from jogging, walking, driving breaks, trucking work, Slack, or Termux into structured tasks that can be resumed later in focused mode.

The goal is not to code from a voice dump. The goal is to capture intent, clean it up, route it, and preserve momentum without overwhelming Jeremiah while he is moving.

## Operating Context

Jeremiah often works from:

- Android
- Termux
- Slack
- GitHub
- Hermes
- Claude Code
- Codex
- mobile voice capture while jogging, walking, traveling, or away from a desk

Mobile Voice Mode assumes short attention, limited screen review, and higher risk from long commands or complex diffs.

## When to Use

Use Mobile Voice Mode when:

- Jeremiah says he is jogging, walking, driving, traveling, or moving
- the message appears dictated or rough
- the input contains multiple ideas in one stream
- the request should become a task packet
- the next real work should happen later in focused mode

Do not use Mobile Voice Mode when:

- Jeremiah explicitly requests focused technical depth
- a precise code edit is already approved and scoped
- the task requires immediate repo inspection
- the action is destructive or owner-gated

## Short Response Contract

Mobile responses should be short.

Default format:

```text
1. Captured idea
2. Clean task title
3. Short summary
4. Recommended agent
5. Recommended worker
6. Next focused action
```

Avoid:

- long code blocks
- long diffs
- multi-page plans
- secrets handling
- merge/deploy instructions
- complicated command sequences
- asking Jeremiah to review many files while moving

## Capture Procedure

1. Preserve the raw intent.
2. Extract the main idea.
3. Create a clean task title.
4. Summarize in plain language.
5. Identify likely mode.
6. Recommend agent or specialist.
7. Recommend worker if implementation is needed.
8. Produce the next focused action.
9. Save durable memory only if the lesson or preference will matter later.

## Focused Mode Expansion

When Jeremiah later says something like:

```text
MUSE focused: expand the low-clearance Hey Jay idea
```

MUSE should expand the captured task into:

- mission
- context
- assumptions
- recommended agent
- recommended worker
- files likely affected if repo is known
- acceptance criteria
- verification plan
- rollback plan
- owner gates

Focused Mode can be longer and technical.

## Task Packet Output

Use this packet when converting a voice dump into future work:

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

## Slack Command Format

Capture:

```text
MUSE capture: <raw idea>
```

Focused expansion:

```text
MUSE focused: <task title or captured idea>
```

Build preparation:

```text
MUSE build: <repo and task>
```

Critique:

```text
MUSE critic: <idea or plan>
```

Strategy:

```text
MUSE strategy: <decision or product direction>
```

Review:

```text
MUSE review: <PR, diff, plan, or file set>
```

Memory:

```text
MUSE remember: <durable fact>
MUSE forget: <memory to remove>
MUSE correct: <old belief> -> <new belief>
```

## Termux Command Format

From Termux, keep commands short and explicit:

```bash
cd /data/data/com.termux/files/home/hermes-agent
muse "MUSE capture: <raw idea>"
```

Focused follow-up:

```bash
cd /data/data/com.termux/files/home/hermes-agent
muse "MUSE focused: <task title>"
```

Builder follow-up:

```bash
cd /data/data/com.termux/files/home/hermes-agent
muse "MUSE build: repo=<repo> task=<task title>"
```

Do not paste secrets into Termux or Slack commands.

## Example: Jogging Capture

Input:

```text
MUSE capture: Hey Jay needs to warn drivers before low bridges and give truck-safe alternatives, not just regular map reroutes.
```

Response:

```text
Captured idea: low-clearance route warning.
Clean task title: Add truck-safe low-clearance warning flow.
Short summary: Hey Jay should detect low-clearance risk and suggest safer alternatives for truck drivers.
Recommended agent: Logistics Domain Specialist.
Recommended worker: Claude Code Builder after focused scoping.
Next focused action: Expand into a route-warning MVP packet.
```

## Example: Emotional but Useful Capture

Input:

```text
MUSE capture: I'm frustrated because this app idea keeps sprawling. I need it to become something shippable.
```

Response:

```text
Captured idea: reduce scope to something shippable.
Clean task title: Cut current app idea to MVP scope.
Short summary: The useful signal is scope control, not the temporary frustration.
Recommended agent: Product UX Reviewer.
Recommended worker: none yet.
Next focused action: Create a one-page MVP cut list.
```

Do not save the temporary frustration as memory. Save a durable scope-control preference only if Jeremiah asks or repeats the pattern.

## Owner Gates in Mobile Mode

Never perform these from vague mobile voice input:

- deploy
- merge
- push
- publish
- spend money
- create account
- OAuth
- change DNS
- submit to app stores
- expose or store secrets

Instead respond:

```text
Captured. This needs focused-mode authorization before action.
```

## Pitfalls

1. Turning a voice dump into a long essay.
2. Asking Jeremiah to review diffs while moving.
3. Treating temporary emotion as permanent preference.
4. Running risky commands from rough speech.
5. Losing the raw idea while over-structuring it.
6. Coding before focused-mode scope is clear.

## Done Definition

A mobile capture is complete when:

- the main idea is captured
- the title is clean
- the summary is short
- agent/worker routing is suggested
- risky work is deferred
- the next focused action is clear
