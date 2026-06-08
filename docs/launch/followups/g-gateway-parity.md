# g-gateway-parity: capability/health describe surface on the SMS adapter (FU-19)

- **Status:** in-review
- **Risk class:** additive
- **Branch:** `claude/g-gateway-parity` · **Base:** `main` @ `ba2c12dfd0ff005f8f0a36f5adbaac96edff681d`
- **PR:** (draft — see PR link in ledger)
- **Owner-gate required to merge?** no — strictly additive, opt-in describe
  surface; no default runtime behavior changes. May auto-merge on green CI.

## Intent (one paragraph)

There is no per-adapter capability/health describe surface in the messaging
gateway today — `gateway/platforms/base.py` exposes only the
`supports_draft_streaming()` hook, and individual adapters cannot be
introspected for what they actually support or whether they are ready. This
grain introduces the parity pattern on the SMS (Twilio) adapter, the weakest
adapter (no media override, no thread concept, no draft streaming). Before:
the SMS adapter had no way to answer "what do you support?" / "are you
ready?" without attempting a real connection. After: `SmsAdapter.capabilities()`
returns a stable, honest dict (`platform`, `supports_media`,
`supports_threads`, `supports_draft_streaming`) and `SmsAdapter.health()`
returns a stable readiness dict (`platform`, `healthy`, `detail`, `running`)
that is safe to call before `connect()`, without live credentials, and
without any network I/O — degrading to an honest `healthy: False` plus a
human-readable reason rather than raising. Send/receive behavior is byte-for-byte
unchanged; this is purely an additive describe surface.

## Owned files (the ONLY files this task may write)

- `gateway/platforms/sms.py` (modified — additive methods only)
- `tests/gateway/platforms/test_sms_capabilities.py` (new)
- `tests/gateway/platforms/__init__.py` (new — package marker so the new
  test subpackage is collectable under pytest's default `prepend` import
  mode; `tests/gateway/__init__.py` already exists)
- `docs/launch/followups/g-gateway-parity.md` (this snapshot)

> Disjoint from every other in-flight task. Touches exactly one adapter; no
> other `gateway/platforms/*` or `gateway/cockpit/*` files are modified.

## Plan (bounded steps)

1. Read `gateway/platforms/sms.py` and the `supports_draft_streaming`
   convention in `gateway/platforms/base.py`.
2. Add `capabilities()` returning a stable dict, with values derived honestly
   from what the adapter implements (no media override ⇒ `supports_media:
   False`; flat DM sessions ⇒ `supports_threads: False`; mirrors the base
   `supports_draft_streaming()` hook ⇒ `False`).
3. Add `health()` that inspects only local config (from-number, webhook URL,
   the live `SMS_INSECURE_NO_SIGNATURE` flag — mirroring `connect()`), never
   makes a Twilio call, never starts the webhook server, and degrades to an
   honest `healthy: False` + reason. A private `_platform_id()` helper
   resolves the platform string defensively so the surface never raises even
   on a partially-constructed adapter.
4. Add `tests/gateway/platforms/test_sms_capabilities.py` asserting dict
   shape/keys/types, honest degradation without credentials/webhook/network,
   never-raises on a bare instance, and no regression to `format_message` /
   `truncate_message` / `MAX_MESSAGE_LENGTH`.

## Validation

- `uv run ruff check gateway/platforms/sms.py tests/gateway/platforms/test_sms_capabilities.py`
  → **All checks passed!**
- `uv run ty check gateway/platforms/sms.py tests/gateway/platforms/test_sms_capabilities.py`
  → **no new diagnostics vs base.** `sms.py` has 7 pre-existing
  `aiohttp` unresolved-import/reference diagnostics on `main` @ base
  (identical count before and after this change — verified against
  `origin/main:gateway/platforms/sms.py`); the test file adds only the
  exempt `pytest` + `aiohttp` third-party unresolved-import false positives.
  The added `capabilities()` / `health()` / `_platform_id()` code references
  only stdlib `os` and `self`, introducing zero new diagnostics.
- `python -m pytest tests/gateway/platforms/test_sms_capabilities.py tests/gateway/test_sms.py -o addopts="" -q`
  → **54 passed** (15 new + 39 existing SMS tests; 6 pre-existing aiohttp
  deprecation warnings, unrelated).

## Residual / follow-on

- The describe surface is realized on the SMS adapter only, as the parity
  exemplar. Rolling the same `capabilities()` / `health()` contract out to the
  other `gateway/platforms/*` adapters (and surfacing it via the cockpit /
  `gateway/platforms/base.py` as a default contract) is intentionally out of
  scope for this grain — it would touch files outside the owned set.
- `health()` reads `SMS_INSECURE_NO_SIGNATURE` live from the environment
  (matching `connect()`'s own behavior) while `from_number` / `webhook_url`
  come from instance state captured at `__init__`. This asymmetry mirrors the
  adapter's existing behavior exactly and is deliberate.
- No change to send/receive, signature validation, or the webhook handler.
