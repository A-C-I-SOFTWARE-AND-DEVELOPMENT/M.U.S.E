---
name: seat-roster
description: "Route orchestrated work across the installed orchestrator seats (planner / executor / critic / researcher / operator / scribe)."
version: 1.0.0
author: Jeremiah Echerd + Hermes Agent
license: MIT
platforms: [linux, termux, macos, windows]
---

# Orchestrator Seat Roster

The seat roster is muse's standing agent team for orchestrated work. Each
seat is a hermes **profile** — an isolated `HERMES_HOME` with its own model,
memory, skills, and `SOUL.md` — so every seat accumulates experience across
jobs instead of starting cold. Seats are installed by `hermes setup trio`
(core trio or full roster) and listed by `hermes profile list`.

| Seat | Job | Route here |
|---|---|---|
| `orchestrator` | Global planner & architect. Holds whole-repo context, decomposes goals into atomic dependency-mapped cards, guards module boundaries. | Planning, decomposition, architecture questions |
| `executor` | Tactical builder. One bounded ticket at a time: writes code, runs commands, self-corrects on tool errors. | Implementation, coding, file edits, tool execution |
| `critic` | Independent reviewer (third-vendor model). Checks diffs against contracts and architecture, approves or rejects with a critique. | Review, verification, QA — never its own build tasks |
| `researcher` | Long-context evidence gatherer. Reads docs/code, compares options, cites sources. | Research, investigation, comparison |
| `operator` | Ops & infrastructure. Environment setup, CI upkeep, release prep — irreversible actions stay owner-gated. | Ops, environment, CI, maintenance |
| `scribe` | Documentation & knowledge curator. Docs, changelogs, job summaries, roster-description upkeep. | Documentation, summarization, knowledge curation |

## When to Use

Use this skill when:

- A goal is being decomposed (`/orchestrate`, kanban triage) and cards need
  assignees — match each card to the seat table above.
- The user asks "who should do X", "assign this", or "use the seats/roster/trio".
- Reviewing a finished card: route the review card to `critic`, never back
  to the seat that built it (builder ≠ reviewer is a hard rule).
- A card doesn't match any seat description — assign `executor` (the
  kanban `default_assignee`) and note the routing gap for the `scribe` to
  fold into a description update.

Do not use this skill when:

- The work is a single conversational answer — no orchestration needed.
- The seats aren't installed (`hermes profile list` shows none of them) —
  offer `hermes setup trio` instead of inventing assignees.
- A seat's action would cross an owner gate (spend, deploy, publish,
  main-branch merge, credential change) — stop and wait for the owner's
  exact `Yes, with authorization.`

## Routing Rules

1. **One card, one seat.** Never co-assign; split the card instead.
2. **Builder ≠ reviewer.** Whatever seat built a card, its review card goes
   to `critic` (or another non-author seat if `critic` is the author).
3. **Planning stays on the orchestrator.** Don't let a builder replan scope
   mid-card; a scope problem goes back as a card comment for the
   `orchestrator` to re-decompose.
4. **Context economics.** Only the `orchestrator` gets whole-repo context.
   Give the `executor` the files a ticket needs, not the repo.
5. **Descriptions are the router.** Seat routing matches card text against
   each profile's `profile.yaml` description. If routing misfires
   repeatedly, fix the *description*, not the dispatcher.
6. **Rejections loop, they don't die.** A rejected card returns to its
   builder with the critique attached as a follow-up card — see the
   rejection-loop section of
   `docs/orchestration/orchestrator-trio.md`.

## Pitfalls

- Don't create a seventh seat for a one-off task — mount a skill into an
  existing seat instead. Profiles are for durable roles that need private
  memory; skills are for expertise.
- Don't hand the `operator` an irreversible action without the owner gate.
- Don't route review to a fourth "second opinion" seat by default; one
  independent critic plus validation gates is the calibrated cost/quality
  point. Escalate to a panel only when the owner asks.
- The seat models are `candidate`-tagged catalog entries — if a seat's
  model is unavailable on OpenRouter, swap it (`hermes -p <seat> model`)
  rather than silently falling back.
