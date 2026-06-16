# Activating Full Autonomy — the Autonomy Charter

This is the **designed, safe way to make MUSE act on its own**: grant it a broad,
scoped, revocable **Autonomy Charter**. It is *not* done by removing gates — it is
done by the owner explicitly chartering bounded autonomy, with a permanent hard
wall keeping the safety-critical core owner-gated forever.

> **Why a charter, not "no gates":** the charter gives MUSE wide latitude to act
> while keeping the one protection that makes that autonomy trustworthy — MUSE can
> never auto-edit its *own* owner-auth, gates, verifier, model registry, routing,
> or Constitution. That hard wall (Constitution **C34**) is what makes every
> autonomous action reversible and auditable. It stays, by design.

## What "autonomous" means here

With an active charter, `research_fabric/controller.py:evaluate_and_apply` stops
falling back to "propose only" and **auto-applies** proposals that are within the
charter's scope, pass all eight gates and the non-regression ratchet, and survive
a post-apply **canary** (which auto-rolls-back on any regression). Without a
charter it logs *"no active autonomy charter — auto-apply requires one (C33)"* and
defers — which is exactly the "AXIOM shows but MUSE isn't acting" state.

## Grant a broad charter (one owner action)

Granting the charter is the owner-gated action `grant_autonomy_charter`
(`hermes_cli/jarvis_prime/owner_auth.py`). Per Constitution **C11** it needs a
**nonce-bound** challenge — a one-time code — not just the static phrase, so a
replayed approval can never mint autonomy:

```text
# 1) Request the challenge (prints a one-time code):
$ muse guardrails authorize grant_autonomy_charter --subject "broad autonomy"
required_phrase: Yes, with authorization. Code: 728193

# 2) Respond with the exact phrase INCLUDING the code:
$ muse guardrails authorize-response <challenge-id> "Yes, with authorization. Code: 728193"
authorized: true   # a content-addressed grant artifact lands in the ledger
```

That grant is what `charter.CharterBook.grant(...)` consumes to mint the charter.
A **broad** charter (maximal autonomy, safety core intact) looks like:

| Charter field | Broad value | Meaning |
|---|---|---|
| `allowed_kinds` | every **non-hard-walled** `ProposalKind` (e.g. `SKILL_UPDATE`, `NEW_SKILL`, …) | what MUSE may auto-apply |
| `risk_band_ceiling` | `RC3` | highest risk it may auto-apply (RC4 is **never** permitted) |
| `per_window_budget` | large (e.g. 50) | max auto-applies per window |
| `window_seconds` | e.g. `86400` | the budget window (1 day) |
| `ttl_seconds` | e.g. `604800` | auto-expiry (1 week) — re-grant to extend |

`grant()` **rejects** an `RC4` ceiling and **rejects** any hard-walled kind up
front, so a "broad" charter is still bounded by the wall.

## What the charter can never cover (the hard wall, C34)

`charter.HARD_WALL_KINDS` + `PROTECTED_PATH_MARKERS` are owner-gated **forever,
regardless of any charter**:

- proposal kinds: `SELF_RUNTIME_UPDATE`, `GATE_UPDATE`, `MODEL_REGISTRY_UPDATE`,
  `ROUTING_RULE_UPDATE`, `AGENT_UPDATE`, `NEW_AGENT`.
- protected paths: `owner_auth.py`, `gates.py`, `constitution.py`,
  `capability_wall.py`, `guardrail_evidence.py`, `self_update.py`, and the
  research-fabric `validators.py` / `charter.py` / `controller.py` / `monitor.py`
  / `verifier`, plus `docs/jarvis-constitution.md` and the model
  catalog/routing policy.

So MUSE can autonomously build skills, run jobs, pick models, and ship bounded
work — but it can never autonomously weaken its own oversight.

## Revoke / inspect at any time

- **Revoke:** `CharterBook.revoke(charter_id)` (or let the `ttl` expire) — the
  controller immediately reverts to propose-only.
- **Inspect:** active charters and every auto-apply land in the decision ledger;
  the daily owner brief (`monitors.py` + `owner_brief.py`) surfaces what autonomy
  did.

## Related

- [MUSE_COMPONENT_REGISTRY.md](MUSE_COMPONENT_REGISTRY.md) — `research_fabric`,
  `owner_authorization`, `emergency_stop_monitors`.
- [`../jarvis-verification-gates.md`](../jarvis-verification-gates.md) — the gates
  every auto-applied change still passes, and the challenge-bound grant flow.
- [`../jarvis-constitution.md`](../jarvis-constitution.md) — C9/C10/C11 (owner
  gates + challenge) and C33/C34 (the bounded-autonomy exception + the hard wall).
- [`../integrations/sia-self-improvement.md`](../integrations/sia-self-improvement.md)
  — the self-improvement worker that the charter governs.
