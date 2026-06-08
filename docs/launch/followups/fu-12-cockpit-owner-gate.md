# FU-12 · Cockpit autonomy owner-gate (C2 + C3 merged)

**Lane:** C (safety) · **Risk:** behavior-change (new owner gate) · **Priority:** P0
**Branch:** `claude/fu-12-cockpit-owner-gate` · **Base:** `origin/main` @ `b74f9889`

## Intent

`POST /v1/cockpit/autonomy` (`handlers.autonomy_set`) was the lone state-mutating
cockpit route with **no owner-authorization phrase** — a bearer-token holder could
raise autonomy to `owner_high_autonomy_coding` (auto-approving code-worker exec,
dependency install, local server, branch/commit, secret access inside a
caller-supplied `workspace_path`). Every sibling gate (approvals, publish,
paid-model flip, pair-confirm, execute) requires the exact phrase. This closes the
asymmetry: **escalation is owner-gated; de-escalation/revoke stay open.**

## Owned files (writable)

- `gateway/cockpit/handlers.py` — `autonomy_set` gated; new
  `_PRIVILEGED_AUTONOMY_LEVELS` + `_autonomy_raises_locked()`.
- `tests/gateway/test_cockpit_autonomy.py` — existing raises now send the phrase;
  new tests: phrase-required-on-raise (403 without / wrong, 200 with), ungated
  lowering, env kill-switch.

No other Wave-1 task writes `handlers.py` (FU-14 is client-only). Disjoint.

## Behavior

- Raising to a **privileged** level (`autonomous` / `yolo` /
  `owner_high_autonomy_coding`) requires `authorization == "Yes, with
  authorization."` → else `403 {authorization_required: true}`.
- Lowering to `read_only`/`assisted` and `{"revoke": true}` are **never** gated.
- `HERMES_COCKPIT_AUTONOMY_LOCKED` (truthy) hard-disables raises even with the
  phrase (rollback / shared-deployment lockdown). Lowering still works.
- Audit record + capability response unchanged.

## Rollback

Revert the commit, or set `HERMES_COCKPIT_AUTONOMY_LOCKED=1` at runtime (no code
change) to disable raises entirely.

## Validation (run, green)

- `uv run ruff check gateway/cockpit/handlers.py tests/gateway/test_cockpit_autonomy.py` → clean
- `uv run ty check …` → clean (no new diagnostics)
- `python -m pytest tests/gateway/test_cockpit_autonomy.py tests/gateway/test_cockpit_api.py -o addopts=""` → **65 passed**

## Residual risk

The other cockpit gates still compare the **static** phrase (replayable over an
authed connection) rather than the `owner_auth` nonce challenge. Migrating the
strongest gates (paid spend, execute, this raise) to the nonce is the natural
[C2] follow-up; tracked separately so this P0 ships now.

## Follow-up note for FU-14 (cockpit UI)

The UI's autonomy control must now send `authorization` on a raise and handle a
`403 {authorization_required: true}` by prompting for the phrase.
