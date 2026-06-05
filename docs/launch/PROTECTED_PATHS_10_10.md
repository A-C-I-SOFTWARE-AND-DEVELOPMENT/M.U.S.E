# Protected Paths — Hermes 10/10 Program

> **Owner:** Sprint 0 (Baseline & Program Governance). **Created:** 2026-06-05.
> **Rule:** Any PR in the 10/10 program that mutates a path listed here requires
> **explicit reviewer signoff** from the named lane, and a note in the PR body
> explaining what changed and why it is safe. These paths concentrate the
> system's safety guarantees: weakening one silently can turn the product into a
> credential-leak, remote-shell, or approval-bypass risk.

This list is intentionally narrow. It is not "all important files" — it is the
set where a careless edit defeats a security control.

## 1. Decision & approval surfaces

Reviewer lane: **Security**. Do not downgrade any `refuse`→`ask` or `ask`→`auto`
path; do not remove an owner-phrase requirement.

- `hermes_cli/approval_policy.py`
- `tools/approval.py`
- `tools/tirith_security.py`
- `tools/slash_confirm.py`
- `hermes_cli/decision_ledger.py`
- `hermes_cli/orchestrator_ledger.py`
- `enterprise/judge.py`
- `enterprise/policy.py`
- *(Sprint 2 will add the unified `DecisionVerdict` engine — it joins this list on creation.)*

## 2. Secret detection & redaction

Reviewer lane: **Security**. Never narrow a secret regex set or remove a `.env`
blocklist entry without justification.

- `tools/tirith_security.py` (secret scanners / command risk)
- Secret-scan + blocklist code paths in `hermes_cli/validation.py`
- Secret-scan paths in `hermes_cli/github_publisher.py` (`scan_for_secrets`, staging blocklist)
- Any redactor used by the cockpit event/audit stream (`gateway/cockpit/event_log.py` and its payload redaction).

## 3. Gateway auth & device pairing

Reviewer lane: **Security / Gateway**. Tokens are hashed/compared in constant
time; pairing is rate-limited and locks out — keep it that way.

- `gateway/cockpit/auth.py` (bearer token, `hmac.compare_digest`)
- `gateway/pairing.py` (rate limit, lockout, code TTL, 0600 storage)

## 4. GitHub live publishing

Reviewer lane: **Security / Publisher**. `dry_run=True` is the default and must
stay the default; live publish must remain owner-gated and (once Sprint 5 is
revisited) repo-allowlisted.

- `hermes_cli/github_publisher.py`
- `plugins/github_assistant/*`

## 5. Remote execution bridge

Reviewer lane: **Security**. No path may execute arbitrary remote shell. Keep the
command allowlist (`("claude",)` default), per-job token, device allowlist, and
scrubbed audit log.

- `hermes_cli/remote_bridge.py`
- Bridge configuration in `hermes_cli/config.py`

## 6. Android permissions & secure storage

Reviewer lane: **Android / Security**. Any new permission triggers a protected-path
review and a note in `docs/jarvis-prime-app-permission-risk-register.md`.

- `apps/android/app/src/main/AndroidManifest.xml`
- `apps/android/app/src/main/java/com/aci/hermes/data/preferences/SecureTokenStore.kt`
  (EncryptedSharedPreferences + Android Keystore)

## 7. Dependencies, lockfiles & installers

Reviewer lane: **Security / Release**. Exact-pinned deps (no ranges) are a
deliberate supply-chain control (see the rationale comment in `pyproject.toml`).

- `pyproject.toml` (`[project.dependencies]`, optional-dependency extras)
- `uv.lock`
- `tools/lazy_deps.py` (lazy backend installer)
- Install/upgrade scripts under `scripts/`

## 8. Validation gates & test isolation

Reviewer lane: **QA / Security**. Do not weaken a blocking gate to non-blocking,
and do not remove the credential-isolation / deterministic-runtime fixtures.

- `hermes_cli/validation.py` (gate definitions, `critical=True` checks)
- `tests/conftest.py` (credential env-var filtering, isolated `HERMES_HOME`, deterministic runtime)

## Review protocol

1. PR touches a path above → label it `protected-path` and tag the named lane.
2. The PR body states: which control the path enforces, what changed, and why the
   control is preserved (with a test or a redaction/verdict trace as evidence).
3. The reviewer lane confirms no downgrade/bypass before merge.
4. If a change *must* relax a control, it requires an explicit, written owner
   decision recorded in the decision ledger — not an inline approval.
