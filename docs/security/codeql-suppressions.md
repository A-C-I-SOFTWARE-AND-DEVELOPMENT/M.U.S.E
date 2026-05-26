# CodeQL Suppressions — Audit Trail

This document is the source of truth for every CodeQL query suppressed
in `.github/codeql/codeql-config.yml`. **No suppression may be added to
that file without a corresponding entry here**, signed off with a
date, a per-site audit, and the runtime mitigation that justifies it.

## Policy

A suppression is acceptable only when **all** of the following hold:

1. The query produces a non-trivial number of false positives across
   the repo for a structurally-similar pattern.
2. The runtime risk the query targets is mitigated by another
   mechanism (a sanitizer, a redactor, a code review rule, etc.).
3. Every individual alert that motivated the suppression has been
   audited and recorded here.

Suppressions are reviewed during each release-readiness pass. A
suppression that no longer corresponds to a CodeQL alert (because the
underlying code was deleted or refactored) should be removed from the
config and from this document.

## Active suppressions

### `py/clear-text-logging-sensitive-data`

- **Suppressed:** 2026-05-26 (PR #109)
- **Scope:** repo-wide for Python.
- **Runtime mitigation:** `agent.redact.safe_audit_identifier()` and
  `agent.redact.safe_log_summary()`, applied at every site CodeQL
  flagged. Both helpers rebuild their output via `re.sub` against a
  bounded character class, so credential bytes cannot survive the
  round-trip — they are replaced with `<redacted>`. Identifier-shaped
  values (env-var names, skill names, session ids, chat ids) pass
  through unchanged. The existing log-handler-level
  `agent.redact.RedactingFormatter` provides defense-in-depth at the
  formatter layer.
- **Why we can't fix at the source level:** CodeQL's
  `CleartextLoggingQuery` (`codeql/python-all` 7.1.1) declares no
  sanitizers in `CleartextLoggingCustomizations.qll`. The query's
  taint-tracking config recognizes only `ConstCompareBarrier` (per
  `semmle/python/dataflow/new/BarrierGuards.qll`) — comparing a value
  against a constant literal. User-defined validation functions, even
  ones built around `re.sub`, are not modelled as barriers, so any
  path from a sensitively-named source variable to a logger sink is
  flagged regardless of intermediate transformation.

#### Per-alert audit (PR #109 — 15 alerts)

Each row records the call site, the variable CodeQL tracked as a
sensitive source, what the call site *actually* emits to the log
after the redact helpers run, and the classification.

| # | Call site | Variable name | Actually logged | Classification |
|---|-----------|---------------|-----------------|----------------|
| 1 | `agent/agent_init.py:865` | `agent.ephemeral_system_prompt` | `<N chars>` (length only) | False positive — no bytes of the prompt appear in the output |
| 2 | `cron/scheduler.py:1078` | `job["name"]` / `job["id"]` | Whitelist-validated identifier or `<redacted>` | False positive — cron job identifier from config |
| 3 | `gateway/platforms/webhook.py:698` | `content` | `<N chars>` (length only) | False positive — log-only delivery; length only |
| 4 | `gateway/run.py:7415` | `bundle_key`, `missing` | Whitelist-validated slash-command identifier; missing skill names | False positive — bundle and skill identifiers |
| 5 | `gateway/run.py:7845` | `source.chat_id`, `source.user_id` | Whitelist-validated routing IDs | False positive — Telegram numeric routing IDs |
| 6 | `gateway/run.py:8495` | `_platform_name`, `source.chat_id` | Whitelist-validated platform name + routing ID | False positive — routing identifiers |
| 7 | `gateway/run.py:8649` | `session_entry.session_id` | Whitelist-validated session id | False positive — log-correlation ID |
| 8 | `gateway/run.py:8656` | `session_entry.session_id` | Whitelist-validated session id | False positive — log-correlation ID |
| 9 | `gateway/run.py:8667` | `session_entry.session_id` | Whitelist-validated session id | False positive — log-correlation ID |
| 10 | `hermes_cli/config.py:308` | `action` (built from env-var name) | Printable-ASCII-stripped user-facing error string | False positive — managed-mode UX error |
| 11 | `hermes_cli/config.py:4772` | `key` (env-var name), `bad_chars` | Whitelist-validated env-var NAME + Unicode positions + code points. **The non-ASCII character itself is never printed** (changed from prior behaviour). | False positive — non-ASCII credential diagnostic |
| 12 | `tools/env_passthrough.py:97` | `name` (env-var name) | Whitelist-validated env-var NAME | False positive — audit log of blocked env var |
| 13 | `tools/env_passthrough.py:101` | `name` (env-var name) | Whitelist-validated env-var NAME | False positive — audit log of registered env var |
| 14 | `tools/skill_usage.py:404` | `skill_name` | Whitelist-validated skill identifier | False positive — debug log of usage update |
| 15 | `tools/skills_tool.py:342` | `entry["name"]` (secret storage key) | Whitelist-validated storage-key name | False positive — secret-capture failure logs the *name* of the storage slot, not the secret value |

A 16th alert site — `tools/skills_tool.py:1466-1506` (the dev-only
`__main__` test scaffold with 7 print calls) — was removed entirely
in commit `bbfc6ed` because it was dev scratch code, not a production
path; the real tests live in `tests/test_plugin_skills.py`.

#### Verification

Manual verification that no credential value reaches a logger from the
audited sites:

- `tests/agent/test_redact.py::TestSafeAuditIdentifier` covers the
  identifier sanitizer behaviour (8 cases including identifiers,
  secrets, special chars, non-strings, overlong values, leading
  digits).
- `tests/agent/test_redact.py::TestSafeLogSummary` covers the
  length-only summary behaviour (6 cases including the secret-length
  preservation, special-char stripping in the preview, and stringify
  for non-string inputs).
- The 13 sites that wrap a single variable also rely on existing
  `tests/agent/test_redact.py` coverage of `RedactingFormatter`, which
  removes any credential value that *does* reach a log handler from a
  path the static helpers can't see (defense in depth).

## Removing a suppression

To remove a suppression:

1. Delete the matching `query-filters` entry from
   `.github/codeql/codeql-config.yml`.
2. Move the audit row from "Active suppressions" to a new "Removed
   suppressions" section with the removal date and the PR that
   removed it.
3. Confirm the next CodeQL run completes without new findings of that
   query — if it does fire, fix the underlying code rather than
   re-suppressing.
