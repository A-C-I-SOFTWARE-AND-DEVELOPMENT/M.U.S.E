# LaunchGate — Reviewer Checklist

One-page checklist a reviewer runs through before enabling GitHub
auto-merge on a MUSE-Prime / Hermes PR. Pairs with the full policy
in [`AUTOMATED_MERGE_POLICY.md`](AUTOMATED_MERGE_POLICY.md) and the
operator steps in [`AUTO_MERGE_RUNBOOK.md`](AUTO_MERGE_RUNBOOK.md).

Auto-merge replaces the **repository-merge ceremony** only. The
**runtime owner gate** (the `Yes, with authorization.` phrase guarding
spend, deploy, credentials, DNS, public posts, package publish,
app-store submission, force push, registry mutation, regulated
claims, and the emergency-stop release flow) is unchanged.

## Gate status — quick read

- [ ] PR is `MERGEABLE` (no conflicts, base is up to date enough).
- [ ] `reviewDecision == APPROVED` (or `null` if branch protection
      does not require reviewers).
- [ ] `statusCheckRollup` has **zero** `FAILURE` / `CANCELLED` /
      `PENDING` entries for required checks.

If any of these is `false`, **stop here**. Do not enable auto-merge.

## Required CI checks — every one must be `SUCCESS`

- [ ] `Build debug APK` (`android-build.yml`)
- [ ] `Lint` (`android-build.yml`)
- [ ] `Android JVM unit (testDebugUnitTest)` (`jarvis-prime-unit.yml`)
- [ ] `Python unit (MUSE + redact + orchestrator)` (`jarvis-prime-unit.yml`)
- [ ] `ruff enforcement (blocking)` (`lint.yml`)
- [ ] `Tests` (`tests.yml`)
- [ ] `Orchestration tests` (`orchestration-tests.yml`)
- [ ] `Scan PR for critical supply chain risks` (`supply-chain-audit.yml`)
- [ ] `LaunchGate aggregate` (`launch-gate.yml`)

> The two `jarvis-prime-unit.yml` checks above are produced by the
> curated, launch-critical workflow `.github/workflows/jarvis-prime-unit.yml`
> (Android `testDebugUnitTest` + the MUSE / redaction / orchestrator
> Python subset). It is intentionally narrower and faster than the
> comprehensive `android-build.yml` / `tests.yml` suites, and its job
> `name:` strings are a contract these checklist entries key on — keep them
> in sync. On a PR, `LaunchGate aggregate` prints an advisory red/green
> rollup of these checks to its job summary.

If any required check is missing from branch protection, add it
**there** — do not waive it here.

## Permission audit (Android)

- [ ] `AndroidManifest.xml` `<uses-permission>` set matches the
      launch allowlist exactly:
      `POST_NOTIFICATIONS`, `FOREGROUND_SERVICE`,
      `FOREGROUND_SERVICE_DATA_SYNC`.
- [ ] No new `READ_MEDIA_*`, `READ_EXTERNAL_STORAGE`,
      `WRITE_EXTERNAL_STORAGE`, `RECORD_AUDIO`, `CAMERA`,
      `SYSTEM_ALERT_WINDOW`, or location permission.
- [ ] The three independent permission tests still pass:
      `ManifestPermissionsTest`, `ManifestPermissionsUnchangedTest`,
      `AndroidManifestPermissionsTest` (and any
      `AvatarPickerPermissionAuditTest` added on later branches).

## Runtime owner-gate audit (Python)

The following must remain unmodified by the PR:

- [ ] `hermes_cli/jarvis_prime/owner_auth.py` —
      `AUTHORIZATION_PHRASE` constant present and equal to
      `"Yes, with authorization."`.
- [ ] `hermes_cli/jarvis_prime/owner_auth.py` — `OwnerAuth` class
      present with the same `OWNER_GATED_ACTIONS` set.
- [ ] `apps/android/app/src/main/java/com/aci/hermes/data/emergency/*`
      (4 files) — not in diff.
- [ ] Redaction modules — not in diff:
      `agent/redact.py`, `SecretRedactor.kt`, `MemoryRedactor.kt`,
      `PrivacyRedactor.kt`.

If any of these moved, the PR is **not** eligible for auto-merge —
it needs the runtime owner-gate flow (the in-app phrase) instead.

## Safety surface

- [ ] PR description includes a rollback plan.
- [ ] PR description names a launch checklist (e.g.
      `docs/audits/hermes-release-checklist.md`) for any
      user-facing or release-affecting change.
- [ ] If the PR adds a new external dependency, the supply-chain
      audit job is green and the dependency pin is exact (no
      ranges) per `pyproject.toml` policy.

## Hard rules — never bend these

- Auto-merge **must** be enabled via GitHub's first-class auto-merge
  (`gh pr merge --auto` or the API equivalent). No local merge,
  no `--admin` override, no `--no-verify`, no `--no-gpg-sign`.
- No force push. `force_push` stays in `OWNER_GATED_ACTIONS`.
- Branch protection wins. If branch protection blocks the merge,
  auto-merge stays queued — fix the underlying block.
- Red CI never merges. If a required check is `FAILURE` /
  `CANCELLED`, disable auto-merge until the cause is addressed.

## When to skip auto-merge entirely

Reach for the runtime owner-gate flow (require the phrase) when the
PR touches any of:

- spend / deploy / credentials / DNS
- public posting / package publish / app-store submission
- DELETE / DROP / TRUNCATE on production data
- the emergency-stop subsystem
- the `AUTHORIZATION_PHRASE` constant itself
- a force push or registry mutation

These cases predate LaunchGate and are out of scope for auto-merge.
