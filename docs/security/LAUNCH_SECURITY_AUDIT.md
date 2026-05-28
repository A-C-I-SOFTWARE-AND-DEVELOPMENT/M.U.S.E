# Launch Security & Owner-Gate Audit — PR #131

## Scope

Independent security review of the JARVIS Prime + Hermes launch candidate.

- **PR:** #131 — `claude/hopeful-bardeen-KBVqi`
- **Head commit reviewed:** `d0caf92` (`revert(android-ci): drop unit-tests job added in 2276e04`)
- **Base commit:** `bc97e43` (also `main` HEAD at audit time, and the merge-base of the two refs)
- **Diff scope:** 164 files, +25 541 / −558 lines
- **Audit branch:** `claude-review/launch-security-owner-gate-audit-m3yjL` (this branch — rebased onto the PR head so this doc lands on the launch line of work)

## Mission

Prove the candidate:

1. does not leak secrets,
2. does not weaken owner gates, and
3. does not allow destructive actions without explicit owner approval.

## Methodology

Read-only inspection against the PR head ref using `git show`, `git grep`, and
`git diff origin/main..origin/claude/hopeful-bardeen-KBVqi`. The audit prefers
literal file:line evidence over prose claims. All file paths and line numbers
in this document are pinned to `d0caf92`.

## Verdict

**PASS.** No fixes required.

The candidate does not leak secrets, weaken owner gates, or allow destructive
actions without approval. The six audit dimensions and their evidence follow.

---

## 1. Owner gates

### 1.1 Authorization phrase is the exact literal

`hermes_cli/jarvis_prime/owner_auth.py:18`:

```python
AUTHORIZATION_PHRASE: str = "Yes, with authorization."
```

`git diff origin/main..origin/claude/hopeful-bardeen-KBVqi -- hermes_cli/jarvis_prime/owner_auth.py`
returns no output — the phrase declaration is identical to base.

The module docstring (`owner_auth.py:1-8`) calls out explicitly that minor
variations ("yes with authorization", "yes - with authorization") do not
authorize. Confirmed at all comparison sites:

| Site                                                | Comparison                                         |
|-----------------------------------------------------|----------------------------------------------------|
| `hermes_cli/jarvis_prime/owner_auth.py:92`          | `phrase.strip() != AUTHORIZATION_PHRASE`           |
| `hermes_cli/jarvis_prime/gates.py:254`              | `phrase != AUTHORIZATION_PHRASE` (after `.strip()` at L253) |
| `hermes_cli/jarvis_prime/__main__.py:246`           | `phrase.strip() != AUTHORIZATION_PHRASE`           |
| `hermes_cli/jarvis_prime/work_packet.py:109`        | Field default: `owner_authorization_phrase: str = AUTHORIZATION_PHRASE` |

No fuzzy match, no `.lower()`, no `startswith`, no regex. The check is byte-exact.

### 1.2 Owner-gated action set is unchanged and complete

`hermes_cli/jarvis_prime/owner_auth.py:22-40` — `OWNER_GATED_ACTIONS` (frozenset):

```text
spend_money                  package_publish
post_publicly                app_store_submission
create_third_party_account   delete_recovered_sources
oauth_change                 modify_secrets
credential_change            change_default_active_agents
production_deploy            registry_mutation
dns_change                   regulated_claim
main_branch_merge
force_push
```

Coverage check against the mission's required categories:

| Required category                | Covered by                                      |
|----------------------------------|-------------------------------------------------|
| merge                            | `main_branch_merge`                             |
| deploy                           | `production_deploy`                             |
| release / publish                | `package_publish`, `app_store_submission`       |
| DNS                              | `dns_change`                                    |
| secrets                          | `modify_secrets`, `credential_change`, `oauth_change` |
| public posting                   | `post_publicly`                                 |
| spending                         | `spend_money`, `create_third_party_account`     |
| destructive operations           | `force_push`, `delete_recovered_sources`        |
| compliance / regulated statements| `regulated_claim`                               |
| default-agent / registry mutation| `change_default_active_agents`, `registry_mutation` |

`git diff origin/main..origin/claude/hopeful-bardeen-KBVqi -- hermes_cli/jarvis_prime/owner_auth.py`
shows no diff — the set is unchanged at the launch.

### 1.3 No bypass paths

Searched the audited code surfaces (`agent/`, `hermes_cli/`, `gateway/`,
`orchestrator/`, `tools/`) for any of:

```
bypass | skip_auth | no_auth | auto_approve | AUTO_APPROVE | FORCE_APPROVE | OWNER_OVERRIDE | YOLO
```

