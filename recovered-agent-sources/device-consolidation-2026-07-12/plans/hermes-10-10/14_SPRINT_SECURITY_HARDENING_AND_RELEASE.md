# Sprint 14 — Security Hardening, Launch Readiness, and Release

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Convert the completed 10/10 loop into a release-quality product: secure defaults, docs, installers, migration, diagnostics, and an end-to-end launch gate.

## Release gate

The release is not ready until this exact flow passes:

```text
Android voice command
  -> gateway transcript
  -> job created
  -> worker produces patch
  -> validation passes
  -> phone approval requested
  -> user approves
  -> GitHub PR created
  -> Android shows PR URL and final job summary
  -> app/gateway restart
  -> session and job replay correctly
```

## Parallel agent lanes

| Lane | Agent | Branch | Mission |
|---|---|---|---|
| A | Security Agent | `sprint/14-security-hardening` | Final threat review, redaction audit, dependency/security scans. |
| B | QA Agent | `sprint/14-e2e-tests` | End-to-end smoke tests and launch gate script. |
| C | Installer Agent | `sprint/14-install-upgrade` | Verify install/update flows for Linux/macOS/WSL/Windows/Termux/Android. |
| D | Docs Agent | `sprint/14-docs` | Write user docs, operator runbook, troubleshooting, architecture overview. |
| E | Android Agent | `sprint/14-android-release` | Release build, permissions audit, crash handling, versioning. |
| F | Backend Agent | `sprint/14-diagnostics` | `hermes doctor --10-10` readiness check. |
| G | Reviewer Agent | `sprint/14-final-review` | Final launch review and no-go list. |

## Required artifacts

- `docs/launch/10_10_RELEASE_CHECKLIST.md`
- `docs/launch/10_10_E2E_RUNBOOK.md`
- `docs/security/10_10_SECURITY_REVIEW.md`
- `docs/android/cockpit_user_guide.md`
- `docs/voice/voice_first_cockpit.md`
- `docs/orchestration/prompt_to_pr_production.md`
- `docs/troubleshooting/10_10_troubleshooting.md`
- `scripts/hermes-10-10-smoke.sh`
- `hermes doctor --10-10` or equivalent diagnostic command

## Security checklist

- Secrets redacted from logs, events, PR bodies, Android UI, diagnostics.
- Remote bridge cannot execute arbitrary shell.
- GitHub live publish allowlist enforced.
- Approval phrase required where configured.
- Pairing tokens hashed at rest.
- Device revocation works.
- Protected paths policy enforced.
- Android permissions reviewed.
- Dependency lock checks pass.
- OSV/security scanning reviewed.
- No debug endpoints exposed on non-localhost by default.

## E2E test matrix

| Scenario | Expected result |
|---|---|
| Happy path Prompt -> PR | PR URL visible on Android. |
| Worker missing CLI | Proposal fallback or clear failure. |
| Validation failure | No PR; failure visible. |
| Secret in diff | Refuse; no publish. |
| Protected path change | Ask/refuse based on policy. |
| Phone offline during approval | Pending approval visible on reconnect. |
| Gateway restart mid-job | Job replay restores state. |
| Duplicate approval submit | Idempotent result. |
| Revoked device approval | Refused. |
| Remote bridge bad signature | Rejected. |

## Launch phases

### Alpha

- Localhost gateway.
- Android debug/internal build.
- Dry-run GitHub publish by default.
- One or two real worker actuators.
- No always-on wake word.

### Beta

- Live GitHub PR allowlist.
- Optional push notifications.
- Optional Supabase/Vercel.
- Remote bridge behind feature flag.

### Stable

- Documented upgrade path.
- Full diagnostics.
- Remote bridge threat model complete.
- E2E smoke repeatable by user.

## Acceptance criteria

- Full target loop passes.
- User docs describe the loop without requiring code knowledge.
- `doctor` reports missing config clearly.
- Security review has no unresolved launch blockers.
- Release notes list limitations honestly.
- Rollback procedure exists.

## Reviewer prompt

```text
Perform final release review. Block release for any unredacted secret path, live publish bypass, approval bypass, remote bridge arbitrary shell behavior, Android permission surprise, irreplayable job state, or undocumented operator requirement.
```

## Definition of done

Hermes 10/10 is releasable as a real personal AI operating layer, not just a set of impressive subsystems.
