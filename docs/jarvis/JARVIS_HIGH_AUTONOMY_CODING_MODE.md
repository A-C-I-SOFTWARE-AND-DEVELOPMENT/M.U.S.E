# muse high-autonomy coding mode

High-autonomy mode lets muse do more without asking each time — but
"more" is **scoped, logged, and revocable**, and the owner gates that
protect irreversible actions never lift. This guide explains the autonomy
dial, what each level actually permits, and how to pull power back
instantly.

> Pairs with [coding from the phone](../mobile/JARVIS_CODING_FROM_PHONE_GUIDE.md)
> and the [owner-gates spec](../jarvis_architecture/JARVIS_OWNER_GATES_AND_PERSONAL_AUTHORITY.md).

---

## The autonomy dial (scoped)

`apps/android/app/src/main/java/com/aci/hermes/data/jarvis/AutonomyMode.kt`
— an owner-controlled level, **never reset implicitly by the runtime**:

| Mode | What muse may do on its own |
|---|---|
| **Manual** | Nothing until you tap a step. |
| **Assisted** | Propose actions; each waits for owner approval. |
| **Trusted (low risk)** | Run **low-risk** steps automatically; destructive actions still require approval. |
| **Lockdown** | Nothing — no external actions, no handoffs, no automation. |

"High autonomy" means **Trusted (low risk)**. It is deliberately *not* an
"approve everything" switch: the scope is *low-risk steps only*. Anything
risky, external, or irreversible still stops at the gate.

## What never lifts (owner gates)

Regardless of autonomy level, owner-gated categories pause for the exact
phrase `Yes, with authorization.`
(`hermes_cli/jarvis_prime/owner_auth.py`, `gates.py`). The canonical set:
spend money, post publicly, create third-party accounts, OAuth changes,
credential changes, production deploys, DNS changes, force-push, package
publish, app-store submission, deleting recovered sources, modifying
secrets, changing default active agents, registry mutation, regulated
claims.

For coding specifically, the cockpit adds a **second** gate: agentic
execute lanes run only over a **loopback** cockpit (see
[coding from the phone](../mobile/JARVIS_CODING_FROM_PHONE_GUIDE.md#3-the-double-gate-on-execution)).

## Logged (everything is auditable)

- The **decision ledger** records every phase decision of every job
  (`docs/orchestration/decision-ledger.md`).
- The **emergency-stop audit log** records every stop transition and every
  blocked action.
- The **approvals history** records what was authorized, when, and the
  exact phrase.
- Backend logs run through the secret redactor, so the audit trail never
  leaks credentials.

You can inspect all of these from the phone (Audit / Approvals / Memory
screens) or on the backend (`muse orchestrator status`,
`~/.hermes/jobs/<job-id>/ledger.jsonl`).

## Revocable (instant brakes)

Any of these immediately narrows or removes autonomy:

- Set Autonomy to **Lockdown** — disables every outbound action.
- Engage **Emergency Stop** (soft pause → hard stop → lockdown); resume is
  audited and approval-gated (`EmergencyStopController`).
- On the backend: `python -m hermes_cli.jarvis_prime stop` clears pending
  owner gates and disables proactive ticks.
- **Unpair** (clear the cockpit token) or rotate it with
  `muse cockpit token --rotate`.

## Rollback (reversible by construction)

Write-intent work is reversible:

- Work happens on an **isolated feature branch — never `main`**.
- Every write packet carries a **rollback plan**; reverting the branch or
  dropping the PR fully undoes it.
- No schema or irreversible migration without a separate owner gate.
- Workers **propose** (draft PR); they never publish or merge on their
  own.

## Refusals

Requests to bypass owner gates, exfiltrate secrets, or perform
harmful/destructive production actions are classified and **blocked** —
they yield a plan/review packet, never an execution packet
(`route_request()`, `validate_work_packet`). High autonomy does not change
this; it only removes friction on the *low-risk* end.

## Recommended posture for personal use

- Day-to-day: **Assisted** or **Trusted (low risk)**.
- Sensitive period / shared device: **Lockdown** or unpair.
- Always keep approvals required and safety gates on (the install
  defaults). These are the safety floor; high autonomy raises the ceiling,
  it does not lower the floor.