All hits fall into one of these unrelated categories:

- **Provider / cache bypass** (e.g. `agent/auxiliary_client.py:2940`, `agent/model_metadata.py:1442`) — talks about provider capacity / quota caches, not authorization.
- **Codex transport sandbox** (`agent/transports/codex_app_server_session.py:150-151`, fields `auto_approve_exec` / `auto_approve_apply_patch`) — this auto-approves the Codex transport's *shell sandbox* for inline tool calls, not the owner-gate set; it never grants any of the 16 owner-gated action categories.
- **`HERMES_YOLO_MODE` / `--yolo`** (`hermes_cli/main.py:1435`, `hermes_cli/oneshot.py:9`, `hermes_cli/tips.py:74`) — bypasses **dangerous-command approval prompts** (shell command Y/N), explicitly not owner gates. `git grep -nE 'YOLO|yolo' origin/claude/hopeful-bardeen-KBVqi -- hermes_cli/jarvis_prime/` returns **no results** — YOLO has no reach into the owner-gate subsystem.
- **Prompt-injection *detection*** (`agent/prompt_builder.py:41`) — `r'act\s+as.*bypass\s+restrictions'` is a regex that *flags* attempts to bypass system restrictions; it's a defensive signal, not a bypass mechanism.
- **`should_bypass_active_session` in `hermes_cli/commands.py:406`** — concerns slash-command routing inside an active session, not authorization.

The owner-gate subsystem (`hermes_cli/jarvis_prime/owner_auth.py`,
`gates.py`, `__main__.py`, `work_packet.py`) has no environment variable,
CLI flag, debug toggle, or test hook that grants an action category without
the literal phrase.

### 1.4 `owner_approval_gate` rejects on every wrong-path branch

`hermes_cli/jarvis_prime/gates.py:232-263` is the single choke point.
Failure modes:

- Unknown action category in the packet → `FAIL` (`gates.py:244-250`).
- Missing or mismatched phrase → `NEEDS_OWNER_APPROVAL` with the literal
  reason `f"awaiting exact phrase: {AUTHORIZATION_PHRASE!r}"` (`gates.py:254-259`).
- Phrase match + every action category in `OWNER_GATED_ACTIONS` → `PASS`.

There is no "skip-this-gate" code path.

---

## 2. Redaction

### 2.1 Python redaction (`agent/redact.py`, 544 LOC at head)

Pattern coverage (verified by reading the file):

| Class                       | Patterns                                                                                                                    |
|-----------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| LLM / aggregator vendors    | OpenAI `sk-*`, Anthropic `sk-ant-*`, OpenRouter `sk-or-*`, xAI `xai-*`, Mistral, Cohere, Together, Fireworks, DeepSeek, Groq |
| Cloud                       | AWS `AKIA*`/`ASIA*`, GCP `AIza*`, DigitalOcean `dop_*`                                                                       |
| Source-control / DevOps     | GitHub `ghp_/gho_/ghu_/ghs_/ghr_/github_pat_`, GitLab, npm, PyPI                                                             |
| Messaging                   | Slack `xox[baprs]`, Discord bot tokens, Telegram bot tokens                                                                  |
| Payments / SaaS             | Stripe `sk_live_/sk_test_/rk_live_`, SendGrid                                                                                |
| Model hubs                  | HuggingFace `hf_*`, Replicate                                                                                                |
| Generic credential shapes   | `-----BEGIN ... PRIVATE KEY-----` blocks, JWT (`eyJ...` 3-segment), DB connection-string passwords, `Authorization: Bearer`  |
| Identifier / PII            | URL userinfo, URL query secrets, E.164 phone numbers, Discord mention snowflakes, form-encoded body keys (exact match)       |

Sensitive query parameter and body-key lists are exact-match (case-insensitive)
at `agent/redact.py:21-54` — `token_count` and `session_id` do **not** match
`token` / `session`.

Default-on per `agent/redact.py:60-63`: `HERMES_REDACT_SECRETS` is snapshotted
at import time, so an LLM-generated `export HERMES_REDACT_SECRETS=false` at
runtime cannot disable redaction mid-session.

### 2.2 Two new audit-safe log sanitizers (this PR)

`agent/redact.py:238-310` adds two helpers used by 68 call sites across
`agent/agent_init.py`, `cron/scheduler.py`, `gateway/run.py`,
`gateway/platforms/webhook.py`, etc.:

