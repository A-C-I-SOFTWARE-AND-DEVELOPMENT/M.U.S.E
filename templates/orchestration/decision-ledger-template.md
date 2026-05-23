# Decision Ledger

> Copy this file to `.hermes/decisions/YYYY-MM-DD_HHMMSS-<slug>.md` (or the
> workspace's configured ledger lane). One ledger per non-trivial decision.
> The ledger is the user-facing artifact — it replaces any hidden
> reasoning trace. Do not paste raw chain-of-thought into it; record
> evidence, options, tradeoffs, the selection, the validation, and the
> rollback path.

**Ledger ID:** `<slug-or-uuid>`
**Session / Run ID:** `<session_id>`
**Authoring agent:** `<orchestrator | leaf:<domain> | judge | monitor>`
**Created:** `<YYYY-MM-DD HH:MM:SS TZ>`
**Status:** `draft | proposed | accepted | superseded | rolled-back`
**Supersedes:** `<previous ledger id or "none">`

---

## Decision

> One sentence. What concrete choice is being made *now*?

…

## Context

> Why is this decision in front of us? What task, repo, user goal, or
> constraint triggered it? Cite the request verbatim if it was short, or
> link to the source (issue, PR, session id, plan file).

- **User goal:** …
- **Triggering event:** …
- **Scope:** what is in scope, what is explicitly out of scope.
- **Constraints:** budget, latency, regulatory, repo policy, autonomy
  mode (`default | strict | yolo`).

## Evidence Reviewed

> Every option/claim below must trace back to something on this list.
> Items with no evidence are *assumptions* — call them out in
> "Open risks" instead of dressing them up as facts.

- **Files:**
  - `path/to/file.py:L42-L97` — what you read and the relevant takeaway.
- **Commands:**
  - `cmd …` → one-line summary of what the output told you.
- **Docs (in-repo):**
  - `docs/…md` — section / heading consulted.
- **Web sources** (only when web access is available and the worker is
  permitted to use it):
  - `<url>` — accessed `<YYYY-MM-DD>`, summary.
- **Prior memory / session notes:**
  - `<ledger id | plan file | audit row>` — what carried over.
- **Skipped on purpose:** sources you deliberately did *not* consult and
  why (e.g. "did not run the live API; would mutate production").

## Options Considered

> At least two options. "Do nothing" and "defer to user" are valid
> options and should appear when relevant. Use the same headings for
> every option so they can be diffed.

### Option A — `<short name>`

- **Summary:** one line.
- **Pros:** …
- **Cons:** …
- **Risks:** what could go wrong, and the blast radius.
- **Validation:** what you would run / check to confirm this option
  works *before* committing to it.
- **Cost / latency / quality:** rough numbers or relative ranking.
- **Evidence supporting:** bullet refs back to the "Evidence Reviewed"
  list.

### Option B — `<short name>`

- **Summary:** …
- **Pros:** …
- **Cons:** …
- **Risks:** …
- **Validation:** …
- **Cost / latency / quality:** …
- **Evidence supporting:** …

<!-- Add Option C, D, … as needed. -->

## Selected Model / Worker

> Which Hermes worker (model, leaf, subagent, external tool) will
> execute the decision, and at what cost. This block is mandatory even
> when the "decision" itself is a code edit — record which model is
> doing the edit and why.

- **Selected:** `<provider/model-id or leaf name>` (e.g.
  `claude-opus-4-7`, `enterprise-finance`, `gpt-4o-mini`, `local/cli`).
- **Why:** the one sentence that distinguishes this worker from the
  rejected alternatives.
- **Rejected alternatives:** `<model/worker>` — why not (cost, latency,
  capability gap, policy, availability).
- **Fallback:** what to switch to if the selected worker is unavailable,
  rate-limited, or produces a judge-failing result.
- **Cost / latency / quality tradeoff:** explicit. e.g. "Opus: highest
  quality, ~3× cost vs Sonnet, ~2× latency; chosen because the failure
  cost (regulated finance mutation) dominates the price delta."

## Validation Plan

> What turns this from a *proposal* into an *accepted* decision. The
> Judge / reviewer should be able to re-run this list and reach the same
> verdict.

- **Commands:** exact invocations with expected outcomes.
- **Manual checks:** files to eyeball, screens to look at, dashboards
  to refresh.
- **Schema / contract checks:** which structured-output contract the
  result must satisfy (links to the leaf's SKILL.md table or judge
  schema).
- **Success criteria:** the *observable* conditions that must hold.
  Avoid "looks good" — prefer "test X passes", "metric Y < threshold".
- **Failure response:** what happens if validation fails (retry once,
  escalate, roll back, ask user).

## Final Decision

> Filled in *after* the validation plan has been executed (or
> explicitly waived with a reason).

- **Decision:** `<the choice, restated>` — option `<A | B | …>`.
- **Confidence:** `low | medium | high`, with one sentence justifying
  the level (what would have to be true for confidence to be wrong).
- **Open risks:** what we are knowingly accepting, and the trigger that
  would force a revisit.
- **Rollback:**
  - **Trigger:** what observable condition causes a rollback.
  - **Action:** the exact steps / commands / revert commit / config
    flip / leaf invocation.
  - **Owner:** which agent or human is responsible.
  - **Window:** how long the rollback path stays cheap before it
    becomes structural.

---

<!--
Cross-links (optional):
- Audit row(s): <session_id> events <event ids>
- Plan: <.hermes/plans/...md>
- Spike: <spikes/NNN-...>
- PR / commit: <ref>
- Superseded by: <ledger id>
-->
