<!--
Worker selection report — emitted by the model-router skill.

Fill every field. Leave a section explicitly empty (`_none_`) rather
than removing it; the user reads these in a fixed order and a missing
section reads as an oversight.

The report is the *deliverable* of the routing step. It is shown to
the user before any handoff or push actually happens. Execution is a
separate turn that quotes the relevant section of this report back.

Replace each {{ placeholder }} with concrete text. Do not leave any
{{...}} in the rendered report.
-->

# Worker selection report — {{ task_title }}

**Task:** {{ one_sentence_restatement_of_the_user_request }}
**Generated:** {{ iso_8601_timestamp }}
**Repo / branch:** {{ repo }} @ {{ branch }}
**Router policy version:** {{ policy_version }}   <!-- e.g. registry v1 -->

## 1. Classification

| Axis | Value | Why |
|---|---|---|
| Task kind | `{{ kind }}` | {{ one_line }} |
| Risk | `{{ low \| medium \| high }}` | {{ one_line }} |
| Quality weight | `{{ low \| medium \| high }}` | {{ one_line }} |
| Speed weight | `{{ low \| medium \| high }}` | {{ one_line }} |
| Cost weight | `{{ low \| medium \| high }}` | {{ one_line }} |
| Privacy weight | `{{ low \| medium \| high }}` | {{ one_line }} |

## 2. Detection snapshot

What was actually available on this machine at routing time. One row
per registry entry the router considered.

| Registry id | Detected? | Evidence |
|---|---|---|
| `{{ id }}` | {{ yes \| no }} | {{ command-on-PATH / env-var-set / file-present / app-installed / prompt-always }} |
<!-- repeat per considered id -->

## 3. Selected worker mix

**Primary worker:** `{{ registry_id }}`

- Strengths used: {{ pull from registry.strengths }}
- Why this one over the alternatives: {{ 1–2 sentences }}

**Supporting workers (in order):**

1. `{{ registry_id }}` — {{ what it does in this plan }}
2. `{{ registry_id }}` — {{ what it does in this plan }}
<!-- or write `_none_` -->

**Fallback chain** (used if the primary fails detection or errors out):

1. `{{ registry_id }}` — {{ when to fall back }}
2. `{{ registry_id }}` — {{ when to fall back }}
<!-- or write `_none_` — but say so explicitly -->

## 4. Approvals required before execution

List every step that must show this report (or a quoted section of it)
to the user and wait for an explicit `yes` before running. Use the
exact text the user should approve.

- [ ] {{ e.g. "Hand off the drafted prompt to ChatGPT via clipboard." }}
- [ ] {{ e.g. "Push branch `claude/foo` to origin and open a draft PR." }}
- [ ] {{ e.g. "Run `goose run upgrade-deps` in a sandbox for up to 20 minutes." }}
<!-- If risk == "low" and no entry has requires_approval: true, write
     `_none — entirely local, reversible work_` -->

## 5. Capability coverage check

Required capabilities for task kind `{{ kind }}` (from
`tool-capability-matrix.md`), and which worker covers each:

| Required capability | Covered by |
|---|---|
| {{ capability }} | `{{ registry_id }}` |
<!-- one row per required capability; every row must have a covering worker -->

If any row reads `_uncovered_`, the router must either widen the worker
mix or fall back to `hermes-local` in best-effort mode and say so.

## 6. Rationale

{{ 1–3 sentences tying the choice to the task. No marketing language.
   Reference the registry entry's `best_for` and tradeoffs explicitly. }}

## 7. What success looks like

A short, checkable definition so the user can tell whether execution
actually worked.

- {{ e.g. "Tests pass on the branch." }}
- {{ e.g. "PR opened with the diff and a description." }}
- {{ e.g. "The drafted RFC is in the clipboard, ready to paste." }}

## 8. What this report deliberately does *not* do

- Does not execute any handoff or push.
- Does not call any third-party API on the user's behalf.
- Does not pick a surface that isn't in `model-registry.yaml`.
- Does not silently fall back — every fallback emits a follow-up note.

---

_Next step: the user reviews this report. Execution happens in a
separate turn, quoting section 3 and section 4._
