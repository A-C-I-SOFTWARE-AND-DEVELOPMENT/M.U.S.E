# LaunchGate — Automated Merge Policy

**Scope:** repository merges to `main` (and to release-candidate
branches) for `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` and the
mirror `echerd27-design/hermes-agent`.

**Replaces:** the prior policy that required the owner to type
`Yes, with authorization.` for every merge. Repository merge approval
is now governed by validated automation; the owner phrase remains
required for the destructive runtime actions enumerated in
[`docs/jarvis-prime-operating-system.md`](../jarvis-prime-operating-system.md)
§ Owner Gates and in
`hermes_cli/jarvis_prime/owner_auth.py::OWNER_GATED_ACTIONS`.

## Why this exists

Manual phrase entry on every PR slowed down low-risk merges (docs,
chore, dependency bumps) without measurably improving safety —
branch protection plus CI was already doing the real work. At the
same time, weakening *runtime* gates (spend, deploy, credentials,
DNS, public posting, package publish, app-store submission,
regulated claims) is unacceptable. LaunchGate splits the two cleanly:
merges are gated by validation, runtime actions stay gated by the
phrase.

## Gate criteria — all must pass before auto-merge fires

Auto-merge may be enabled on a PR only after **every** item below is
satisfied. If any item is not satisfied, auto-merge must not be
enabled; if auto-merge is already queued and a check goes red, the
queued merge will not fire.

- [ ] PR is **mergeable** (no conflicts; `mergeable == "MERGEABLE"`).
- [ ] **Required GitHub checks** pass on the PR head commit.
- [ ] **Android `assembleDebug`** passes
      (`.github/workflows/android-build.yml` → `assemble-debug` job).
- [ ] **Android `testDebugUnitTest`** passes. *Wiring note:* this
      task is not yet a job in `android-build.yml`. Until it is
      wired, the operator must run
      `./gradlew --no-daemon testDebugUnitTest` locally on the PR
      head and attach the report before enabling auto-merge. A
      follow-up should add the job; do **not** drop this requirement
      to ship.
- [ ] **Android `lintDebug`** passes
      (`.github/workflows/android-build.yml` → `lint` job).
- [ ] **Python muse tests** pass:
      `python -m pytest tests/test_jarvis_prime_*.py tests/test_orchestrator_*.py -q`.
- [ ] **`ruff check`** passes
      (`.github/workflows/lint.yml` → `ruff enforcement (blocking)`).
- [ ] **Permission audit** passes — no new Android runtime
      permissions, no broadened scopes in skill/plugin manifests, no
      new `OWNER_GATED_ACTIONS` removals.
- [ ] **Security / redaction audit** passes — secrets stay out of
      memory, redaction rules in
      [`docs/security/private-local-security-guide.md`](../security/private-local-security-guide.md)
      and `SECURITY.md` are not weakened.
- [ ] **Launch checklist exists** for any user-facing or release-
      affecting change (e.g.
      [`docs/audits/hermes-release-checklist.md`](../audits/hermes-release-checklist.md)
      or
      [`docs/orchestration/release-checklist.md`](../orchestration/release-checklist.md)).
- [ ] **Rollback plan exists** in the PR description or linked from
      the launch checklist.

## Hard rules

- Auto-merge **must** use GitHub auto-merge
  (`gh pr merge <PR> --auto`). Local force merge is **not** allowed.
- **No force push.** `force_push` remains in `OWNER_GATED_ACTIONS`.
- **No bypass of branch protection.** Branch protection wins over
  auto-merge: if branch protection blocks the merge, auto-merge
  stays queued indefinitely and the operator must address the
  underlying block (missing review, failing check, stale base).
- **No merging red CI.** If any required check is failing or
  cancelled, auto-merge must not be enabled.
- **No auto-closing superseded PRs** as part of the merge flow.
  Cleanup of duplicate/superseded PRs is out of scope here; a
  separate cleanup workflow must be approved before any such
  automation lands.

## What did **not** change

The following runtime owner gates remain in place exactly as before
and still require the exact phrase `Yes, with authorization.`:

- spend money
- production deploy
- credential change (incl. OAuth, secrets, third-party accounts)
- DNS change
- post publicly
- package publish / app-store submission
- delete recovered sources / registry mutation /
  change default active agents
- force push
- regulated claim (legal, compliance, security, health, financial)
- emergency-stop release flow

The owner-phrase constant
(`hermes_cli/jarvis_prime/owner_auth.py::AUTHORIZATION_PHRASE`),
the `OwnerAuth` class, the
`hermes_cli/jarvis_prime/gates.py::owner_approval_gate`, redaction
policy, memory privacy rules, and audit/proof trails are unchanged.

## Operational handle

See the companion runbook:
[`AUTO_MERGE_RUNBOOK.md`](AUTO_MERGE_RUNBOOK.md).
