# Jarvis Prime — research translation map (Python runtime ↔ Android cockpit)

This document maps every concept in the Jarvis Prime Python runtime
(`hermes_cli/jarvis_prime/`) and the operating-system spec
(`docs/jarvis-prime-operating-system.md`) to the corresponding
Android surface — what already exists in `apps/android/`, what needs
to be built, and which wave it lands in (from the
[roadmap](jarvis-prime-app-finish-roadmap.md)).

Source layout (4275 LOC, 18 modules, 159 passing tests):

```
hermes_cli/jarvis_prime/
├── __init__.py             public API
├── __main__.py             CLI entry point
├── awareness.py            six-stream live perception
├── communication_style.py  tone shaping
├── epistemics.py           truth / audit gate
├── gates.py                eight verification gates
├── memory.py               MemoryRecord + MemoryStore (JSONL journal)
├── modes.py                Mode + ModeClassifier (six modes)
├── onboarding.py           first-run onboarding
├── owner_auth.py           authorization phrase + OWNER_GATED_ACTIONS
├── persona.py              voice/identity prompt builder
├── reasoning.py            Reasoner / Inference / Rule
├── research.py             ResearchBrief / open_brief
├── router.py               Route decisions across surfaces
├── runtime.py              JarvisPrime orchestrator (the entry)
├── self_update.py          Proposal / ProposalBook
├── social_research.py      social signal harvesting
└── tick.py                 scheduled tick handler
```

---

## 1. Modes (six)

Source: `modes.py:Mode` / `ModeClassifier`,
spec §"Modes" in `docs/jarvis-prime-operating-system.md`.

| Mode | Spec rules | Android surface today | Android surface target | Wave |
|---|---|---|---|---|
| Companion | Tone-aware, separate empathy from technical judgment, no temporary emotion saved as memory. | None. | Mode chip on top bar; persona-aware prompt shaping for chat-type tasks (when chat lands as a future wave). | W2 |
| Strategy | Plain tradeoffs, highest-leverage path, what *not* to do. | None. | Mode chip + Settings → Mode picker; dispatch sends mode hint to gateway. | W2 |
| Critic | Contrarian review, strongest objection first, fatal vs fixable. | None. | Mode chip; review-task target tool defaults to Claude when mode is Critic. | W2 |
| Operator | Convert chaos into a task packet; smallest useful route. | The whole shipped *Orchestrator* dashboard is operator-mode-shaped — task list, prompt builder, copy/open. | Make it explicit: when mode is Operator, the dashboard is the entry; the task editor is the default route. | W2 |
| Builder | Repo work, Claude Code / Codex handoffs, tests, rollback notes. | `TargetTool.CODEX` / `CLAUDE_CODE` + `TaskType.BUILD` selectors. | Add gates panel (P-01 in the gap map) to TaskDetail when mode is Builder. | W2 |
| Mobile Voice | Short responses, no long code, no diff review, defer destructive commands. | None. | Voice intake screen (W4) + driving-mode toggle (W4) + auto-pick `MOBILE_VOICE_FORMAT` persona on dispatch. | W4 |

ModeClassifier behavior: the runtime infers mode from
`ClassifierContext` (explicit override > driving/voice signal > task
intent). The Android side should provide:

- Explicit override via Settings → Mode (W2).
- Driving signal via the Driving mode toggle (W4).
- Voice signal when entering via the Voice Intake screen (W4).

---

## 2. Persona

Source: `persona.py:Persona`, `PersonaPrompt`, three formats:
`DEFAULT_FORMAT`, `OPERATOR_FORMAT`, `MOBILE_VOICE_FORMAT`.

| Format | When used | Android trigger today | Android trigger target | Wave |
|---|---|---|---|---|
| DEFAULT_FORMAT | Normal conversation flow (5- to 6-line structure). | n/a | Default for chat tasks once Chat lands; not part of W1-W4. | future |
| OPERATOR_FORMAT | Cockpit dispatch and task editor. | The PromptBuilder's nine sections already echo OPERATOR_FORMAT — but not bound to the runtime. | Dispatch payloads include `persona = OPERATOR_FORMAT` so the gateway can pin behavior on the same axis as the local prompt. | W1 |
| MOBILE_VOICE_FORMAT | Voice intake / driving mode. | n/a | Voice Intake screen pins this; dispatched dispatches set `persona = MOBILE_VOICE_FORMAT`. | W4 |

