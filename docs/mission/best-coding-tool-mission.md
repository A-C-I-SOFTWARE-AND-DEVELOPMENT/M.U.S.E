# Hermes — Best Coding Tool Mission

> One prompt is enough.

## Mission statement

Hermes strives to be the best private local-first developer command
center. Its mission is to make one prompt enough to plan, research,
route, build, validate, self-improve, and publish software work.

Hermes is the only coding tool Jeremiah needs. Every job teaches it
something it keeps.

## Product principles

These are not aspirational; they are the contract every subsystem in
this repo must honor. When a new feature lands, it must point at the
principle(s) it advances and must not silently break the others.

1. **One prompt starts everything.** The user opens the cockpit,
   types or speaks a single intent, and Hermes is responsible for
   turning that into a complete delivery. No multi-form wizards, no
   "now configure X before you can ask Y."
2. **Hermes chooses the best worker/model mix.** Routing — local vs.
   cloud, planner vs. builder vs. reviewer, cheap vs. capable model —
   is Hermes' job, not the user's. The user may override; the user
   should never *have* to.
3. **Every decision has visible evidence and validation.** Routing
   choices, plan steps, tool selections, and merges all surface the
   evidence that justified them (tests, scorecards, logs, prior
   outcomes) in a place the user can actually read.
4. **Every job has durable artifacts.** Plans, transcripts,
   diffs, evaluations, and routing decisions are written to disk
   under the job's directory and survive container teardown via the
   user's repo / sync target. Nothing important lives only in RAM.
5. **Every worker output is scored.** Worker output is graded against
   the standing quality scorecard (below) before it can be merged or
   published. Unscored output is treated as untrusted.
6. **Every merge is reviewed.** No worker self-merges its own change.
   A different agent (or the user) reviews the diff against the plan
   and the scorecard.
7. **Every publish is reversible.** Every action that leaves the
   private device — git push, PR open/merge, release tag, deploy,
   external message — produces a recorded undo path (revert SHA,
   close-and-revert PR, redeploy of previous tag, retraction
   message). If we cannot describe how to undo it, we do not ship it.
8. **Hermes learns from every job.** Every completed (or failed) job
   feeds the self-improvement loop. Wins update skills, prompts, and
   routing weights. Losses produce concrete proposals before they
   produce blame.
9. **Current AI improvements update the routing policy.** When new
   models, new providers, new tools, or new local capabilities appear,
   the routing policy must absorb them automatically (or surface a
   queued proposal). The router is a living artifact, not a constant.
10. **The Android APK is the cockpit; Hermes backend is the engine.**
    The APK at `apps/android/` is the place a human drives Hermes
    from. The backend (`run_agent.py`, `cli.py`, gateway, plugins,
    skills, enterprise council) is where work actually happens. The
    cockpit must never silently bypass the engine.

## Standing quality scorecard

Every worker output (plan, patch, doc, deploy plan, review) is graded
against this rubric. Each axis is 0–10. The scorecard travels with
the job and is what the reviewer reads first.

```json
{
  "correctness": 0,
  "maintainability": 0,
  "testability": 0,
  "architecture_fit": 0,
  "developer_experience": 0,
  "ui_ux": 0,
  "speed": 0,
  "cost_efficiency": 0,
  "local_first_fit": 0,
  "jeremiah_fit": 0
}
```

Axis definitions:

| axis | what it measures |
|---|---|
| `correctness` | Does it do what was asked, verified against tests / runtime / explicit acceptance criteria? |
| `maintainability` | Will a future reader (Jeremiah or another agent) understand and safely change this? |
| `testability` | Can the change be exercised by automated checks, and were those checks added/updated? |
| `architecture_fit` | Does it match the patterns and seams already in this repo (no parallel re-implementations, no premature abstractions)? |
| `developer_experience` | Did the change keep the build, the CLI, the docs, and the error messages friendly? |
| `ui_ux` | For user-facing surfaces (APK, TUI, gateway, web): is the result obvious, fast, and respectful of attention? |
| `speed` | Wall-clock cost of the change at runtime and the wall-clock cost of producing it. |
| `cost_efficiency` | Did the worker/model mix match the difficulty of the job? Cheap models for easy work, capable models for hard work. |
| `local_first_fit` | Does it preserve the local-first, private-by-default posture (no surprise cloud calls, no leaked secrets, no required external accounts)? |
| `jeremiah_fit` | Does it match Jeremiah's known preferences (terse, durable artifacts, one-prompt UX, reversible publishes)? |

Routing, reviews, and the self-improvement loop all read this
scorecard. Any axis scoring `<= 4` blocks merge by default; the
reviewer may override with an explicit, recorded reason.

## How this document is used

- `skills/best-coding-tool-mission/SKILL.md` — the skill that reminds
  Hermes of this mission and forces it to declare which principles a
  given job advances.
- `skills/self-improvement-loop/SKILL.md` — the per-job learning
  pass that turns artifacts and scorecards into proposed updates to
  skills, prompts, and the routing policy.
- `docs/orchestration/self-improvement-loop.md` — the operational
  description of where artifacts live, how proposals are recorded,
  and how routing absorbs new capabilities.
