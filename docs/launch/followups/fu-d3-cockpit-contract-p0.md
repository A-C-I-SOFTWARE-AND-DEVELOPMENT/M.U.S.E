# FU-D3: Cockpit wire-contract freeze — EPIC-COCKPIT-SEAM Phase 0 (Wave D G3)

- **Status:** in-review
- **Risk class:** additive
- **Branch:** `claude/fu-d3-cockpit-contract-p0` · **Base:** `main` @ `e283d39ea`
- **PR:** draft (see ledger for number)
- **Owner-gate required to merge?** no — strictly additive (generator + committed
  artifacts + freeze test); zero edits to any runtime code path.

## Intent (one paragraph)

Freeze the cockpit wire surface before any seam work begins. A stdlib-only
generator walks the live route tables in `gateway/cockpit/server.py`
(`_ROUTES`, `_STREAM_ROUTES`) plus the special cases hand-dispatched in
`Handler._dispatch` (streaming chat POST `/v1/jarvis/chat`, static UI shell
`/` + `/cockpit[/...]`) and emits a deterministic JSON + Markdown contract.
A freeze test regenerates the contract in-memory on every gateway test run
and fails on any drift, so no route can be added/removed/re-pathed/re-authed
or have its owner gate moved without the diff being committed in the same PR.
Before: the wire surface existed only implicitly in `server.py`. After: it is
a committed, pinned, source-derived artifact. `gateway/cockpit/handlers.py`
and `gateway/cockpit/server.py` are untouched (verified: not in the diff).

## Honest census (real counts, not the brief's estimate)

The brief estimated "~108 entries" in `_ROUTES` from its line span
(server.py:50–158); the **real** count is **90 entries** (the span includes
comments). Frozen contract totals:

- **96 routes** = 90 `_ROUTES` + 2 `_STREAM_ROUTES` (SSE) + 1 chat POST
  + 3 static-shell paths (`/`, `/cockpit`, `/cockpit/{path}`)
- **94 distinct handlers** (the 3 static paths share `_serve_static`)
- **10 owner-gated** routes (handler source — or the same-module helper
  `_evaluate_execute_gate` for `job_run`/`coding_execute` — references
  `owner_auth.AUTHORIZATION_PHRASE`; there is no `require_owner` symbol):
  `approvals_decide`, `autonomy_set`, `coding_execute`, `evidence_promote`,
  `job_approve`, `job_publish`, `job_run`, `learning_decide`,
  `model_route_override`, `pair_confirm`. Cross-checked against every
  `AUTHORIZATION_PHRASE` grep hit in `handlers.py`/`handlers_autonomy.py` —
  all accounted for.
- **6 unauthenticated** routes: health, `pair/start`, `pair/confirm`
  (token-less by design, but `pair_confirm` is owner-phrase-gated), and the
  3 static-shell paths.
- `_ROUTES` tuple shape verified by reading server.py:50: `(method,
  compiled-pattern, handler, requires_auth)`; the generator hard-fails if the
  shape ever changes, and also hard-fails if `_dispatch` stops referencing
  `CHAT_PATH` / `_serve_static` / `_match_stream` (stale-special-case guard).

## Owned files (the ONLY files this task may write)

- `scripts/generate_cockpit_contract.py` (new)
- `docs/contracts/cockpit-wire-contract.json` (new, generated)
- `docs/contracts/cockpit-wire-contract.md` (new, generated)
- `tests/gateway/test_cockpit_contract_freeze.py` (new)
- `docs/launch/followups/fu-d3-cockpit-contract-p0.md` (this snapshot)

## Plan (bounded steps)

1. Read `server.py` route tables + `_dispatch`; grep handlers for the real
   owner-gate symbol (`AUTHORIZATION_PHRASE`; no `require_owner` exists). ✓
2. Write the stdlib-only generator (deterministic JSON: sorted keys, routes
   sorted by `(path, method)`, trailing newline; honest Markdown census). ✓
3. Run it twice → byte-identical artifacts; commit both. ✓
4. Write the freeze test (imports `build_contract` via `importlib`, no
   subprocess) with the exact drift message. ✓
5. Proof-of-failure: perturb `_ROUTES` in memory, observe the drift failure;
   final tree clean. ✓

## Validation

- `uv run ruff check scripts/generate_cockpit_contract.py
  tests/gateway/test_cockpit_contract_freeze.py` → **All checks passed!**
- `uv run ty check` (same files) → **All checks passed!** (0 diagnostics;
  one initial `unresolved-attribute` on `__qualname__` fixed with `getattr`)
- `uv run --extra dev python -m pytest
  tests/gateway/test_cockpit_contract_freeze.py -o addopts="" -q` →
  **3 passed**
- Determinism: generator run twice → byte-identical
  (`sha256 cockpit-wire-contract.json =
  6ed4c600f89ad2acb880c2f58c7894bd028640d1ad9ff4dfc542eb27db95eafa`,
  `cockpit-wire-contract.md =
  7ba2b26367c2f0ea3e143d54b959bc52067d10f4efb148a11b0419a74aec9ce9`)
- `python3 scripts/scan_secrets.py --base origin/main` → exit 0
- **Drift-failure proof:** in the same process, `server._ROUTES.pop()` then
  running `test_contract_json_matches_committed` failed with
  `AssertionError: cockpit wire-contract drift — if intentional, regenerate
  via scripts/generate_cockpit_contract.py and commit the diff in the same
  PR` (and showed `route_count 95 != 96`). The perturbation was in-memory
  only; `git status` clean afterward, no edit ever touched `server.py`.

## Residual / follow-on

- Phase 0 freezes the *route inventory* (method/path/auth/gate/handler), not
  per-route request/response body schemas — those are partially covered by
  `gateway/cockpit/contract.py` adapters and remain a later phase.
- The `kind` facet (json/sse/chat-ndjson/static) is descriptive metadata
  derived from the dispatch path, included for the seam work to build on.
- The generator's special-case list for `_dispatch` is hand-enumerated (with
  a stale-guard assertion); if `_dispatch` grows a new special case, the
  guard cannot detect *additions* that don't remove existing seams — the
  reviewer checklist for any `_dispatch` change must include re-running the
  generator.