PromptBuilder (`apps/android/app/src/main/java/com/aci/hermes/data/orchestrator/PromptBuilder.kt`)
is a static, kotlin-side template. The Wave 2+ direction is **not** to
duplicate the Python builder in Kotlin — the cockpit sends the task
payload to the gateway and the gateway returns the persona-shaped
prompt back. The local builder stays as the offline / local-handoff
fallback only.

---

## 3. Memory

Source: `memory.py:MemoryRecord`, `MemoryStore` (JSONL journal,
expiry support, dedup).

| Concept | Python | Android today | Android target | Wave |
|---|---|---|---|---|
| MemoryRecord | `kind`, `text`, `source`, `created_at`, `expires_at` | n/a | `data/memory/MemoryRecord.kt` data class; deserialized from gateway. | W2 |
| MemoryStore (journal) | Append-only JSONL with dedup | n/a | Gateway-side; cockpit reads only. No local memory store on Android. | W2 |
| Memory rules | What gets saved / what doesn't (spec §Memory Rules) | n/a | Static card on MemoryScreen header listing the rules verbatim. | W2 |
| Forget verb | `MemoryStore.forget` | n/a | "Forget this fact" button on each record with confirmation. | W2 |
| Save verb | `MemoryStore.remember` | n/a | "Save this as durable memory" long-press on a task. | W2 |
| Expiry visibility | `expires_at` field | n/a | Pill on each record: "renews 2026-08-12" or "expires in 30 days". | W2 |

Owner promise mirrored from `docs/jarvis-prime-operating-system.md`
§Memory Rules: the Android UI must never offer to save secrets,
temporary emotions, raw voice dumps, or stale issue numbers, and
must say so on the Memory screen.

---

## 4. Gates (eight)

Source: `gates.py:Gate`, `GateOutcome`, `GateResult`, `GateSummary`,
+ `docs/jarvis-verification-gates.md`.

| Gate | Spec triggers | Android today | Android target | Wave |
|---|---|---|---|---|
| Planning | Required files exist, references coherent. | None. | Render badge in JobDetail. | W2 |
| Build | Compile, lint, dep audit. | None. | Badge + tap-through to validation log excerpt. | W2 |
| Review | Diff reviewed, no scope drift. | None. | Badge + tap-through to review notes / Codex Reviewer output. | W2 |
| Test | Tests run / reason for no-run. | None. | Badge + tap-through to test output. | W2 |
| Security | No secrets, no exfil paths. | None. | Badge + tap-through to security report. | W2 |
| Release | Versioning, changelog, signing. | None. | Badge + tap-through to release evidence. | W2 |
| Owner Approval | `Yes, with authorization.` recorded. | None. | Badge bound to the in-app owner-auth dialog. | W2 |
| Rollback | Rollback path documented. | None. | Badge bound to the task's rollback notes field. | W2 |

`GatesPanel` is shared across JobDetail and TaskDetail (when a task
has been dispatched as a cockpit job). The badge colors use
`GateOutcome` (PASS / WARN / FAIL / N_A) — same colors the runtime
returns.

---

## 5. Owner authorization

Source: `owner_auth.py:AUTHORIZATION_PHRASE = "Yes, with authorization."`,
`OWNER_GATED_ACTIONS` set, `OwnerAuth`, `OwnerGate`.

Owner-gated actions (the Python source of truth):

- spending money
- posting publicly
- creating third-party accounts
- OAuth or credential changes
- production deploys
- DNS changes
- main-branch merges
- package publishing
- app store submissions
- regulated claims (legal / compliance / security / health / financial)

Android target (W2):