- **`safe_audit_identifier(value)`** — strict shape check on
  identifier-like values (env var name, skill name, session id, chat id).
  Validates by `re.sub`-stripping every character outside
  `[A-Za-z0-9_.:\-]` and comparing against the original; any mismatch or
  non-letter leading character yields `<redacted>`. Output of `re.sub` is a
  freshly composed string — CodeQL's Python flow library treats
  `re.sub` output as sanitized, which is the structural property used here.
- **`safe_log_summary(value, max_preview=0)`** — by default returns
  `f"<{len(value)} chars>"` so **no byte** of the original value reaches
  the log line. With `max_preview > 0`, up to `max_preview` characters are
  passed through `re.sub` against a printable-ASCII allow-list before
  emission.

Both helpers are **structural barriers**, not annotation-only suppressions.
They are the correct response to CodeQL's
`py/clear-text-logging-sensitive-data` taint analysis on identifiers that
flow from credential-handling code paths.

### 2.3 Android redaction layers

Three classes cover three different surfaces:

- **`apps/android/app/src/main/java/com/aci/hermes/data/audit/SecretRedactor.kt`** (90 LOC, new) — guards the audit UI and clipboard copy. Patterns: private-key blocks, JWT, OpenAI / GitHub / Slack / AWS / Google provider tokens, `Authorization: <bearer|basic>` headers, generic `KEY=VALUE` assignments for any of `api_key, secret, token, password, passwd, pwd, access_key, private_key, client_secret, auth, bearer, session`. Marker: `[REDACTED]`. Tests: `SecretRedactorTest.kt` (91 LOC).
- **`apps/android/app/src/main/java/com/aci/hermes/data/memory/MemoryRedactor.kt`** (151 LOC, new) — guards the memory write path. Strips secret hints, high-entropy tokens, email, phone, social handles; demotes long-term emotional records to ephemeral so they don't accumulate cross-session identity. Tests: `MemoryRedactorTest.kt` (113 LOC).
- **`apps/android/app/src/main/java/com/aci/hermes/data/social/PrivacyRedactor.kt`** (161 LOC, new) — guards social-research output before it reaches storage or UI. Strips handles, platform URLs (with a small whitelist of legitimate platform domains), real-name pairs, email, phone; strips identity from provenance lines; drops auth-walled URLs. Designed to be over-eager: per `PrivacyRedactorTest.kt` (170 LOC), it prefers false positives over leaks.

### 2.4 Diagnostics / audit export

The Android `AuditRepository.kt` (533 LOC, new) routes every UI render of audit
material through `SecretRedactor.redact(...)` before display. The Python
diagnostics path uses `safe_log_summary` for any byte that could be tainted
from a credential-bearing code path.

---

## 3. CodeQL

### 3.1 No project-level CodeQL config exists

```
$ git ls-tree -r origin/claude/hopeful-bardeen-KBVqi -- '.github/codeql/'
(empty)
$ git ls-tree -r origin/claude/hopeful-bardeen-KBVqi | grep -iE '(codeql|\.qhelp|\.ql)$'
(empty)
$ git ls-tree -r origin/claude/hopeful-bardeen-KBVqi -- '.github/workflows/' | grep -iE 'codeql|security'
(empty)
```

The project relies on GitHub's default CodeQL setup. There is no
`codeql-config.yml`, no `paths-ignore`, no `query-filters`, no language
overrides committed in the repo to weaken.

### 3.2 No new inline suppressions added in the audited trees

`git grep -nE '(# nosec|# noqa: S|codeql\[|lgtm\[|# pragma: allowlist|nopep8.*S)' origin/claude/hopeful-bardeen-KBVqi -- 'agent/' 'hermes_cli/' 'gateway/' 'tools/' 'orchestrator/'` returns these hits, **all pre-existing** (`git diff origin/main..origin/claude/hopeful-bardeen-KBVqi` for each path is empty for the suppression lines):

| Site                                       | Comment                                              | Class     |
|--------------------------------------------|------------------------------------------------------|-----------|
| `gateway/platforms/telegram.py:830`        | `# noqa: SLF001`                                     | ruff style (private member access), not security |
| `gateway/run.py:3519-3522`                 | `# noqa: SLF001 — snapshot under lock`               | ruff style, not security |
| `hermes_cli/kanban_db.py:5357`             | `# noqa: S603 -- argv is a fixed list built above`   | bandit; argv is internal — explanation documented |
| `hermes_cli/validation.py:518`             | `# noqa: S603 — argv is built internally.`           | bandit; argv is internal — explanation documented |
| `tools/discord_tool.py:170`                | `# nosec — detection is best-effort`                 | bandit; legacy on an exception path, not a security suppression of vulnerable code |
| `tools/mcp_oauth_manager.py:495`           | `# noqa: SLF001`                                     | ruff style, not security |

