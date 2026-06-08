# FU-14 — Depth cockpit: close the "consume gap"

**Status:** in-review
**Branch:** `claude/fu-14-cockpit-consume-gap` (cut from `main` @ `b74f9889`)
**Owner of this snapshot:** the FU-14 builder agent (sole writer)

## Intent

The browser cockpit shell existed but threw away the rich backend: it polled
`GET /v1/cockpit/jobs` on an 8s timer (no SSE), rendered approvals read-only,
and had no phase rail, model switcher, or first-run pairing. This follow-up
makes the shell a real operator surface by **consuming endpoints that already
exist on the server** — no new server routes, client-only.

## What the shell now does

1. **Live jobs via SSE.** Replaced the `setInterval` poll of `/v1/cockpit/jobs`
   with a live subscription to the SSE endpoint `GET /v1/cockpit/jobs/stream`.
   It consumes the server's `job.upsert` / `job.removed` / `heartbeat` events
   and reconnects with backoff when the server hits its per-stream duration cap.
   - **Why fetch-stream, not a bare `EventSource`:** the server authorizes the
     stream **only** via the `Authorization` header (`server._authed()` →
     `auth.extract_bearer(headers["Authorization"])`; there is no query-token
     path). A native `EventSource` cannot attach headers. So the shell streams
     the `text/event-stream` body via `fetch()` carrying the bearer token the
     same way every other API call does, and parses SSE frames itself. This is
     a genuine live subscription (no polling). Falls back to a one-shot poll
     only if `fetch`/`ReadableStream`/`AbortController` are unavailable. (The
     old code's claim that the server "also accepts" a query-param token was
     incorrect — verified against `auth.py` and `server._authed()`.)
2. **Phase rail.** Each job card renders a visible per-job phase progression
   (Queued → Running → Approval → Approved → Publishing → Published), lit with
   the spectral ring; terminal `FAILED`/`CANCELLED` render a failed node. The
   phases mirror the server's `contract.JOB_STATUSES` vocabulary.
3. **Owner-gated approve / deny.** The Approvals tab now has Approve/Deny
   controls that `POST /v1/cockpit/approvals/{id}` with
   `{decision, authorization}`. The exact owner phrase is **prompted at action
   time** (never hardcoded or stored); a `403` re-prompts once. Reject sends no
   phrase but still re-prompts on a `403`.
4. **Model switcher.** The Routes tab reads `GET /v1/cockpit/model-routes` and
   lets the operator pin a task class to a model (chosen + fallbacks, or "auto"
   to clear) via `POST /v1/cockpit/model-routes/override`
   (`{task_class, model}`; empty `model` clears).
5. **First-run auto-pair.** When there is no token, a banner surfaces a pairing
   flow: `POST /v1/cockpit/pair/start` → show the short-lived code →
   `POST /v1/cockpit/pair/confirm` with `{pairing_code, authorization}` →
   store the minted per-device token. A `403`/`429` is surfaced honestly.
   "Paste a token instead" remains available.
6. **Autonomy control.** New Autonomy tab reads `GET /v1/cockpit/autonomy` and
   sets the level via `POST /v1/cockpit/autonomy`. A **raise** (more autonomy
   than current) attaches the owner `authorization` phrase and handles a `403`
   by re-prompting. (Forward-compatible: this branch predates the server-side
   raise gate; sending the field is harmless when the gate isn't present.)
   Revoke → Assisted is one click.
7. **Look preserved.** Uses the existing `tokens.css` Singularity variables
   (`--void`, `--core`, `--ring-1/2`, `--ok`, `--danger`). New phase-rail and
   live-dot styles live in `index.html`'s `<style>` block and reuse those
   existing tokens, so `tokens.css` needed no change. No new framework, no
   build step, stdlib/static only.

## Owned (writable) files

- `gateway/cockpit/static/index.html` — the shell (rewritten to consume the backend).
- `gateway/cockpit/static/tokens.css` — unchanged (existing tokens sufficed).
- `tests/gateway/test_cockpit_static_ui.py` — new consume-gap assertions +
  percent-encoded path-traversal cases.
- `docs/launch/followups/fu-14-cockpit-consume-gap.md` — this snapshot.

## Constraints honored

- **Client-only:** no edits to `server.py` / `handlers.py`; no new routes.
- **No build step / no CDN:** all inline static; CSP-friendly.
- **Additive:** the shell still loads unauthenticated; API calls carry the
  token afterward. Default server code paths are byte-for-byte unchanged.

## Validation

- `uv run ruff check tests/gateway/test_cockpit_static_ui.py` → **All checks passed**
- `python -m pytest tests/gateway/test_cockpit_static_ui.py -o addopts="" -q` →
  **16 passed**
- JS re-read against real endpoint shapes confirmed in `handlers.py` /
  `contract.py` / `task_router.py` / `auth.py` (SSE event names + CockpitJob
  fields, ApprovalCard shape + 403 owner gate, model-routes `to_dict` +
  override body, autonomy levels + status shape, pair start/confirm bodies).
- Live probe: percent-encoded traversal paths fall back to the SPA index
  (status 200, no server source bytes leaked).

## Residual risks / assumptions

- **Test assertion wording:** the task asked the test to assert "an EventSource
  subscription." Because a native `EventSource` cannot authenticate against the
  unmodified server (header-only auth), the shell subscribes via a fetch SSE
  reader; the tests assert the load-bearing facts instead — subscription to
  `/v1/cockpit/jobs/stream`, `text/event-stream`, and the `job.upsert` /
  `job.removed` event names. This is the substance of "consume the SSE stream"
  and is robust to the header-vs-EventSource detail.
- The autonomy raise gate is not on this base branch; the client sends the
  `authorization` field on raises anyway (harmless now, correct once merged).
- SSE frame parsing normalizes CRLF→LF and splits on a blank line, matching the
  server's `_sse_send` format; a partial frame is buffered until complete.
