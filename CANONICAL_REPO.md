# Canonical Repo Declaration — JARVIS Prime

This document declares the canonical source of truth for the JARVIS
Prime runtime and the rules that govern parallel work across forks.

## Canonical repo

**`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` is the canonical source
of truth for the JARVIS Prime runtime, tests, and shipping branches.**

All future JARVIS runtime work must branch from
`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`'s `main`.

## Legacy / spec mirror

`echerd27-design/hermes-agent` is treated as a **legacy and spec mirror**.
It holds historical context, early JARVIS Prime operating-layer
documents, and spec material that was authored before the ACI fork.

Do not edit it for runtime changes unless an explicit sync has been
declared. If a useful change exists only in the echerd27 fork, port it
into ACI as a normal PR — do not work in both repos in parallel.

## Repo-parallelism rule

**No one should edit multiple Hermes/JARVIS repos in parallel without
first declaring which repo is canonical for that change.** Parallel
edits in two forks produce stale runtime, hidden conflicts, and
duplicate JARVIS systems — all of which violate the "do not create
duplicate JARVIS systems" rule.

When in doubt: edit ACI. Mirror to echerd27 only if explicitly synced.

## Worker assignment

| Role | Tool | Notes |
| --- | --- | --- |
| Primary builder | Claude Code | Implements features, writes tests, ships PRs. |
| Reviewer / bounded fix / refactorer | Codex | Independent review, narrow fixes, second-pass engineering. |

**Claude Code and Codex must not edit the same branch at the same
time.** Hand off explicitly (Claude finishes → pushes → Codex reviews
on the next branch, or vice versa). See
`docs/claude-codex-handoff-workflow.md`.

## Owner-gated actions

The following actions require explicit owner authorization and the
exact phrase `Yes, with authorization.` before they may be executed:

- Merging any branch into `main`.
- Production deploys.
- Package publishing (PyPI, npm, app stores, etc.).
- App-store submissions.
- DNS changes.
- Credential changes (OAuth, API keys, secrets).
- Posting publicly on Jeremiah's behalf.
- Spending money or creating third-party accounts.
- Force-push, destructive history rewrites, or any destructive
  operation against a shared branch.
- Legal, compliance, security, health, financial, or other regulated
  claims.

The canonical list lives in
`hermes_cli/jarvis_prime/owner_auth.py::OWNER_GATED_ACTIONS` and the
authorization phrase in `AUTHORIZATION_PHRASE`. If you change the set
or the phrase, update both this document and
`docs/jarvis-prime-operating-system.md`.

## Cross-references

- `docs/jarvis-prime-operating-system.md` — runtime spec.
- `docs/jarvis-prime-wave-plan.md` — wave-by-wave build plan.
- `docs/jarvis-verification-gates.md` — eight verification gates.
- `docs/claude-codex-handoff-workflow.md` — worker handoff protocol.
- `skills/jarvis-prime/SKILL.md` — activation skill.
- `hermes_cli/jarvis_prime/` — runtime implementation.
- `hermes_cli/jarvis_prime/work_packet.py` — canonical WorkPacket model.
