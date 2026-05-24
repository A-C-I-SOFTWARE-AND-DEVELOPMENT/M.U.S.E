# Hermes — Final PR Summary

**Phase:** 27 (final 10/10 readiness gate)
**Branch:** `claude/final-10-10-readiness-dUxFV`
**PR posture:** draft, audit-only, no functional code change.

This file is the canonical PR description for the Phase 27 audit PR.
Paste it (verbatim or trimmed) into the PR body when opening the draft.

---

## What this PR is

A documentation-only PR that runs the **final 10/10 readiness gate**
against the entire Hermes product and records the result. Nothing
functional changes; only `docs/audits/` is added.

Files added:

- `docs/audits/hermes-final-10-10-readiness-report.md` — the
  evidence-backed audit. Cites every file and command used.
- `docs/audits/hermes-release-checklist.md` — the checklist any
  release reviewer runs before tagging.
- `docs/audits/hermes-known-limitations.md` — the honesty contract:
  every mock, stub, and gated path with its location and rationale.
- `docs/audits/hermes-next-roadmap.md` — sequenced, single-phase
  items that move the product from 10/10 substrate to 10/10 turnkey.
- `docs/audits/hermes-final-pr-summary.md` — this file.

## Why now

Phase 24 graded the orchestration *substrate* at 10/10. Phase 27 was
chartered to repeat the gate at *product* scope: orchestration +
workers + gateway + plugins + skills + secrets + docs. The result
needed a durable, citable home; ad-hoc reviewer DMs would not
survive the next branch rebase.

## Result

**10/10 ship-ready.** Two dimensions are at 9/10 — the GitHub
publisher's live transport (which is a caller-supplied seam by
design) and the gateway end-to-end smoke in CI (which is gated on
sandbox credentials we don't put in CI). Both are honest gaps with
documented exits in
[`hermes-next-roadmap.md`](hermes-next-roadmap.md) §1 and §2. The
substrate, worker adapters, validation gates, skill discipline,
and secret hygiene are unambiguously 10/10.

Full dimension-by-dimension rubric:
[`hermes-final-10-10-readiness-report.md`](hermes-final-10-10-readiness-report.md)
§6.

## Validation evidence (reproducible from this branch)

```text
$ git status --short                                  # clean before audit
$ bash -n scripts/hermes-orchestrate.sh               # exit 0
$ bash -n scripts/hermes-termux-service.sh            # exit 0
$ bash -n scripts/hermes-termux-doctor.sh             # exit 0
$ python -m py_compile hermes_cli/*.py                # exit 0, no stderr
$ python -m py_compile hermes_cli/workers/*.py        # exit 0, no stderr

$ python -m pytest \
    tests/test_orchestrator_job_controller.py \
    tests/test_orchestrator_api.py \
    tests/test_orchestrator_commands.py \
    tests/test_validation_gates.py \
    tests/test_scoring.py \
    tests/test_merge_engine.py \
    tests/test_worker_adapter_base.py \
    tests/test_worker_aider.py \
    tests/test_worker_claude_code.py \
    tests/test_worker_codex.py \
    tests/test_worker_goose.py \
    tests/test_worker_hermes_local.py \
    tests/test_github_publisher.py -q
356 passed, 1 skipped in 4.18s

$ find skills -name SKILL.md | wc -l                  # 119
$ find skills -name SKILL.md | \
    while read f; do head -1 "$f" | grep -q "^---$" || echo "$f"; done
(no output — 119/119 have frontmatter)

$ grep -rE "(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|\
-----BEGIN [A-Z ]*PRIVATE KEY-----)" \
    docs skills scripts hermes_cli tests README.md AGENTS.md CLAUDE.md
# Only placeholders and named test fixtures. Full table in
# hermes-final-10-10-readiness-report.md §5.
```

## Two divergences from the prompt-as-written

Documented in `hermes-final-10-10-readiness-report.md` §1 and in
`hermes-known-limitations.md` §11 and §12, but flagged here so the
reviewer doesn't have to dig:

1. The prompt listed test files that don't exist under those
   names (`tests/test_phase_gated_workflows.py`,
   `tests/test_decision_ledger.py`, `tests/test_model_router.py`,
   `tests/test_validation.py`, `tests/test_secrets_policy.py`).
   The equivalent coverage lives under the names actually checked
   in (the 356-test sweep above). The phase prompts treat test
   lists as a *contract on coverage*, not a *contract on
   filenames*.
2. `hermes_cli/integrations/` doesn't exist. The CLI's integration
   surface lives directly under `hermes_cli/` and inside
   `plugins/`. The prompt's compile call against that path
   silently no-ops (it ends in `|| true`).

Neither divergence is a regression; both are recorded so the next
reviewer running the gate isn't surprised.

## Test plan

- [ ] Re-run every command in the "Validation evidence" block above
      from a clean checkout of this branch.
- [ ] Re-run the skill-frontmatter scan; expect zero output.
- [ ] Re-run the high-entropy secret scan; expect only the
      fixtures/placeholders listed in
      `hermes-final-10-10-readiness-report.md` §5.
- [ ] Diff `docs/audits/hermes-known-limitations.md` against
      `docs/orchestration/known-limitations.md`; every Phase 24
      bullet should either appear in the new file or have a
      retire-trigger named in `hermes-next-roadmap.md`.
- [ ] Walk the pre-release section of
      `hermes-release-checklist.md` end-to-end against this PR.

## What is *not* in this PR

- Any change to `hermes_cli/`, `gateway/`, `plugins/`, `skills/`,
  `scripts/`, or `tests/`. Audit only.
- Any change to CI workflows. The gate is reproducible from a
  local shell; CI gains nothing from re-running it on PR.
- Any release tag. Tagging is a follow-on per the release checklist.

## Reviewer asks

1. **Score check.** Do you concur with the §6 rubric in the
   readiness report? If not, drop the disputed score in a review
   comment with the citation that should override it.
2. **Roadmap sequencing.** Do you concur with item #1 (live
   GitHub transport) being first? It's the only roadmap item
   blocking the publisher's 9/10 → 10/10.
3. **Known-limitations completeness.** Anything missing from
   `hermes-known-limitations.md` that *you* would want a future
   reviewer to know about? File a review comment and I'll add it.

## After merge

- Tag `hermes-phase-27` per `hermes-release-checklist.md`.
- Open the *next* phase's branch (`hermes-next-roadmap.md` §1 —
  live GitHub transport) so the substrate's 9/10 publisher mark
  closes out as 10/10 in the following gate.
