# JARVIS Prime mobile chat — streaming, phases & tool visibility

The Chat tab is the primary mobile surface for JARVIS Prime. It streams
the **real** agent (or an offline-safe mock) and now shows *what the agent
is doing*, not just the final words: a phase rail, compact tool activity,
and one-tap evidence/ledger inspection — with inline owner approvals.

This is an additive extension of the existing chat stack
(`apps/android/.../ui/screens/chat/`, `data/jarvis/`, and the gateway in
`gateway/jarvis_local_http.py` + `gateway/cockpit/agent.py`). Older app
builds ignore the new chunk types, and older gateways simply don't emit
them, so both ends stay forward/backward compatible.

## Wire contract

The chat stream is newline-delimited JSON (`application/x-ndjson`) over
`POST /v1/jarvis/chat`. Each line is one chunk. The original vocabulary is
unchanged:

```
{"type":"thinking"}
{"type":"working","label":"Searching the repo"}
{"type":"tone","tone":"SERIOUS"}
{"type":"body","text":"On it."}
{"type":"detail","text":"Longer reasoning…"}
{"type":"done"}
{"type":"error","message":"…","retryHint":"…"}
```

### New, additive chunk types

| Chunk | Shape | Purpose |
|---|---|---|
| `phase` | `{"type":"phase","phase":"ROUTING"}` | Progress rail. One of `RECEIVING, THINKING, ROUTING, TOOL, CODING, RESEARCH, VERIFICATION, FINAL`. |
| `tool_call` | `{"type":"tool_call","id","name","summary","status":"START\|OK\|FAIL","detail"?}` | One inline tool run. Emitted twice (START then a terminal status); the app folds both into one animating chip keyed by `id`. |
| `evidence` | `{"type":"evidence","auditId","title"}` | Reference the app resolves via `GET /v1/cockpit/audit/{id}/proof`. |
| `ledger` | `{"type":"ledger","ledgerId","title"}` | Reference the app resolves via `GET /v1/cockpit/audit`. |

Chunk builders live in `gateway/jarvis_local_http.py`; the Kotlin mirror is
`data/jarvis/JarvisChatChunk.kt` + `JarvisToolActivity.kt`. The two ends are
kept 1:1 — the phase names and tool statuses are the same constants
(`PHASES` / `TOOL_STATUSES` ↔ `JarvisPhase` / `JarvisToolStatus`).

### Redaction

Every `tool_call` `summary`/`detail` is scrubbed through
`hermes_cli.secrets_policy.redact` **inside the chunk builder**, so a tool
arg or result that captured a token can never reach the wire even if a
caller forgets to pre-redact. (Branch names in `git_status` are left
intact — they aren't secrets and would otherwise trip the high-entropy
matcher.)

## Inline tools (real, read-only, gated)

For code-shaped turns (`builder` mode or a code route target) the responder
runs a tiny, allowlisted, **read-only** repo inspector inline and streams
each call:

- `git_status` — porcelain status summary (never mutates),
- `repo_grep` — bounded source search, returns *paths only* (never file
  contents),
- `repo_read` — a size-capped, path-traversal-safe head slice of one file.

Implemented in `gateway/cockpit/inline_tools.py`. Hard caps keep a turn
well under half a second. Anything irreversible or external (deploy,
publish, push, OAuth, spend) is **never** run here — it stays a pending
owner gate surfaced by the JARVIS route and decided through the approval
flow below.

## Message actions

Each Jarvis reply offers:

- **Copy** — body + detail to the clipboard.
- **Continue** — re-streams from where the reply left off (sends a
  lightweight `continue` directive through the same gated path; the prior
  transcript is the context). Adds no new user turn.
- **Create job** — promotes the reply into a job. Dispatches to the cockpit
  job queue (`POST /v1/cockpit/jobs`) when a gateway is paired; falls back
  to a local DRAFT task in the orchestrator otherwise. Worker routing
  reuses `JarvisIntentClassifier`.
- **Inspect evidence / ledger** — chips appear when the turn carries
  `evidence`/`ledger` refs; tapping opens a bottom sheet resolved from the
  cockpit audit/proof endpoints.
- **Approve / Hold** — on the inline Approval card. When the card carries a
  live `approvalId` and a gateway is paired, approving submits the owner
  phrase (`Yes, with authorization.`) to `POST /v1/cockpit/approvals/{id}`;
  the gateway still enforces it server-side. Synthesized/mock cards stay
  local-only. The optimistic UI flip is rolled back if the gateway
  declines.

## Mock vs. real

`RoutingJarvisChatGateway` selects per-send: paired → live
(`HttpJarvisChatGateway` → cockpit), otherwise the offline
`MockJarvisChatGateway`. The mock emits the full vocabulary (phases, two
redacted tool calls, evidence + ledger refs for task-shaped prompts) so the
surface is demoable and deterministically testable with no daemon.

## Files

| Concern | File |
|---|---|
| Wire builders + redaction | `gateway/jarvis_local_http.py` |
| Phase/tool/ref emission | `gateway/cockpit/agent.py` |
| Inline read-only tools | `gateway/cockpit/inline_tools.py` |
| Chunk + message model | `data/jarvis/JarvisChatChunk.kt`, `JarvisChatMessage.kt`, `JarvisToolActivity.kt` |
| Stream parsing | `data/jarvis/HttpJarvisChatGateway.kt` |
| View-model ports | `data/jarvis/JarvisChatPorts.kt`, `data/cockpit/CockpitChatPorts.kt` |
| State machine | `ui/screens/chat/JarvisChatViewModel.kt` |
| UI | `ui/screens/chat/JarvisChatScreen.kt` |

## Tests

- Python: `tests/gateway/test_jarvis_local_http.py` (chunk builders +
  redaction), `tests/gateway/test_cockpit_inline_tools.py` (read-only/
  traversal-safe tools, phase order, gated tool emission).
- Kotlin: `JarvisChatViewModelTest` (phases, tool fold/expand, continue,
  create-job paired/unpaired, live approve + rollback, record inspect),
  `MockJarvisChatGatewayTest` (phase + tool + ref emission).
