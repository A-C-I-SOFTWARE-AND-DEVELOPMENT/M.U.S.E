---
name: hermes-council-protocol
description: Run a structured multi-agent council on a high-stakes question and synthesize one prioritized answer. Use when the task spans more than one specialist domain or when the owner asks for a "full review" / "use all agents" / "council mode".
---

# Hermes Council Protocol

## When to invoke

- Mission-level questions: "should we launch?", "is this ready?", "what
  would the team say?".
- Multi-domain changes (e.g. security + UX + mobile, product + growth +
  pricing).
- Before any external claim of production readiness.

## Procedure

1. **Mission brief.** Write one paragraph: goal, scope, exclusions, success
   criteria. The owner approves this before specialists run.
2. **Repo map.** Invoke `repo-context-librarian` once; share the map with
   every specialist.
3. **Specialist selection.** Pick only relevant specialists, justify each
   inclusion in one line. Maximum 6 specialists per pass — more is theater.
4. **Parallel fan-out.** Issue all specialist `Agent` calls in a single
   message. Each gets: mission, repo map, their specific question, output
   format. Specialists do NOT see each other's output.
5. **Collect verbatim.** Paste each specialist's output without editing.
6. **Synthesis.** Invoke `hermes-final-synthesizer` with the mission and
   all specialist outputs.
7. **Owner handoff.** Surface code-side blockers, owner-only blockers, and
   the single next action.

## Hard rules

- One council pass per question. Loops are forbidden — if the owner needs
  another pass, that's a new mission brief.
- A specialist that returned nothing useful is reported as "no findings",
  not silently dropped.
- Disagreement between specialists is surfaced, not averaged.
- The synthesizer cannot upgrade a verdict above the lowest specialist
  verdict without an explicit override rationale.

## Output

```
## Mission brief
## Repo map (link or paste)
## Specialists engaged (name, one-line reason)
## Specialist findings (verbatim, per specialist)
## Synthesizer verdict
## Code-side blockers
## Owner-only blockers
## Single next action
```
