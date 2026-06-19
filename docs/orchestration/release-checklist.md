# muse orchestration — release checklist

Run this checklist for every Phase 24+ tagged release. Every item is
either a command you can paste and check the output of, or a single
boolean question with an obvious yes/no answer.

## Pre-release

- [ ] **Branch is up to date with `main`.** Confirm with:
      `git fetch origin && git log --oneline origin/main..HEAD`.
- [ ] **Orchestrator bash entry compiles cleanly.**
      `bash -n scripts/hermes-orchestrate.sh` exits 0.
- [ ] **Python modules compile cleanly.**
      `python -m py_compile hermes_cli/*.py hermes_cli/workers/*.py`
      exits 0.
- [ ] **Orchestration tests all pass.**
      ```
      pytest tests/test_orchestrator*.py tests/test_worker*.py \
             tests/test_scoring.py tests/test_merge_engine.py \
             tests/test_validation_gates.py tests/test_github_publisher.py \
             -q
      ```
      Expected: `60 passed`.
- [ ] **No real secrets in repo.** The high-entropy grep returns only
      documented placeholders and test fixtures (see
      `final-10-10-readiness-report.md` §6).
- [ ] **Skills lint.** All `SKILL.md` files have YAML frontmatter.
      ```
      while IFS= read -r f; do head -1 "$f" | grep -q "^---$" || echo "$f"; \
        done < <(find skills -name SKILL.md)
      ```
      Expected: no output.
- [ ] **`docs/orchestration/PHASES.md` has an entry for this phase.**
- [ ] **`docs/orchestration/known-limitations.md` is current.** If a new
      mock or stub was added since the previous release, it is listed.
- [ ] **No new dependencies introduced.** Orchestration is stdlib-only;
      `pyproject.toml` should not have changed for this phase.

## Release

- [ ] **Tag the head of the release branch.**
      ```
      git tag -a hermes-phase-24 -m "Phase 24 — release hardening + 10/10 final gate"
      git push origin hermes-phase-24
      ```
- [ ] **Branch is pushed.**
      `git push -u origin claude/hermes-release-hardening-10-10-Wx2MN`
      with retry-on-network-error per repo policy.
- [ ] **Open a draft PR** against `main` describing what changed and
      pointing reviewers at
      `docs/orchestration/final-10-10-readiness-report.md`.
- [ ] **PR body includes the validation evidence** from PHASES.md so
      reviewers can verify without re-running.
- [ ] **CI is green** before flipping out of draft.

## Post-release

- [ ] **Run a dry-run orchestration end-to-end** against a throwaway
      repo:
      ```
      bash scripts/hermes-orchestrate.sh --prompt "smoke" \
            --repo /tmp/hermes-smoke \
            --out /tmp/hermes-smoke/out
      ```
      Expected: `"status": "ok"` and a JSON descriptor at
      `/tmp/hermes-smoke/.hermes/publish/`.
- [ ] **Confirm PR auto-comments work in dry-run mode.** The publisher
      writes `pull_request_*.json` under `.hermes/publish/` and never
      contacts the network unless `HERMES_PUBLISH_LIVE=1` is set.
- [ ] **Confirm worktree cleanup.** After the smoke run, the directory
      `.hermes/worktrees/` should be empty.
- [ ] **Capture artefacts.** Attach the smoke-run `run-*.json`,
      `gates-*.json`, and the dry-run `pull_request_*.json` to the
      release notes for reproducibility.
- [ ] **Watch for the first live invocation.** If anyone flips
      `HERMES_PUBLISH_LIVE=1`, the resulting PR/issue body MUST be
      reviewed by a human before merge.

## Rollback

If a regression surfaces:

1. Revert the offending commit (do **not** force-push the release tag).
2. Re-run the pre-release checklist on `main + revert`.
3. Cut a new patch tag (`hermes-phase-24.1`, etc.).
