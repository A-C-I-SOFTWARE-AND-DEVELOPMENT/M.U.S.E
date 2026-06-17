# NEXUS — External Adapter Contracts

Every surface NEXUS talks to implements the `AgentSurface` interface
(`src/lib/types.ts`). This file documents the concrete wire contracts so a
maintainer can wire a backend without reading the UI.

```ts
interface AgentSurface {
  id: string;
  kind: 'muse' | 'antigravity' | 'aistudio';
  canEmbed: boolean;                 // true ONLY for muse
  listAgents(): Promise<AgentSummary[]>;
  getStatus(agentId: string): Promise<AgentStatus>;
  openExternal?(agentId: string): void;                       // link-out surfaces
  applySteering?(agentId: string, v: SteeringVector): Promise<void>; // muse only
}
```

---

## 1. M.U.S.E. (deep integration — the only backend the user owns)

Base URL: `VITE_MUSE_BASE_URL` (e.g. `https://muse.example.com`). All paths are
relative to it. When unset, every call degrades to an **honest empty state** —
NEXUS never fabricates data.

| Purpose | Method & Path | Response shape |
|---|---|---|
| List AOS Council agents | `GET /api/agents` | `AgentSummary[]` |
| Agent status | `GET /api/agents/:id/status` | `AgentStatus` |
| **Apply steering vector** | `POST /api/agents/:id/steer` | `204` |
| Live metrics (telemetry panel) | `GET /api/metrics` | `{ loss, accuracy, epoch, trainingSets }` |
| Event stream (activity feed) | `GET /api/events` (SSE) | `ActivityEvent` frames |
| Register push device | `POST /api/push/subscribe` | `204` |
| Voice STT transcript | `POST /api/voice/stt` `{transcript}` | `204` |
| Observatory snapshot | `GET /v1/observatory/snapshot` | boot map (clusters, stations, ladder) |
| Observatory stream (SSE) | `GET /v1/observatory/stream` | `job.stage` / `gate.verdict` / `node.activate` / `route.decision` / `resync` |

### `AgentSummary`
```jsonc
{ "id": "council-architect", "name": "Principal Systems Architect",
  "surface": "muse", "role": "architecture", "state": "idle" }
```
`state ∈ idle | running | error | needs-auth | unknown`.

### Steering payload — `POST /api/agents/:id/steer`
The octagon emits this exact object (debounced ~120ms). The practical payload is
`inference`, which maps onto M.U.S.E.'s model-routing layer:

```jsonc
{
  "profileId": "default",
  "weights": { "reasoning": 0.21, "creativity": 0.05, "...": 0.0 }, // sums to 1.0
  "dominant": "coding",
  "glowState": { "color": "#34E5C8", "pulse": false, "label": "Coding-dominant" },
  "inference": {
    "temperature": 0.41,        // creativity↑ raises, coding/logic↓ lower (0..2)
    "topP": 0.78,               // creativity↑ widens, factuality↓ narrows
    "maxThinkingTokens": 3200,  // contemplation/reasoning buy thinking budget
    "groundingStrength": 0.12,  // factuality drives retrieval reliance (0..1)
    "systemStyleHint": "precise, technical, terse"
  },
  "timestamp": 1718600000000
}
```

> The `inference.*` curves are **tunable starting points** (see
> `weightsToInference` in `src/lib/steering.ts`), not ground truth. Adjust the
> coefficients to match your router's behavior.

### Metrics — `GET /api/metrics`
```jsonc
{ "loss": 1.535, "accuracy": 0.593, "epoch": 8430, "trainingSets": 12 }
```
Any missing field renders as `—`. If the endpoint 404s or the base URL is unset,
the telemetry panel shows **"No live metrics — connect an agent."**

### Events (SSE) — `GET /api/events`
Each `message` frame is JSON:
```jsonc
{ "id": "evt_1", "surface": "muse", "agentId": "council-architect",
  "kind": "run-completed", "message": "Goal→PR run finished", "timestamp": 1718600000000 }
```
`kind ∈ run-started | run-completed | error | pr-opened | idle | needs-auth`.

### Voice bridge
NEXUS integrates the **existing** M.U.S.E. voice bridge (Flask + Web Speech API).
It is NOT reimplemented here. NEXUS requests microphone permission, runs Web
Speech STT/TTS locally, and POSTs settled transcripts to `/api/voice/stt`
(`src/lib/voice.ts`). Configure the bridge on the M.U.S.E. side.

### Neural Observatory (the live "mirror" dashboard)
NEXUS renders the read-only `/v1/observatory/*` route family
(`docs/synapse/design/10-observatory-spec.md`) — the web member of MUSE's
cross-device live-wallpaper program. `GET /v1/observatory/snapshot` boots the
galaxy (clusters with `pos`/`radius`/`heat`, station graph, Brain Ladder tiers);
`GET /v1/observatory/stream` (SSE) drives live pulses. Render-only and honest:
the `{"status":"unavailable"}` graph shape → `bGraphAvailable=false` → dormant
dressing (zero planets), and `heat: null` → neutral grey, never a guessed glow.
See `src/adapters/observatory.ts`.

---

## 2. Antigravity & AI Studio (LINK-OUT ONLY)

These are **not embeddable**. Both send `X-Frame-Options` /
restrictive `frame-ancestors` CSP and refuse to render in an iframe, and neither
exposes an embeddable SDK. NEXUS deep-links out instead — do **not** try to
iframe them (a code comment in `src/adapters/index.ts` says the same).

| Surface | Deep link |
|---|---|
| Antigravity | `https://antigravity.google/` (set to your launch URL) |
| AI Studio | `https://aistudio.google.com/prompts/new_chat` |

`listAgents()` returns a single known placeholder; `getStatus()` returns
`unknown` unless you later wire a status API. The primary action is
`openExternal()` → new browser tab / Android Custom Tab.

---

## 3. Adding a new surface

Implement `AgentSurface`, add it to `surfaces` in `src/adapters/index.ts`. No UI
changes are required — the Console, Agents, and Activity views are all
surface-agnostic.
