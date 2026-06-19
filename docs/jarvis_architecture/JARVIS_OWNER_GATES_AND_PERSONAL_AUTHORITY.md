# muse — Owner Gates & Personal Authority

muse is **loyal to the owner's long-term mission, not blindly obedient
to the moment.** Personal-use authorization may reduce repeated permission
friction, but **irreversible or external actions still require a final
confirmation**. Owner gates are never removed.

## The authorization phrase
Owner-gated actions are deferred until the owner replies **exactly**:

```
Yes, with authorization.
```

Approximate phrases ("yes", "go ahead", "approved") do **not** authorize.
Enforced in `hermes_cli/jarvis_prime/owner_auth.py` and the
`owner_approval` verification gate (`gates.py`).

## Owner-gated action categories
Canonical set (`OWNER_GATED_ACTIONS` in `owner_auth.py`):
`spend_money`, `post_publicly`, `create_third_party_account`,
`oauth_change`, `credential_change`, `production_deploy`, `dns_change`,
`force_push`, `package_publish`, `app_store_submission`,
`delete_recovered_sources`, `modify_secrets`,
`change_default_active_agents`, `registry_mutation`, `regulated_claim`.

The natural-language coder detects these categories from plain-English
requests via `OwnerGate` and maps them to the canonical vocabulary in
`to_gate_packet()` so they flow through the verification gates.

## Personal action authority (Android)
A standing owner-authorized profile **may** exist to reduce friction, but:

- Android **system permissions remain technical gates** that muse cannot
  bypass.
- External post/send/purchase/security/destructive actions **pause before
  the final irreversible step**.
- The action broker returns one of: `direct_execute`,
  `blocked_missing_capability`, `requires_final_confirmation`,
  `blocked_by_policy`.

## Emergency stop
`python -m hermes_cli.jarvis_prime stop` clears pending owner gates and
disables proactive ticks. The Android avatar surfaces a visible emergency
stop. Emergency stop overrides all presence/automation state.

## What muse will refuse
Requests to bypass owner gates, exfiltrate credentials/secrets, or perform
harmful/destructive production actions are classified `RC4` / blocked by
`route_request()` and produce a **plan/review** packet, never an execution
packet. The packet validator (`validate_work_packet`) flags blocked packets
as errors.

## Rollback & reversibility
Every write-intent work packet carries a rollback plan: work happens on an
isolated feature branch (never `main`), and reverting the branch / dropping
the PR fully undoes it. No schema or irreversible migration without a
separate owner gate.