No `# codeql[query-id]` or `# lgtm[query-id]` annotations exist anywhere in
the audited trees, before or after the PR.

### 3.3 New sanitizers are real, not suppressions

The CodeQL-related work this PR adds is `safe_audit_identifier` and
`safe_log_summary` (§ 2.2). Both produce their output via `re.sub` against
an explicit allow-list, which is a **structural** sanitizer that CodeQL's
flow library recognizes as a taint barrier. They do not silence the alert;
they remove the underlying cleartext-credential dataflow from the log
statement. This is the correct response to
`py/clear-text-logging-sensitive-data`.

---

## 4. Android permissions

`apps/android/app/src/main/AndroidManifest.xml` (full file):

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />

    <application
        android:name=".HermesApplication"
        android:allowBackup="true"
        android:dataExtractionRules="@xml/data_extraction_rules"
        android:fullBackupContent="@xml/backup_rules"
        ...
```

Total permissions declared: **3**, all minimum-required for a foreground sync
service that posts notifications. The manifest declares **no** Internet, no
storage, no media. The data-sync service is exposed `android:exported="false"`.

Explicit absence check:

| Permission                       | Present? |
|----------------------------------|----------|
| `RECORD_AUDIO`                   | No       |
| `SYSTEM_ALERT_WINDOW`            | No       |
| `READ_SMS` / `SEND_SMS` / `RECEIVE_SMS` | No |
| `READ_CONTACTS` / `WRITE_CONTACTS` | No     |
| `READ_CALL_LOG` / `WRITE_CALL_LOG` | No     |
| `READ_PHONE_STATE`               | No       |
| `ACCESS_FINE_LOCATION` / `ACCESS_COARSE_LOCATION` | No |
| `CAMERA`                         | No       |
| `READ_EXTERNAL_STORAGE` / `WRITE_EXTERNAL_STORAGE` | No |
| Internet                         | Not declared (the app is on-device-only) |

Diff vs base: `git diff origin/main..origin/claude/hopeful-bardeen-KBVqi -- apps/android/app/src/main/AndroidManifest.xml` is empty.

### 4.1 Backup is locked down

Both `backup_rules.xml` and `data_extraction_rules.xml` exclude the two
stores Hermes uses for user-generated content:

- `datastore/hermes_settings.preferences_pb`
- `hermes_tasks.json`

`data_extraction_rules.xml` additionally excludes both from
device-to-device transfer. These exclusions are asserted by
`apps/android/app/src/test/java/com/aci/hermes/backup/BackupRulesTest.kt`.

---

## 5. Emergency stop

`apps/android/app/src/main/java/com/aci/hermes/data/emergency/EmergencyStopController.kt`
(300 LOC, new) implements a five-state machine with audit. The two
properties the mission cares about — **visible stop** and **non-silent
resume** — are both enforced.

### 5.1 Resume is two-phase and id-bound

```kotlin
suspend fun requestResume(requestedBy: String, reason: String? = null): ResumeApproval? {
    val current = state.value
    if (!current.isActive) return null
    val approval = ResumeApproval(id = idGenerator(), ...)   // fresh UUID per request
    ...
    repository.commit(event = event, pendingApproval = approval)
    return approval
}

suspend fun approveResume(approvalId: String, approver: String): Boolean {
    val pending = pendingApproval.value ?: return false
    if (pending.id != approvalId) return false               // replay / stale rejected
    ...
    repository.commit(state = EmergencyStopState.INACTIVE, ...)
}
```

`deescalate()` explicitly forbids transitioning to `INACTIVE`:

```kotlin
require(target.isActive) {
    "deescalate() cannot return to INACTIVE — use requestResume()/approveResume()"
}
```

There is **no timer-based auto-resume** and **no silent resume**. Every
transition writes an `EmergencyStopAuditEvent` (engage, escalate,
deescalate, resume_requested, resume_approved, resume_denied, resume).
State persists via `EmergencyStopRepository` (DataStore) so the stop
survives process restart.

### 5.2 Stop is visible in the UI

`apps/android/app/src/main/java/com/aci/hermes/ui/components/EmergencyStopButton.kt`
(104 LOC, new) exposes the stop in the navigation shell. The button uses
`JarvisCrimson` colors with a Bolt icon, and one tap opens an
`AlertDialog` confirmation — the destructive action is **never one-tap**:

```kotlin
/**
 * Emergency stop — halt every active Jarvis task.
 *
 * One tap opens a confirmation dialog. The destructive action is never
 * one-tap; the dialog forces a deliberate second tap.
 */