- `OwnerAuthorizationDialog.kt` Composable that captures the literal
  phrase — case sensitive, trailing period required, exact-match
  comparison against `AUTHORIZATION_PHRASE`.
- Authorization is held **in memory only** (not persisted to
  DataStore) and clears on process death — same lifecycle as the
  Python runtime's per-session cache.
- The Approvals screen renders the gated-action kind from the
  gateway's `PendingApproval.kind`; the dialog text references the
  matching `OWNER_GATED_ACTIONS` entry verbatim.
- The cockpit must show the same set of gated actions even when the
  gateway is unreachable, so a user can read the policy offline.

---

## 6. Awareness (six-stream perception)

Source: `awareness.py:perceive`, `AwarenessSnapshot`,
`GatewayState`, `GitHubSnapshot`, `JobStatus`, `TelemetrySnapshot`,
`UserProfile`, `MemoryRecord`.

| Stream | Python | Android today | Android target | Wave |
|---|---|---|---|---|
| Gateway state | `GatewayState` (running, mode, started_at, queue) | None. | "Awareness card" on Orchestrator dashboard. | W3 |
| GitHub snapshot | `GitHubSnapshot` (open PRs, failing checks) | None. | Section in the awareness card; tap-through opens PR list. | W3 |
| Job status | `JobStatus` (running, queued, waiting_approval) | None. | Section in the awareness card; tap-through opens Cockpit. | W1 (read-only) / W2 (with approvals) |
| Telemetry | `TelemetrySnapshot` (memory load, recent decisions) | `LogBuffer` (ephemeral) | Diagnostics screen extension — show recent decisions next to logs. | W3 |
| User profile | `UserProfile` (preferred builder/reviewer, modes, …) | `SettingsRepository.preferredBuilder`/`preferredReviewer` | Already wired; expand to include the Wave 2 mode + Wave 4 voice flags. | W2 / W4 |
| Memory records | `MemoryRecord` | None. | Memory screen (§3). | W2 |

The Awareness card is intentionally a digest, not a feed —
`docs/jarvis-prime-operating-system.md` §Non-Goals forbids the
cockpit becoming an "always-on" surface.

---

## 7. Router

Source: `router.py:Router`, `RouteDecision`, `RouteTarget`.

Routes (Python):

- Direct answer
- AOS Council (specialist review)
- Claude Code (primary build)
- Codex (review / bounded fix)
- Mobile Voice (capture only)

Android target (W2): the Router decision is invoked **on the
gateway**; the cockpit just renders `RouteDecision.target` as a chip
on the JobDetail header. Tap-through explains why the route was
chosen (`RouteDecision.reason`).

The cockpit must **not** decide routes locally. The router is an
asymmetric authority: gateway owns the choice, cockpit owns the
display.

---

## 8. Reasoning

Source: `reasoning.py:Reasoner`, `Inference`, `Premise`, `Rule`,
`ReasoningKind`, `deduce`, `induce`, `should_research`.

Android target: not directly surfaced in the cockpit. Reasoning is
internal to the gateway and only ever appears as part of a
`RouteDecision.reason` (W2 §7) or an `AuditReport` (W2 §9).

---

## 9. Epistemics

Source: `epistemics.py:audit_response`, `AuditReport`, `AuditOutcome`.

Android target:

- A small "audit confidence" pill on the JobDetail header (W2).
- The `AuditReport.evidence` items become the per-task evidence list
  (L-03 in the gap map).

---

## 10. Research

Source: `research.py:open_brief`, `ResearchBrief`, `ResearchQuestion`,
`ResearchScope`, `needs_research`.

Android target: a dedicated *Research* task type is not added in the
roadmap (already covered by `TaskType.RESEARCH`). The cockpit
displays the gateway-returned `ResearchBrief` as a markdown card in
the task detail screen (W2).

---

## 11. Self-update

Source: `self_update.py:Proposal`, `ProposalBook`, `ProposalEvidence`,
`ProposalKind`, `ProposalStatus`.

