# FU-13 · `--allow-external` host/CIDR allowlist + static-suffix allowlist

- **Status:** in-review
- **Risk class:** additive / behavior-guard (hardening) — owner-gated to merge
- **Lane:** C (safety) · **Priority:** P0
- **Branch:** `claude/fu-13-allow-external` · **Base:** `main` @ `e1ac6eed`
- **PR:** (draft — see ledger)
- **Owner-gate required to merge?** yes — tightens a security-relevant default
  (a non-loopback bind that used to be allowed by `allow_external=True` alone
  now also requires an explicit host/CIDR). Awaiting `Yes, with authorization.`

## Intent

The cockpit server's external-bind story was binary: loopback by default, and
`allow_external=True` (`--allow-external`) flipped it fully open — any
non-loopback host (including the wildcard `0.0.0.0` / `::`) was accepted with
only a warning. FU-13 adds defense-in-depth on top of the existing per-request
owner-phrase gate and the loopback-only execute refusal:

1. **Bind allowlist (fail-closed).** When binding a **non-loopback** host,
   `allow_external=True` is no longer sufficient on its own — the host must also
   appear in a new `allow_external_hosts` allowlist (explicit host strings
   and/or CIDR ranges). A non-loopback host not in the allowlist **raises
   `ValueError`** (by design — that's the security behavior). The default
   loopback path never consults the allowlist and is byte-for-byte unchanged.
2. **Static-suffix allowlist.** `_serve_static` now only serves files whose
   suffix is in `_STATIC_TYPES`. A concrete file with a disallowed suffix
   (e.g. a stray `.py`) **404s** instead of leaking as
   `application/octet-stream`. Routes (no file suffix) and missing allowlisted
   files still fall back to the SPA `index.html`, so client-side routing is
   intact.

Neither change weakens the loopback-only execute refusal
(`allow_remote_execute`) or the owner-phrase gate — both are preserved exactly.

## Owned files (the ONLY files this task may write)

- `gateway/cockpit/server.py` — new `_host_in_allowlist()` helper; `serve()`
  gains an `allow_external_hosts` keyword and a fail-closed non-loopback bind
  guard; `_serve_static` gains the suffix-allowlist check.
- `tests/gateway/test_cockpit_loopback_guard.py` — extended (allowlist matching,
  bind-guard fail-closed/positive, execute-still-refused, static suffix
  allow/404/SPA-route).
- `docs/launch/followups/fu-13-allow-external.md` — this snapshot.

Disjoint from every other in-flight task: FU-12 owned `handlers.py`, FU-14 was
client-only, FU-11 the single-job/orchestrator path. No shared writable file.

## What changed (behavior)

- `serve(host, ..., allow_external=False, allow_external_hosts=None, ...)`:
  - loopback host → bind, no allowlist consulted (unchanged).
  - non-loopback + `allow_external=False` → raise (original message, unchanged).
  - non-loopback + `allow_external=True` + host **not** in `allow_external_hosts`
    → raise `ValueError` mentioning `allow_external_hosts` (NEW, fail-closed).
  - non-loopback + `allow_external=True` + host **in** `allow_external_hosts`
    (exact host or a containing CIDR) → bind + warn (as before).
- `_host_in_allowlist(host, allowlist)`: literal-string match plus IP/CIDR
  membership (a bare host matches its own `/32`/`/128`; a CIDR matches every
  address it contains); v4↔v6 never cross-match; blank/garbage entries are
  skipped; **never raises**.
- `_serve_static`: existing-file-with-disallowed-suffix → `return False` →
  404; suffix-less route or missing allowlisted file → SPA index fallback.

The CLI (`hermes cockpit serve`) keeps `--host` defaulting to `127.0.0.1`, so
`--allow-external` on its own still binds loopback and is unaffected. Only an
operator explicitly passing a non-loopback `--host` is now additionally required
to name the host/CIDR (wiring a `--allow-external-host` CLI flag through
`hermes_cli/main.py` is the natural follow-on — see Residual; `main.py` is out
of this task's owned set).

## Validation (run, green)

- `uv run ruff check gateway/cockpit/server.py tests/gateway/test_cockpit_loopback_guard.py`
  → **All checks passed!**
- `uv run ty check gateway/cockpit/server.py tests/gateway/test_cockpit_loopback_guard.py`
  → 1 diagnostic = the pre-existing/exempt `unresolved-import: pytest` FP on the
  test file (present identically on unmodified `test_cockpit_api.py`).
  `server.py` alone → **All checks passed!** (no new diagnostics).
- `python -m pytest tests/gateway/test_cockpit_loopback_guard.py tests/gateway/test_cockpit_api.py -o addopts="" -q`
  → **74 passed**.
- Regression spot-check (not required, related to the static change):
  `pytest tests/gateway/test_cockpit_static_ui.py tests/gateway/test_cockpit_job_files.py tests/gateway/test_cockpit_publish.py`
  → **49 passed**; `tests/test_release_readiness_doctor.py` → **9 passed**
  (the `serve` signature still satisfies the loopback-default gate).

## Rollback

Revert the single commit. The change is additive at the API surface
(`allow_external_hosts` defaults to `None`); the only externally-visible behavior
delta is that a non-loopback bind now requires the allowlist, which is the
intended hardening.

## Residual / follow-on

- No CLI flag yet exposes `allow_external_hosts` (`hermes_cli/main.py` is outside
  this task's owned files). Follow-on: add `--allow-external-host HOST/CIDR`
  (repeatable) to `cockpit serve` and thread it into `serve(...)`.
- The bind allowlist hardens *which host* may be bound; it does not add
  network-layer ACLs (firewalling remains the operator's responsibility). The
  bearer token + owner phrase + loopback-only execute refusal remain the
  request-time guards.
