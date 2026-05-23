# Self-Improvement Loop

Hermes runs a retrospective after every job. The retrospective is the
unit of learning: it captures what was tried, what worked, what did
not, and what Hermes will do differently next time.

## Why every job needs a retro

A job that succeeded but taught Hermes nothing is a missed upgrade.
The loop's job is to make sure each cycle either (a) reinforces the
routing decisions that already work, or (b) proposes a concrete change
to routing, skills, or memory.

The metric Hermes optimizes is defined in
`docs/mission/best-coding-tool-mission.md`: jobs delivered, validated,
and accepted. Every retrospective traces an outcome back to that
metric.

## When the loop runs

- After every job marked complete (success, partial, or failure).
- After every user correction that overrides a Hermes action.
- On operator request (`hermes retro <job-id>`).

If a job ran through a worker pool (kanban dispatcher, enterprise
council, etc.), the loop runs **once per top-level job**. Worker-level
scoring feeds into that single retrospective rather than producing N
separate files.

## What gets recorded

Every retrospective fills the template at
`templates/orchestration/job-retrospective.md`. The required fields:

| Field | Notes |
|---|---|
| Job id, prompt, repo, date | As-typed prompt; never rewritten. |
| Outcome | Succeeded, partially succeeded, or failed. One must be `yes`. |
| Worker performance table | Score 0-10 per worker, strength, weakness, use-again. |
| Validation | Commands run + pass/fail. If skipped, write `not run` and flag. |
| Lessons | What should Hermes remember? |
| Routing updates | What should the router do differently? `no change` is valid. |
| Skill updates | Are any SKILL.md files now wrong or missing? |
| Jeremiah preference updates | Tracked separately from aggregate users. |
| Memory notes | One-line declaratives, persisted under `memory/longterm-memory/`. |
| Next improvement | One experiment Hermes will run on a comparable job. |

Empty sections must read `none` or `not applicable` so retrospectives
are greppable across the corpus.

## Where retros live

- File path: `memory/longterm-memory/retrospectives/<YYYY-MM-DD>-<job-id>.md`
- The directory is created on first use. It follows the same privacy
  rules as the rest of `memory/longterm-memory/`: local only, no
  telemetry, no third-party calls.

## Jeremiah vs. aggregate preferences

`Jeremiah` is the primary operator and his preferences drive
single-operator routing. Other users' aggregate preferences are
tracked separately so a future per-operator routing layer can use the
delta. The retrospective template forces the two fields to be filled
independently to keep the data clean.

## How the loop feeds the rest of Hermes

```
job runs
   |
   v
retrospective written  ----> memory/longterm-memory/retrospectives/
   |
   v
routing updates proposed  -> routing policy patch (PR)
   |
   v
skill updates proposed    -> SKILL.md patch (PR)
   |
   v
memory notes persisted    -> memory/longterm-memory/
   |
   v
next-improvement experiment scheduled for next comparable job
```

The `ai-improvement-radar` skill consumes the retrospectives - it
watches for patterns like "worker X has lost 4 of the last 5 bugfix
jobs" and proposes demoting that worker in the next radar report.

## Hard rules

- ASCII only.
- Offline safe; no network calls.
- No silent edits to routing or skills. Proposals go to a PR unless
  the operator has explicitly authorized autonomous routing changes
  for the current job.
- Never edit the original job transcript. The retrospective is a new,
  additive artifact.
- If a field is unknown (e.g. validation skipped, worker rationale
  unclear), write `not run` or `unknown` and flag it under "Lessons".

## Operator workflow

1. Job finishes.
2. Hermes (or the operator) runs the retrospective skill.
3. The retrospective is reviewed, edited if needed, and committed.
4. Any proposed routing or skill patches are opened as PRs.
5. The "next improvement" item is scheduled for the next comparable
   job and tracked across runs.

## Related docs

- `docs/ai-intelligence/ai-improvement-radar.md` - external ecosystem
  tracking.
- `docs/mission/best-coding-tool-mission.md` - north-star metric.
- `templates/orchestration/job-retrospective.md` - the template itself.
- `skills/self-improvement-loop/SKILL.md` - the agent-side procedure.
