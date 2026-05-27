# Hermes — Release Checklist

**Phase:** 27 (final 10/10 readiness gate)
**Use:** run this checklist for every Hermes release from Phase 27
forward. Supersedes the orchestration-only checklist at
[`docs/orchestration/release-checklist.md`](../orchestration/release-checklist.md)
for product-level releases (the orchestration-only list still
applies to substrate-scoped phases).

Every item is either a command whose output you check, or a single
yes/no question with an obvious answer. Tick the box as you go.

---

## Pre-release

### Repo state

- [ ] **Branch up to date with `main`.**
      `git fetch origin && git log --oneline origin/main..HEAD`
      shows only commits intended for this release.
- [ ] **Working tree clean.** `git status --short` returns nothing
      except files this release deliberately adds.
- [ ] **No `WIP:` / `fixup!` / `squash!` commits left over.**
      `git log --oneline origin/main..HEAD | grep -iE 'wip|fixup|squash'`
      returns no rows.

### Static checks

- [ ] **Orchestrator bash entry compiles.**
      `bash -n scripts/hermes-orchestrate.sh` exits 0.
- [ ] **Termux scripts compile.**
      `bash -n scripts/hermes-termux-service.sh` and
      `bash -n scripts/hermes-termux-doctor.sh` both exit 0.
- [ ] **All CLI Python modules compile.**
      `python -m py_compile hermes_cli/*.py hermes_cli/workers/*.py`
      exits 0 with no stderr.
- [ ] **No new dependencies for orchestration.** `pyproject.toml`
      diff against `main` shows no additions in the orchestration
      stack unless the phase explicitly approved them.

### Tests

- [ ] **Orchestration + worker + publisher tests pass.**

      ```
      python -m pytest \
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
      ```

      Expected: **356 passed, 1 skipped** (the platform-gated
      `test_orchestrator_api.py` skip). If a number changed, update
      this checklist in the same PR.

- [ ] **Full test suite passes in CI** (not just the orchestration
      slice). At minimum: green on Linux + macOS, Python 3.11 and
      3.12.

### Security & hygiene

- [ ] **No high-entropy credentials in the repo.**

      ```
      grep -rE "(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|\
-----BEGIN [A-Z ]*PRIVATE KEY-----)" \
        docs skills scripts hermes_cli tests README.md AGENTS.md CLAUDE.md
      ```

      Every hit must already appear in
      `docs/audits/hermes-final-10-10-readiness-report.md` §5. If a
      new one appears, it must be either a placeholder or a fixture
      *and* it must be appended to that table in this same PR.

- [ ] **Skill frontmatter present everywhere.**

      ```
      find skills -name SKILL.md | while read f; do \
        head -1 "$f" | grep -q "^---$" || echo "MISSING: $f"; \
      done
      ```

      Expected: no output.

- [ ] **`tests/conftest.py` credential-strip still active.**
      Spot-check with `grep -n credential tests/conftest.py`; the
      fixture should still be wiping env vars before each test.

### Documentation

- [ ] **`docs/orchestration/PHASES.md` has an entry for this phase.**
- [ ] **`docs/audits/hermes-known-limitations.md` is current.** Any
      new mock, stub, or "out of scope" item added since the last
      release is listed here.
- [ ] **`docs/audits/hermes-next-roadmap.md` is current.** Any
      roadmap item completed this phase is removed; new ones are
      appended.
- [ ] **`README.md` and `AGENTS.md` reflect new user-visible
      commands.** Spot-check `/orchestrate`, `/orchestrator status`,
      `/decision-ledger show`, `/model-router explain`,
      `/ai-radar update`, `/best-coding-tool-mission status`.

---

## Release

- [ ] **Tag the head of the release branch.** Use an annotated tag.

      ```
      git tag -a hermes-phase-27 \
        -m "Phase 27 — final 10/10 readiness gate"
      git push origin hermes-phase-27
      ```

- [ ] **Branch pushed with `-u`.**

      ```
      git push -u origin claude/final-10-10-readiness-dUxFV
      ```

      On network failure, retry up to four times with exponential
      backoff (2s, 4s, 8s, 16s) per repo policy.

- [ ] **Draft PR opened against `main`.** Title is short
      (< 70 chars); body points at
      `docs/audits/hermes-final-10-10-readiness-report.md` and
      includes the validation evidence so reviewers do not need to
      re-run the gate locally.

- [ ] **CI green** on the PR before flipping out of draft.

- [ ] **Repository merges are governed by LaunchGate automated
      validation. Runtime owner-gated actions remain protected.**
      Enable GitHub auto-merge per
      [`docs/launch/AUTOMATED_MERGE_POLICY.md`](../launch/AUTOMATED_MERGE_POLICY.md);
      branch protection still requires the configured reviewer
      approvals before the queued merge will fire.

---

## Post-release

- [ ] **Dry-run end-to-end smoke** against a throwaway repo:

      ```
      bash scripts/hermes-orchestrate.sh --prompt "smoke" \
            --repo /tmp/hermes-smoke \
            --out /tmp/hermes-smoke/out
      ```

      Expected: `"status": "ok"` and a JSON descriptor at
      `/tmp/hermes-smoke/.hermes/publish/`. No network egress.

- [ ] **Worktree cleanup verified.** After the smoke run,
      `/tmp/hermes-smoke/.hermes/worktrees/` is empty.

- [ ] **Publisher remained in dry-run.** The smoke run's descriptor
      JSON was written under `.hermes/publish/` and the
      `HERMES_PUBLISH_LIVE` env var is *not* set in the operator's
      shell.

- [ ] **Termux scripts spot-checked on at least one Android device**
      (or in a Termux container) if any Termux-touching change
      landed.

- [ ] **Artefacts captured.** Attach the smoke-run `run-*.json`,
      `gates-*.json`, and the dry-run `pull_request_*.json` to the
      release notes for reproducibility.

- [ ] **First live invocation watch.** If anyone flips
      `HERMES_PUBLISH_LIVE=1`, the resulting PR/issue body MUST be
      reviewed by a human before merge. The publisher does not
      enforce this; we do.

---

## Rollback

If a regression surfaces after release:

1. Revert the offending commit on a new branch — **do not**
   force-push the release tag.
2. Re-run the pre-release section of this checklist on
   `main + revert`.
3. Cut a new patch tag (`hermes-phase-27.1`, `hermes-phase-27.2`,
   …) and open a follow-up PR.
4. Append a short note to
   `docs/audits/hermes-known-limitations.md` describing the
   regression and the fix so the next release reviewer sees it
   without having to re-derive it from git history.
