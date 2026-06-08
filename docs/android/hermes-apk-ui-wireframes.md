# M.U.S.E. APK Cockpit — UI wireframes

ASCII wireframes for the nine cockpit screens. Phone-first
(360 × 740 dp ≈ 6.0", portrait). System bars not drawn; the
horizontal rules below mark the visible content area only.

> Conventions used in these wireframes:
> - `[ Button ]` filled button, `[· Button ·]` outlined / secondary.
> - `( ○ )` Material switch off, `( ● )` switch on.
> - `▸` collapsed, `▾` expanded.
> - `«` back, `⋯` overflow menu.
> - `▣` skeleton placeholder, `…` truncation.
> - `■` solid swatch, used only for status colour glyphs.

See the [cockpit doc](hermes-apk-cockpit.md) for the screen catalogue
this file illustrates, and the
[API contract](hermes-apk-api-contract.md) for what every screen reads
and writes.

---

## 1. Prompt Command Center

```
─────────────────────────────────────────────
 «  Prompt Command Center                  ⋯
─────────────────────────────────────────────
 Worker
 ( Codex CLI )( Claude Code )( M.U.S.E. batch )
                                  ▸ Custom
─────────────────────────────────────────────
 Workspace
 [ /data/.../projects/hermes              ▾ ]
 Branch hint  [ feature/oauth-callback     ]
─────────────────────────────────────────────
 Prompt
 ╭───────────────────────────────────────╮
 │ ## Goal                               │
 │ Add OAuth callback handler that …     │
 │                                       │
 │ ## Constraints                        │
 │ – do not change the public router     │
 │   surface                             │
 │                                       │
 │ (Safety block is appended on dispatch)│
 ╰───────────────────────────────────────╯
─────────────────────────────────────────────
 [· Save as draft ·]      [   Dispatch    ]
─────────────────────────────────────────────
```

**Notes**

- The worker chip row is **horizontally scrollable**; the last chip is
  always `▸ Custom` which opens a sheet of less-common workers.
- Long-press *Dispatch* → *Dispatch and watch* (the row in the
  dashboard expands automatically and the events screen opens).
- Validation errors land **inline** under the offending field; the
  prompt body is never wiped on error.

---

## 2. Worker Dashboard

```
─────────────────────────────────────────────
   Worker Dashboard                       ⋯
   ■ Live                          [refresh]
─────────────────────────────────────────────
 [ All ][ Running ][ Waiting ][ Done ][ Failed ]
─────────────────────────────────────────────
 ▸ Add OAuth callback handler   ■ running
   Codex CLI · 12m ago
─────────────────────────────────────────────
 ▸ Audit billing module         ■ waiting
   Claude Code · 4m ago     [· Approve ·]
─────────────────────────────────────────────
 ▸ Refactor cron scheduler      ■ failed
   M.U.S.E. batch · 1h ago
─────────────────────────────────────────────
 ▸ Draft release notes 0.15.0   ■ done
   Codex CLI · 3h ago
─────────────────────────────────────────────
 [+]  ← FAB opens Prompt Command Center
```

**Notes**

- `■` is the colour + glyph status badge (running / waiting / failed /
  done). Colour augments the glyph; the glyph alone is sufficient.
- Swipe right on a row → quick **Approve** (only enabled in `waiting`).
- Swipe left → **Cancel** (confirm sheet).
- The live indicator turns amber + says *paused* if SSE drops.

---

## 3. Job Folder Browser

```
─────────────────────────────────────────────
 «  job_01HXYZ — files                    ⋯
─────────────────────────────────────────────
 hermes › src › auth                    ▸ ↵
─────────────────────────────────────────────
 📁  tests
 📄  __init__.py            420 B  18:35
 📄  callback.py           1.2 kB  18:42
 📄  oauth.py              4.1 kB  18:30
─────────────────────────────────────────────
 (tap a file)
 ╭───────────────────────────────────────╮
 │ src/auth/callback.py                  │
 ├───────────────────────────────────────┤
 │   1  from hermes.web import router    │
 │   2  from hermes.auth import …        │
 │   3                                   │
 │   4  @router.get("/oauth/callback")   │
 │   5  async def callback(…):           │
 │  …                                    │
 ╰───────────────────────────────────────╯
                                 [ Copy path ]
                                 [· Open in Termux ·]
─────────────────────────────────────────────
```

**Notes**

- Breadcrumb is horizontally scrollable; the current directory
  segment is pinned right.
- Files >1 MB or binary surface the *Open in Termux* fallback instead
  of a preview.

---

## 4. Diff and Merge Review

```
─────────────────────────────────────────────
 «  Review changes                        ⋯
─────────────────────────────────────────────
 Files changed (3)
 [src/auth/callback.py +42 −3] [tests/… +18 −0] …
─────────────────────────────────────────────
 ── src/auth/callback.py ────────────────────
   1   from hermes.web import router
   2 + from hermes.auth.oauth import …
   3
   4 + @router.get("/oauth/callback")
   5 + async def oauth_callback(req):
   6 +     code = req.query.get("code")
   7 +     if not code:
   8 +         raise HTTPException(400, "missing code")
   9 +     …
  …
─────────────────────────────────────────────
 ── tests/test_auth.py ──────────────────────
   …
─────────────────────────────────────────────
 [· Request revision ·]   [ Approve & merge ]
─────────────────────────────────────────────
```

**Notes**

- Bottom action bar is **sticky**; the user never has to scroll back
  up to approve or reject.
- *Request revision* opens a sheet asking for reviewer notes.
- File-strip chips at the top scroll horizontally and act as anchors —
  tapping jumps the viewport.

---

## 5. Validation Gate

```
─────────────────────────────────────────────
 «  Validation                            ⋯
─────────────────────────────────────────────
 Job: Add OAuth callback handler
 Policy: all gates must pass
─────────────────────────────────────────────
 ✅  Unit tests
     412 passed, 0 failed
─────────────────────────────────────────────
 ✅  Lint (ruff)
     no findings
─────────────────────────────────────────────
 ❌  ty type-check                ⚠ override
     3 errors in src/auth/
     ▾ src/auth/callback.py:42: …
       src/auth/oauth.py:88:    …
       src/auth/oauth.py:91:    …
─────────────────────────────────────────────
 ⏳  Security review
     waiting for review hook
─────────────────────────────────────────────
 [· Re-run gates ·]     [ Override + note ]
─────────────────────────────────────────────
```

**Notes**

- *Override + note* is only visible when **any** failed gate is marked
  `override_allowed=true` by the backend policy. Otherwise the slot is
  hidden so the user is never tempted into a path the backend refuses.
- Failed gates expand inline; the cockpit does not push a separate
  "log" screen for each gate.

---

## 6. GitHub Publisher

```
─────────────────────────────────────────────
 «  Publish                               ⋯
─────────────────────────────────────────────
 origin · feature/oauth-callback → main
 1 commit
   abc1234  feat(auth): add OAuth callback handler
─────────────────────────────────────────────
 Title
 [ feat(auth): add OAuth callback handler ]
─────────────────────────────────────────────
 Body
 ╭───────────────────────────────────────╮
 │ ## Summary                            │
 │ - Adds /oauth/callback route          │
 │ - Wires the redirect back to /login   │
 │                                       │
 │ ## Test plan                          │
 │ - …                                   │
 ╰───────────────────────────────────────╯
─────────────────────────────────────────────
 Draft         ( ● )
─────────────────────────────────────────────
                          [   Publish PR    ]
─────────────────────────────────────────────
```

**Confirm sheet** before the POST:

```
 ╭───────────────────────────────────────╮
 │   You are about to push                │
 │   feature/oauth-callback to            │
 │   origin and open a draft PR           │
 │   against main.                        │
 │                                       │
 │   [· Cancel ·]      [  Confirm  ]     │
 ╰───────────────────────────────────────╯
```

**Notes**

- If the backend has no GitHub credentials, the *Publish PR* button is
  replaced with a banner explaining *PATs live on the backend; configure
  them via `~/.hermes/.env`*. The cockpit never collects a PAT.
- If a PR already exists for this branch (`409 pr_already_exists`),
  *Publish PR* swaps to *Update existing PR*.

---

## 7. Android / Termux Control Panel

```
─────────────────────────────────────────────
   Termux Control Panel                   ⋯
─────────────────────────────────────────────
 Backend                                ■ up
 termux gateway · v0.14.0 · :8080
 2 running · 1 queued · 0 waiting
─────────────────────────────────────────────
   [    Stop gateway    ] [· Restart ·]
─────────────────────────────────────────────
 Keep device awake while orchestrating  ( ● )
   Held by foreground service; release on
   the next idle.
─────────────────────────────────────────────
 ▾ Open in Termux
   [· Open Termux  ·]
   [· Copy last worker prompt ·]
   [· Tail gateway log ·]
─────────────────────────────────────────────
 Pending approvals (1)
 ▸ Force-push feature/oauth-callback
   [· Deny ·]              [ Approve ]
─────────────────────────────────────────────
 Last publish-pending
 ▸ Audit billing module
                          [ Approve publish ]
─────────────────────────────────────────────
```

**Notes**

- *Stop gateway* / *Start gateway* is a single primary button that
  swaps label and colour with the backend status. Restart is
  outlined / secondary.
- *Approve publish* is a shortcut to the most recent job in
  `waiting_for_approval` whose pending decision is publish.
- *Approve destructive command* lives under *Pending approvals* and
  always requires a confirm sheet.
- If Termux is not installed, the *Open in Termux* section collapses
  into a single install card instead of these actions.

---

## 8. Logs and Events

```
─────────────────────────────────────────────
   Logs & Events                          ⋯
   ■ Live (paused stream → ■ amber)
─────────────────────────────────────────────
 [ All ][ info ][ warn ][ error ]
 [ gateway ][ worker ][ hook ][ cron ]
─────────────────────────────────────────────
 18:45:01  i  worker  job_01HXYZ
   Wrote src/auth/callback.py
─────────────────────────────────────────────
 18:44:58  ⚠  hook    job_01HXYZ
   tests/test_auth.py::test_oauth_callback skipped
─────────────────────────────────────────────
 18:44:50  ✕  gateway
   Provider call failed: 429 too many requests
   ▾ attempt 3/5, backoff 4s
─────────────────────────────────────────────
 18:44:32  i  gateway
   Job job_01HXYZ moved to running
─────────────────────────────────────────────
 …
─────────────────────────────────────────────
```

**Notes**

- Each row is one wrapped line; long messages truncate with an
  inline-expand caret. Tapping the timestamp copies the full line.
- Filter chips persist across navigations within the session; they
  reset on app restart.

---

## 9. Settings / Worker Detection

```
─────────────────────────────────────────────
   Settings                               ⋯
─────────────────────────────────────────────
 ▾ Connection
   Gateway URL
   [ https://hermes.example.com           ]
   Gateway token (hidden)
   [ ••••••••••••••••              show 5s ]
   [· Test connection ·]   ■ ok
─────────────────────────────────────────────
 ▾ Workers (gateway-side)               [↻]
   ✅ Codex CLI            v0.6.2  termux
   ✅ M.U.S.E. batch         v0.14.0 internal
   ⚠ Claude Code          not installed
─────────────────────────────────────────────
 ▾ Behaviour
   Auto-subscribe new jobs to events  ( ● )
   Allow Termux intents from this app ( ● )
   Show safety reminders before
   destructive approvals              ( ● )
─────────────────────────────────────────────
 ▾ About
   App  com.aci.hermes  v0.14.0 (debug)
   Gateway  v0.14.0  /v1/cockpit
   [· Reset all cockpit settings ·]
─────────────────────────────────────────────
```

**Notes**

- Sections are accordions (anchors), not tabs. Tabs at 6" portrait
  are awful.
- *Test connection* shows the result inline as ■ status + a
  one-line reason (`Connected`, `Backend unreachable`, `Wrong URL`,
  `Token rejected`).
- Worker detection comes from `/v1/cockpit/runtime/workers`. If the
  endpoint 404s the row reads *"backend predates Phase 18"* and the
  cockpit screens stay navigable but show the empty-state copy from
  the cockpit doc §4.4.

---

## Empty states

Reused across multiple screens:

```
 ╭─────────────────────────────────────╮
 │  No reachable M.U.S.E. gateway.        │
 │                                       │
 │  • Point at one in Settings → Conn.  │
 │  • Start one in Termux from Control  │
 │    Panel.                            │
 │  • Switch to Local handoff if you    │
 │    only want clipboard handoff to    │
 │    Codex / Claude / ChatGPT.         │
 ╰─────────────────────────────────────╯
```

The same card is rendered on the Worker Dashboard, Job Folder Browser,
Diff Review, Validation Gate, GitHub Publisher, and Logs screens when
the gateway is unreachable. The Prompt Command Center can still author
drafts locally, and the Termux Control Panel still works for
starting / stopping the gateway, so they show a smaller inline banner
instead of the full empty card.