```

---

## 6. Tests

### 6.1 Required suites green

```
$ python3 -m pytest tests/test_jarvis_prime_*.py tests/test_orchestrator_*.py tests/agent/test_redact.py -q
493 passed, 1 skipped in 6.84s
```

### 6.2 Lint clean

```
$ ruff check
All checks passed!
```

### 6.3 No new tests added by this audit

Direct inspection in §§ 1-5 found no confirmed coverage gap that the
"Allowed files if fixes are needed" list could address. Every property
this audit cares about is already covered:

- Owner-gate semantics: `tests/test_jarvis_prime_owner_auth.py`,
  `tests/test_jarvis_prime_gates.py`, `tests/test_jarvis_prime_work_packet.py`.
- Redaction: `tests/agent/test_redact.py` (Python),
  `apps/android/app/src/test/java/com/aci/hermes/data/audit/SecretRedactorTest.kt`,
  `…/data/social/PrivacyRedactorTest.kt`, `…/memory/MemoryRedactorTest.kt`.
- Backup exclusions: `…/backup/BackupRulesTest.kt`.

---

## Files reviewed

Grouped by surface (164 files in the PR; the surfaces below are where the
audit looked):

**Python — owner-gate core**
- `hermes_cli/jarvis_prime/owner_auth.py`
- `hermes_cli/jarvis_prime/gates.py`
- `hermes_cli/jarvis_prime/__main__.py`
- `hermes_cli/jarvis_prime/work_packet.py`
- `hermes_cli/jarvis_prime/__init__.py`

**Python — redaction**
- `agent/redact.py`
- `agent/agent_init.py` (call sites)
- `cron/scheduler.py` (call sites)
- `gateway/run.py` (call sites)
- `gateway/platforms/webhook.py` (call sites)

**Python — suppression scan**
- `agent/**`, `hermes_cli/**`, `gateway/**`, `tools/**`, `orchestrator/**`

**Android — security surface**
- `apps/android/app/src/main/AndroidManifest.xml`
- `apps/android/app/src/main/res/xml/backup_rules.xml`
- `apps/android/app/src/main/res/xml/data_extraction_rules.xml`
- `apps/android/app/src/main/java/com/aci/hermes/data/audit/SecretRedactor.kt`
- `apps/android/app/src/main/java/com/aci/hermes/data/audit/AuditRepository.kt`
- `apps/android/app/src/main/java/com/aci/hermes/data/memory/MemoryRedactor.kt`
- `apps/android/app/src/main/java/com/aci/hermes/data/social/PrivacyRedactor.kt`
- `apps/android/app/src/main/java/com/aci/hermes/data/emergency/EmergencyStopController.kt`
- `apps/android/app/src/main/java/com/aci/hermes/data/emergency/EmergencyStopRepository.kt`
- `apps/android/app/src/main/java/com/aci/hermes/data/emergency/EmergencyStopState.kt`
- `apps/android/app/src/main/java/com/aci/hermes/data/emergency/EmergencyStopAuditEvent.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/components/EmergencyStopButton.kt`

**CI / CodeQL**
- `.github/codeql/` (does not exist)
- `.github/workflows/` (no codeql / security workflow committed)

**Tests run**
- `tests/test_jarvis_prime_*.py`
- `tests/test_orchestrator_*.py`
- `tests/agent/test_redact.py`

---

## Risks and notes for the next audit

- **CodeQL backlog on PR #109 files** is out of scope per the PR description
  and is not regressed by this candidate. Worth re-running CodeQL on `main`
  after merge to confirm no new findings.
- **`HERMES_YOLO_MODE`** bypasses *dangerous-command approval* (shell
  prompts), not owner gates. The naming is potentially confusing for new
  reviewers; the next audit should keep a note in case anyone tries to
  thread YOLO into the owner-gate path.
- **`auto_approve_exec` / `auto_approve_apply_patch`** on
  `agent/transports/codex_app_server_session.py` apply only to the Codex
  transport's internal sandbox executor. If a future change wires either of
  those toggles to non-Codex execution paths, the next audit should verify
  they cannot satisfy an `OWNER_GATED_ACTIONS` entry.
- **Pre-existing `# noqa: S603` and `# nosec` comments** are documented as
  justified in their respective files (argv built internally; detection
  best-effort). No new such suppressions added by PR #131.

## Conclusion

The launch candidate at `d0caf92` **PASSES** the launch security and
owner-gate audit. No fixes are required to the allowed file list. The
candidate is safe to remain DRAFT pending owner authorization for the
launch action category itself (which, per § 1, requires the exact phrase
"Yes, with authorization.").
