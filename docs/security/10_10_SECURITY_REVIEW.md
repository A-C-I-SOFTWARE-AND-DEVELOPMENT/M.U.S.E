# Hermes 10/10 — Security Review

> **Owner:** Sprint 14 (Security hardening). **Reviewed against:** current `main`.
> **Method:** static review (read + grep) of the safety-critical surfaces, with
> file evidence. Pairs with the runnable gate `hermes doctor --10-10` (which
> re-checks the load-bearing controls) and
> [`PROTECTED_PATHS_10_10.md`](../launch/PROTECTED_PATHS_10_10.md).

## Verdict

**Posture: strong (≈9/10).** Every hard safety/correctness gate passes. Secret
redaction is applied at every egress, owner gates enforce an exact phrase +
nonce challenge, the remote bridge is signed/allowlisted, and the supply chain
is exact-pinned. One real gap (publisher repo allowlist) and two
operational notes are the only findings; none is a release blocker for a
loopback/dry-run alpha.

## Control review

| Control | Status | Evidence |
|---|---|---|
| **Secret redaction** | PASS | Canonical `redact()` / `scan_text()` in `hermes_cli/secrets_policy.py`; cockpit ledger/audit through `gateway/cockpit/redaction.py` (`redact_text`/`redact_value`, recursive); `DecisionVerdict.to_redacted_dict()` redacts every string; PR bodies via `hermes_cli/pr_body.py`; logs via `agent/redact.py` (`RedactingFormatter`); Android mirror in `apps/android/.../SecretRedactor.kt`. |
| **Owner gates** | PASS | `hermes_cli/jarvis_prime/owner_auth.py`: exact `AUTHORIZATION_PHRASE`, nonce-bound challenge/response (6-digit, TTL, `secrets.randbelow`), `OWNER_GATED_ACTIONS` frozenset; strict guardrail gates + tamper-evident evidence ledger (`gates.py`, `guardrail_evidence.py`). |
| **GitHub live publish** | PARTIAL | Dry-run is the default (`github_publisher.py`, `approve=False`); pre-publish secret scan (filename + path + content) blocks push; no `--force`; verdict computed at the publish boundary. **Gap:** no explicit repo allowlist in the publisher — see Findings. |
| **Remote bridge** | PASS | Command allowlist (default `("claude",)`, expanding needs code review); **signed envelope** HMAC-SHA256 + constant-time verify + expiry + single-use nonce with durable `SeenNonceStore` (`bridge_envelope.py`, wired in `remote_bridge.py`); per-device allowlist; secret-scrubbed JSONL audit. No arbitrary remote shell. |
| **Cockpit auth / pairing** | PASS | Bearer token stored owner-only `0600`, compared with `hmac.compare_digest`; **per-device pairing** with hashed-at-rest tokens + immediate revocation (`auth.py` → `device_pairing`); pairing rate-limit + lockout + code TTL (`gateway/pairing.py`); **loopback bind by default** (external requires explicit opt-in + warning); no unauthenticated non-health endpoints. |
| **Android** | PASS | Minimal, justified permissions (INTERNET loopback, foreground-service, optional mic/camera — no location/contacts); token in `EncryptedSharedPreferences` (AES-256-GCM, Keystore master key); audit material redacted before UI/clipboard. |
| **Supply chain** | PASS | Every base dependency exact-pinned `==` (rationale: post-Shai-Hulud, `pyproject.toml`); `uv.lock` committed; OSV scanner + supply-chain-audit CI on PRs. |
| **Test isolation** | PASS | `tests/conftest.py` unsets all credential-shaped env vars, isolates `HERMES_HOME` to a tempdir, and pins a deterministic runtime — a test cannot read or leak real credentials. |

## Findings

1. **GitHub publisher repo allowlist (LOW–MEDIUM, fixable).** `github_publisher.py`
   parses the repo slug from the remote but does not validate it against an
   explicit allowlist. Live publish is currently constrained only by
   **owner-gating** the `github.publish_pr` action (effective, but a
   misconfiguration pointing at an unexpected repo is not blocked until the owner
   reviews). *Recommendation:* add an explicit repo allowlist checked before
   `approve=True` allows a push. Tracked in the release checklist punch list and
   surfaced by `hermes doctor --10-10`.

2. **Cockpit token on shared filesystems (MEDIUM, operational).** The cockpit
   bearer token is stored `0600` under `~/.hermes/cockpit/`. Safe on a
   single-user host; on a multi-user box or networked `HERMES_HOME`, another
   local user could read it. *Mitigation in place:* `0600` + loopback-only bind.
   *Recommendation:* document that the cockpit must run single-user/local.

3. **Redaction opt-out (LOW).** Redaction can be disabled via
   `HERMES_REDACT_SECRETS=false` (logged as a downgrade warning). Explicit, not
   implicit. *Recommendation:* keep the warning; consider refusing the opt-out in
   release builds.

## Release security checklist (Sprint 14)

- [x] Secrets redacted from logs, events, PR bodies, cockpit, and diagnostics
- [x] Remote bridge cannot execute arbitrary shell (signed envelope + allowlist)
- [x] GitHub live publish is dry-run by default; secret scan before publish
- [ ] GitHub live publish repo allowlist enforced *(Finding 1)*
- [x] Owner phrase required for owner-gated actions; nonce challenge available
- [x] Pairing tokens hashed at rest; device revocation works
- [x] Cockpit loopback-only by default; no debug endpoints exposed externally
- [x] Android permissions reviewed; secure token storage
- [x] Dependency lock + exact pins; OSV / supply-chain scanning on PRs
- [x] Test isolation prevents credential leakage
- [ ] Document single-user/local requirement for cockpit token *(Finding 2)*

No unresolved **blocker** for a loopback/dry-run alpha. Findings 1–2 are
recommended before enabling live publish or a multi-user deployment.