Android target: NTH — a "Jarvis suggests" inbox where the runtime's
self-improvement proposals (e.g. "rename this skill", "this gate is
flaky") surface to the user. Not part of W0-W4. Tracked here so the
proposals don't get lost during the rebrand.

---

## 12. Onboarding

Source: `onboarding.py` (430 LOC, the most behavior-heavy module).

Android target (W0 + W1 split):

- W0: Splash + minimal "Welcome to Jarvis Prime" card; preserves the
  existing `SettingsRepository.hasOnboarded` flag.
- W1: After the Connection screen lands, the onboarding flow asks
  the user (in order):
  1. Choose mode (Operator default).
  2. Configure gateway (or pick Local handoff).
  3. Acknowledge owner-gate policy (read-only excerpt of
     `OWNER_GATED_ACTIONS`).
  4. Acknowledge memory rules (read-only excerpt of Memory Rules).

The notification permission prompt currently fires in `MainActivity`
on every cold launch where it isn't granted. Onboarding moves that
prompt **into the explainer step** so the user understands *why*
before granting (W0).

---

## 13. Communication style

Source: `communication_style.py`.

Android target: prompt shaping per mode is gateway-side. The cockpit
ensures the dispatch payload carries enough mode/persona context
that the gateway can apply the right style — and the cockpit
itself does not paraphrase model output.

---

## 14. Tick

Source: `tick.py`.

Android target: none. Scheduled ticks run on the gateway. The
cockpit observes the tick-driven state via `AwarenessSnapshot`
updates.

---

## 15. CLI entry point

Source: `__main__.py`.

Android target: not used. The cockpit talks to the gateway, not to
the local Python CLI. Termux users continue to use `hermes` from a
shell.

---

## 16. Translation summary

| Python module | Android wave(s) | Cockpit screen / surface |
|---|---|---|
| `modes.py` | W2 (UI) + W4 (driving) | Settings → Mode; top-bar mode chip |
| `persona.py` | W1 (dispatch) + W4 (voice) | Implicit in dispatch payload |
| `memory.py` | W2 | MemoryScreen |
| `gates.py` | W2 | GatesPanel embedded in JobDetail + TaskDetail |
| `owner_auth.py` | W2 | OwnerAuthorizationDialog + Approvals |
| `awareness.py` | W1 / W2 / W3 | Awareness card; Cockpit; Memory |
| `router.py` | W2 | RouteDecision chip on JobDetail |
| `epistemics.py` | W2 | Audit confidence pill |
| `research.py` | W2 | Research brief card in TaskDetail |
| `self_update.py` | NTH | (later) Suggestions inbox |
| `reasoning.py` | indirect | Surfaces via RouteDecision.reason |
| `communication_style.py` | indirect | Gateway-side; not surfaced |
| `onboarding.py` | W0 / W1 | Splash + onboarding cards |
| `tick.py` | indirect | Awareness card refresh trigger |
| `social_research.py` | indirect | Optional; surfaces as a `ResearchBrief` source field |
| `runtime.py` | indirect | All cockpit traffic terminates here on the gateway |

---

## 17. Cross-references

- Audit body: [`jarvis-prime-app-deep-audit.md`](jarvis-prime-app-deep-audit.md)
- Gap map: [`jarvis-prime-app-final-gap-map.md`](jarvis-prime-app-final-gap-map.md)
- Roadmap: [`jarvis-prime-app-finish-roadmap.md`](jarvis-prime-app-finish-roadmap.md)
- Permissions: [`jarvis-prime-app-permission-risk-register.md`](jarvis-prime-app-permission-risk-register.md)
- Operating system spec: [`jarvis-prime-operating-system.md`](jarvis-prime-operating-system.md)
- Verification gates: [`jarvis-verification-gates.md`](jarvis-verification-gates.md)
- Routing model: [`aos-jarvis-agent-routing.md`](aos-jarvis-agent-routing.md)
- Skill: [`/skills/jarvis-prime/SKILL.md`](../skills/jarvis-prime/SKILL.md)
- Runtime source: `hermes_cli/jarvis_prime/`
