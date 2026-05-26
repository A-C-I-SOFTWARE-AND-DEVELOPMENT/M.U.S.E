# Canonical Repo Declaration for JARVIS Prime

This document establishes which repository owns the canonical runtime
for JARVIS Prime and how parallel repository work must be coordinated.

## Canonical source of truth

`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` is the canonical source of
truth for the JARVIS Prime runtime.

All JARVIS Prime runtime files — the `hermes_cli/jarvis_prime/` package
(`runtime.py`, `router.py`, `modes.py`, `gates.py`, `owner_auth.py`,
`memory.py`, `awareness.py`, `reasoning.py`, `research.py`,
`social_research.py`, `epistemics.py`, `self_update.py`, `onboarding.py`,
`persona.py`, `tick.py`, `communication_style.py`, `work_packet.py`),
the operating-system spec at `docs/jarvis-prime-operating-system.md`,
the verification-gate spec at `docs/jarvis-verification-gates.md`, the
routing doc at `docs/aos-jarvis-agent-routing.md`, the wave plan at
`docs/jarvis-prime-wave-plan.md`, the activation skills under
`skills/jarvis-prime/` and `skills/jarvis-code-operator/`, and the
test suite at `tests/test_jarvis_prime_*.py` — are owned here.

## Legacy mirror

`echerd27-design/hermes-agent` is a legacy / spec mirror. It may carry
older drafts or design-time notes that have not yet been promoted into
the canonical repo. Treat it as read-only context unless a deliberate
sync has been planned and announced. Do not assume that a file in the
mirror is current, and do not edit both repositories in the same change
without first declaring which one is canonical for that change.

## Branching policy

* All future JARVIS Prime runtime work branches from
  `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` `main`.
* Do not edit `main` directly.
* Do not edit multiple Hermes/JARVIS repositories in parallel without
  declaring which repo is canonical for that change. If a change must
  land in both, land it here first, then port.
* When branching, cut from the current `origin/main` HEAD — never from
  an existing feature branch unless the dependency is intentional and
  declared. Stale-base branches (forked from a divergent history) will
  conflict with the shipped runtime files and must be rebased before
  merge.

## Worker assignments

* Claude Code is the primary builder for JARVIS Prime runtime changes.
* Codex is the reviewer, bounded fix worker, refactorer, and
  second-pass engineer.
* Claude Code and Codex must not edit the same branch at the same
  time. Coordinate handoff explicitly.

## Owner-gated actions

The following actions require explicit owner authorization with the
exact phrase `Yes, with authorization.` before they are executed.
This list is kept in sync with the canonical `OWNER_GATED_ACTIONS`
frozenset in `hermes_cli/jarvis_prime/owner_auth.py`; the code is the
authority and this doc must follow.

* `spend_money`
* `post_publicly`
* `create_third_party_account`
* `oauth_change`
* `credential_change`
* `production_deploy`
* `dns_change`
* `main_branch_merge`
* `force_push`
* `package_publish`
* `app_store_submission`
* `delete_recovered_sources`
* `modify_secrets`
* `change_default_active_agents`
* `registry_mutation`
* `regulated_claim` (legal, compliance, security, health, financial)

The phrase is enforced literally by
`hermes_cli/jarvis_prime/owner_auth.py:OwnerAuth.authorize`. Minor
variations ("yes with authorization", "yes - with authorization") do
not authorize. Authorization stands only for the scope it was granted
for — it is not a blanket approval for future actions of the same kind.

## Verification before "done"

No work is "done" until verification evidence has been recorded. For
runtime changes that means at minimum:

* Tests run with results captured (the shipped runtime ships 159
  hermetic tests; new work should add to that suite at
  `tests/test_jarvis_prime_*.py`, not in a parallel `tests/jarvis_prime/`
  layout).
* Diff reviewed.
* Rollback plan documented in the PR or in a `WorkPacket`.

If verification cannot be produced, the change is not done — it is
"awaiting verification" and must be labeled as such.

## WorkPacket schema

The canonical descriptor for a JARVIS unit of work is
:class:`hermes_cli.jarvis_prime.work_packet.WorkPacket`. It carries
mission, repo_root, branch, risk_class (RC0..RC4), allowed/protected
files, non_goals, acceptance_criteria, files_changed, tests_run,
tests_failed, verification_summary, rollback_plan, owner_gated_actions,
owner_authorization_phrase, citations, confidence, and created_at.
WorkPacket defaults its `owner_authorization_phrase` to the canonical
constant from `owner_auth.py` so the data layer and the gate layer
cannot disagree on the exact string.
