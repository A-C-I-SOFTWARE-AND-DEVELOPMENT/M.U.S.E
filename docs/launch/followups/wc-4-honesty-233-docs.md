# WC-4: Honesty propagation — "233 → routed catalog" doc sweep (FU-18 follow-through)

- **Status:** building → in-review (PR opens on push)
- **Risk class:** additive (doc-only, RC0).
- **Branch:** `claude/vigilant-knuth-519h3u` · **Base:** `main` @ `860a88b8e`
- **PR:** TBD (draft on push)
- **Owner-gate required to merge?** **no** — auto-merge on green CI. (The
  owner's `Yes, with authorization.` covers the whole Wave C merge train
  for consistency, but doc-only RC0 is the auto-merge tier per the
  parallel-execution contract.)

## Intent (one paragraph)

The audit's `evidence-architect` found that FU-18's "233 → routed
catalog" honesty restatement landed in `CLAUDE.md` and `README.md:27,41`
but did **not** propagate to the canonical `AOS_*.md` recovery reports
or their `docs/aos-recovery/` mirrors. `AOS_AGENT_REGISTRY_COMPLETE.md`
(line 20) still said bare "Distinct names registered: 233" with no
qualifier; the same was true of `docs/aos-recovery/AOS_AGENT_RECOVERY_REPORT.md`
(line 43), `docs/aos-recovery/AOS_AGENT_REGISTRY_COMPLETE.md` (line 21),
and `docs/aos-recovery/AOS_INSTALLATION_REPORT.md` (line 17). Each of
these is a place a serious reader (a public auditor, a customer eval, a
linked-from-the-PR-description deep-dive) can land. WC-4 inserts the
exact "routed-catalog tally, not a file count" paragraph that
`AOS_INSTALLATION_REPORT.md:19-30` and the root
`AOS_AGENT_RECOVERY_REPORT.md:45-57` already carry, with an explicit
"WC-4 honesty propagation, following FU-18" marker so the next audit
can grep for completeness.

## Owned files (the ONLY files this task may write)

- `AOS_AGENT_REGISTRY_COMPLETE.md` — add the qualifier under the
  "Distinct names registered: 233" totals block.
- `docs/aos-recovery/AOS_AGENT_RECOVERY_REPORT.md` — add the qualifier
  under the registry-entry totals table.
- `docs/aos-recovery/AOS_AGENT_REGISTRY_COMPLETE.md` — add the qualifier
  under the totals block.
- `docs/aos-recovery/AOS_INSTALLATION_REPORT.md` — add the qualifier
  under the "files needing manual owner review" row.

Files **deliberately not touched**:

- `AOS_AGENT_RECOVERY_REPORT.md` (root) and `AOS_INSTALLATION_REPORT.md`
  (root) **already** carry the FU-18 qualifier; touching them again
  would risk drift.
- `docs/audits/hermes-full-repo-audit.md` and `docs/audits/hermes-file-inventory.md`
  both contain the literal string "233" only as **LOC counts**
  (`hermes_cli/main.py: 13,233 LOC`, `kanban_db.py: 6,233 LOC`) — false
  positives for the "agent claim" search. Not an honesty issue.
- `docs/orchestration/local-validation-gates.md:122` contains "2333" as
  a `duration_ms`. False positive.

## Plan (bounded steps)

1. Add the qualifier block (the same prose as
   `AOS_INSTALLATION_REPORT.md:19-30` / root
   `AOS_AGENT_RECOVERY_REPORT.md:45-57`) to each of the four owned
   files, immediately after the "totals" block where the bare "233"
   appears. Each insertion includes the marker "WC-4 honesty
   propagation, following FU-18" for traceability. [done]
2. No grep automation here — the four targets are explicit because
   the universe is small and the false-positive rate of a bare grep
   on "233" is too high to automate without a curated allowlist.

## Validation

- `uv run ruff check` → N/A (markdown).
- Manual grep: `rg -n '\b233\b' AOS_AGENT_REGISTRY_COMPLETE.md docs/aos-recovery/` →
  every match is now within 30 lines of "routed-catalog" qualifier
  text.
- `uv run python -m pytest` → unaffected (doc-only).

## Residual / follow-on

- A future packet could add a CI grep gate that fails the build on any
  bare "233 agents" / "233 distinct" / "341 agents" claim that is not
  within N lines of the qualifier. That is an automation play, not a
  doc fix — kept separate.
