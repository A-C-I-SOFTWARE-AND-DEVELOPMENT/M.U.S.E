# MUSE — Android App Product Specification

> **Status:** product spec, v1.
> **Branch context:** transforms the existing native module at
> [`apps/android/`](../apps/android/) into **MUSE**.
> **Companion docs:**
> [`jarvis-prime-app-user-flows.md`](jarvis-prime-app-user-flows.md),
> [`jarvis-prime-app-screen-map.md`](jarvis-prime-app-screen-map.md),
> [`jarvis-prime-app-onboarding-spec.md`](jarvis-prime-app-onboarding-spec.md),
> [`jarvis-prime-app-launch-standard.md`](jarvis-prime-app-launch-standard.md).
>
> **Naming policy.** Externally, the product is **MUSE**.
> The legacy name *Hermes* survives only inside this repository as a
> technical compatibility surface — package id `com.aci.hermes`,
> gateway path `/v1/*`, and the local foreground service class
> `HermesService`. Those identifiers are intentionally not renamed so
> existing installs, signed releases, and the running Python gateway
> keep working. User-visible strings, screen titles, voice readbacks,
> notifications, lock-screen widgets, marketing copy, and app store
> metadata all say **MUSE**.

---

## 1. Product promise

**MUSE is a mobile-first AI operating partner that lets the
owner talk, command, approve, monitor, remember, verify, and stop
work from one app.**

The owner is the single source of authority. The app's job is to
keep that authority reachable from the phone — at the desk, on the
treadmill, in the car, in the airport, and at 2 a.m.

Eight verbs anchor the entire product:

| Verb | What the app must always make possible |
|---|---|
| **Talk** | A real conversation with MUSE, voice or text, in one tap from launch. |
| **Command** | Convert a rough idea into a runnable task without sitting down at a desk. |
| **Approve** | Pass owner gates (spend, deploy, publish, OAuth, main-branch merge, package publish, credential change, regulated claims) on a phone, with full diff visible and a hard-to-misfire confirm. |
| **Monitor** | See what MUSE, the AOS Council, and the workers are doing right now, in plain English, at a glance. |
| **Remember** | Inspect, correct, and delete the durable memory MUSE is using to make decisions. |
| **Verify** | Read the audit / proof history of any consequential action, before or after it happens. |
| **Stop** | Trigger an emergency stop from any screen, in one gesture, with no possibility of accidental dispatch in the same flow. |
| **Resume** | Bring MUSE back online safely after an emergency stop with a written confirmation. |

Anything in the app that does not serve one of these eight verbs is a
candidate for removal.

---

## 2. Operating principles (mobile-first)

These are non-negotiable. Every screen, every flow, every component
in this spec is reviewed against them.

1. **Glanceable.** The owner can answer *"what is MUSE doing right
   now?"* in under one second from any screen, without scrolling.
2. **Status-first.** Every screen renders its state (a coloured pill,
   a glyph, a one-line summary) before its body.
3. **One-thumb.** Every primary action is reachable with the right
   thumb on a 6-inch screen held vertically. Two-handed gestures are
   never required for primary flows.
4. **Voice-equivalent.** Anything tappable on a primary flow is also
   reachable by voice, including approval and emergency stop. Typing
   is never the only path.
5. **Approvals are explicit.** Risky actions are gated by a two-step
   confirm. Critical actions are gated by a two-step confirm **plus**
   an Impact Report. There is no quiet "tap to approve."
6. **Memory is owner-correctable.** Every durable memory fact is
   visible, editable, and deletable from the app.
7. **Audit is always reachable.** Every consequential action writes
   to the audit / proof ledger. The ledger is always one tap away
   from the home screen.
8. **Emergency stop is always reachable.** The interactive icon, in
   its alarm state, is reachable from every screen.
9. **Calm by default.** Push notifications fire only on state
   changes the owner must act on (approval pending, validation
   failed, emergency stop engaged, gateway lost). Routine progress
   stays in the dashboard, not the notification tray.
10. **Plain English.** Raw model output, stack traces, JSON dumps,
    and provider error blobs are folded behind a *Show details*
    affordance. The default view is plain language.
11. **Offline-aware.** The app degrades clearly when the gateway is
    unreachable: read views remain available from cache; writes go
    to a visible outbox; destructive actions are blocked, never
    silently queued.
12. **No silent fallback.** The app never swaps cloud STT, cloud
    LLMs, mock mode, or local handoff in for their alternatives
    without a visible banner and an owner-visible choice.

---

## 3. Product surface (what the app actually is)

MUSE is a **native Android control surface** for the
MUSE operating partner (running in the Hermes gateway
process — Python core, AOS Council, MUSE runtime, memory,
verification gates). The phone:

- **Watches** the operating partner's state (chat, tasks, approvals,
  memory, audit ledger, gateway / worker / hook health).
- **Submits** prompts and approval decisions through the gateway.
- **Launches and stops** the gateway when it runs co-located in
  Termux on the same phone.
- **Never silently mutates state.** Every destructive or publishing
  action is gated on an explicit, named, on-device confirmation.

The Python core, AOS Council routing, skill execution, memory
write-paths, scheduling, and verification gates all live on the
gateway side. The Android app is a thin client over the gateway's
HTTP + SSE surface and remains intentionally so.

### 3.1 Existing module → MUSE mapping

The current native module at [`apps/android/`](../apps/android/) is
the basis for MUSE. The transformation is in-place: no new
app module, no duplicate Gradle project, no package id change.

| Existing surface (`apps/android/`) | MUSE concept |
|---|---|
| `com.aci.hermes` package | Unchanged (compatibility). External name: **MUSE**. |
| `HermesApplication` | Unchanged class name. App label resource → **MUSE**. |
| `MainActivity` + `HermesNavGraph` | Hosts the new ten-screen MUSE nav graph. |
| `HermesService` (foreground service) | Becomes the **Operating Partner Service** — owns gateway probe, SSE subscriptions, outbox replay, emergency-stop signal, lock-screen widget feed. Class name kept for manifest compatibility; user-visible notification title is "MUSE — listening". |
| `HermesGatewayClient` (`/v1/health`, `/v1/chat`) | Becomes `JarvisGatewayClient`; wire format unchanged. SSE consumer extended to cover task / approval / memory / audit / control streams. |
| `HermesClientFactory` (Gateway · Mock) | Becomes `JarvisClientFactory` (Gateway · Mock · Termux-local). All three are runtime-selectable, never silently swapped. |
| `SettingsRepository` (DataStore + EncryptedSharedPreferences) | Unchanged storage shape. Adds MUSE-specific keys (driving mode, voice opt-in, memory verbosity, lock-screen widget). |
| `LogBuffer` (in-memory ring) | Becomes the **Diagnostics buffer** — feeds the new Diagnostics screen and the audit export. |
| Existing screens: splash, setup, provider, chat, status, settings, diagnostics | Re-mapped onto the new ten-screen spec (see §4 and `jarvis-prime-app-screen-map.md`). Orchestrator screens (`OrchestratorScreen`, `TaskDetailScreen`) are folded into **Tasks** and **Approvals**. Termux handoff (`TermuxIntentBridge`, `HandoffLauncher`) is preserved as the Termux gateway / local-handoff fallback. |

This is a **transformation**, not a fork. There must be exactly one
Android module in the repo. The acceptance check in §10 is "no
duplicate app module."

---

## 4. Required app screens (the ten)

Each of the ten required screens has its full component / state /
behavior specification in this section. For navigation, deep-link,
and component-inventory views, see
[`jarvis-prime-app-screen-map.md`](jarvis-prime-app-screen-map.md).

The interactive icon described in §5 is a global element that
appears on **every** screen below.

### 4.1 Onboarding

**Purpose.** Get the owner from a freshly installed app to a working,
trusted connection to MUSE — gateway URL, optional token,
provider key, mock vs. live, voice and permission choices — with no
required steps that block continuing in mock.

**Components.**

- Brand mark + tagline (*"Talk. Command. Approve. Stop."*).
- Five-step pager: Welcome · Connect · Choose mode · Voice & permissions · You're in.
- Connection card: gateway URL, optional bearer token (write-only),
  *Test connection* button with live status pill.
- Mode chooser: *Live gateway* (default if reachable) · *Termux on
  this phone* · *Mock mode*.
- Voice & permissions card: microphone, notifications, foreground
  service, optional Bluetooth (driving mode), optional widget pin.
  Each is **declinable** and each shows what is lost by declining.
- *Skip for now* affordance on every step after Welcome — never
  blocks entry into the app.

**Empty state.** First launch with no prior settings. Welcome card
front and center; *Get started* primary button; *Use mock mode and
look around* secondary button.

**Loading state.** *Testing connection…* spinner under the URL field
during a probe. The five-step pager is otherwise instant.

**Error state.** Each connection failure surfaces a named, plain-English
diagnosis (see §7 connection state model):

- **Wrong backend URL.** *"That URL only works inside the Android
  emulator. Enter your gateway's LAN or public address."*
- **Backend unreachable.** *"I can't reach MUSE at this URL.
  Check the gateway is running, then tap Test connection."*
- **Gateway token rejected.** *"The gateway rejected this token. Re-enter
  it or clear and continue without one."*
- **TLS error.** *"The gateway's certificate did not verify. Tap
  Details to see why."*

**Success state.** Green *Connected* pill, version + provider + model
echoed back from `/v1/health`. *Continue* primary button.

**Mobile behavior.** Pager is swipeable. Soft keyboard never overlaps
the primary action. *Test connection* lives in the bottom 25% of the
viewport at all times.

**Safety behavior.** Mock mode is allowed and *encouraged* for first
look; the app makes clear in a persistent banner that mock mode does
not reach a real gateway. Voice and notification permissions are
explained before being requested; both can be declined and revisited
later from Settings.

**Accessibility requirements.** All copy at minimum 16 sp, primary
actions at 64 dp tap targets, screen-reader labels on every step,
high-contrast mode honored, animation reduced when system "reduce
motion" is on.

**Gateway / offline behavior.** Onboarding works fully offline in
mock mode. Live and Termux modes show real-time reachability and do
not let the owner finish step 2 (*Connect*) without a successful
probe — but step 2 can be skipped, leaving the owner in mock mode
on the home screen with a banner.

The full step-by-step is in
[`jarvis-prime-app-onboarding-spec.md`](jarvis-prime-app-onboarding-spec.md).

### 4.2 MUSE Home

**Purpose.** The single screen the owner opens to know, in one
second: *MUSE is up · these are the active tasks · these
approvals are waiting on me · this is the last consequential thing
that happened.*

**Components.**

- **Status header.** Colored pill (Connected · Connecting · Degraded
  · Offline · Mock · Emergency-stopped), gateway label, current
  provider + model.
- **Interactive icon (large).** Big, central. Six visible states
  (see §5). Tap → chat. Long-press → voice. Double-tap → emergency
  stop (with confirm). Always shows current state.
- **Active tasks tile.** Top 3 active tasks, status badges,
  one-line summaries. Tap any → Tasks screen filtered to that task.
- **Approvals tile.** Count of pending approvals; if ≥ 1, a primary
  *Review approvals* CTA. Risky and critical approvals are color-
  and glyph-differentiated.
- **Last consequential action tile.** One-line plain-English
  summary of the most recent ledger entry classified as
  consequential (approval, publish, deploy, memory write, gateway
  start/stop).
- **Quick actions row.** *New chat · Voice · Memory · Audit ·
  Control · Diagnostics*.

**Empty state.** Fresh connection, no active tasks, no approvals.
*"MUSE is online and idle. Say something, or tap the mic."*

**Loading state.** Status pill shows *Connecting…*; tiles render
skeletons; the interactive icon is in its *thinking* state.

**Error state.** Status pill turns red (*Offline*) or amber
(*Degraded*). Tiles fall back to last-known cached values with a
*Last refreshed HH:MM* line. Writes are blocked at the source; the
owner sees no false success.

**Success state.** Green pill, populated tiles, icon in *ready* or
*listening*.

**Mobile behavior.** Pull-to-refresh re-probes the gateway. Bottom
sheet exposes secondary actions to keep the visible area calm.

**Safety behavior.** Emergency stop is reachable from Home in one
gesture (double-tap the icon) and one confirm. The home screen
never auto-dispatches anything.

**Accessibility requirements.** Pill announces state changes via
`AccessibilityEvent`; icon has a content description matching its
current state ("MUSE is ready", "MUSE is listening", "MUSE is
working", "MUSE is waiting for your approval", "MUSE is paused",
"MUSE is stopped"). All tiles are screen-reader-traversable in
priority order: status → approvals → tasks → last action.

**Gateway / offline behavior.** Cached tiles render with their
last-known data; a persistent banner reads *"Showing cached state —
last sync HH:MM"*; the icon enters its *paused* state; the *Voice*
quick action is dimmed and labelled *Voice (offline — capture
queued)*.

### 4.3 Chat

**Purpose.** The conversational surface with MUSE —
Companion, Strategy, Critic, Operator, Builder, and Mobile Voice
modes all route through this screen.

**Components.**

- **Header.** Mode chip (auto-routed; tappable to override), current
  thread title, *New chat* affordance.
- **Message list.** User and MUSE bubbles, streaming token deltas,
  inline tool / agent attributions (*"AOS Council · Principal
  Systems Architect"*).
- **Composer.** Multi-line input that expands to 70% viewport on
  focus; mic button on the right; *Send* primary button; *Abort*
  button while a stream is in flight.
- **Quick-task chip.** When MUSE proposes converting the
  conversation into a task, a *Convert to task* chip appears
  beneath the latest assistant bubble. Tapping it opens the Task
  draft sheet pre-filled.

**Empty state.** New thread: *"MUSE is listening. What's on your
mind?"* with a row of suggested first prompts (e.g. *"Audit
hermes-agent"*, *"What's the next move on MUSE?"*, *"Read
last night's PR feedback"*).

**Loading state.** Streaming dots in the latest assistant bubble;
*Abort* button visible.

**Error state.** Stream error renders as a red inline note under
the partial reply; the partial reply is preserved. Banner shows
*Stream interrupted — tap to retry*.

**Success state.** Final assistant bubble with the *done* event
recorded; reply is selectable, copyable, and (where applicable)
linked to a created Task.

**Mobile behavior.** Voice button is always reachable bottom-right.
Long-press voice button = push-to-talk capture; release =
transcribe + insert. Tap voice button = open Voice Capture screen
(driving mode style).

**Safety behavior.** Anything the owner says that MUSE
classifies as touching an Owner Gate (spend, deploy, publish,
OAuth, main-branch merge, package publish, credential change,
regulated claims) is **not executed from chat**; instead a *Risky
action proposed* card appears with a *Review in Approvals* CTA.
Chat never silently dispatches a destructive job.

**Accessibility requirements.** Streaming text is announced in
chunks (not character-by-character) for screen readers; *Abort*
has a screen-reader label that reads *"Stop MUSE"*; chat history
is keyboard-traversable.

**Gateway / offline behavior.** Outbound messages compose locally
and queue in the visible outbox; a banner reads *"Offline — messages
will send when MUSE is back"*. Voice capture works offline and
queues. No silent retry of writes once back online — the outbox is
visible and replayed only after the owner taps *Send queued*.

### 4.4 Tasks

**Purpose.** The list of work MUSE is doing, has queued, or
recently finished — research, audit, code, validation, publish,
deploy.

**Components.**

- **Filter chip row** (sticky): *all · running · waiting · done ·
  failed · cancelled*.
- **Task rows** (two-line): title + worker chip · status badge +
  relative time.
- **Swipe actions.** Right swipe = quick *Approve* (only when
  status is *waiting for approval*). Left swipe = *Cancel* (with
  confirm).
- **Tap row** → Task detail (sub-screen): plan, files affected,
  validation gate status, decision-ledger summary, *Open in
  Approvals* button when applicable.
- **New task FAB.** Opens a new draft (voice or text).

**Empty state.** *"No tasks yet. Ask MUSE to do something."* with
a *Start a task* primary button that opens Chat in Operator mode.

**Loading state.** Skeleton rows for the first page; thin progress
bar above the list during paginated fetches.

**Error state.** Failed task rows show a red glyph and a *View
why* affordance — tapping opens the audit ledger filtered to that
task. SSE drop turns the *live* pill amber (*Live updates paused —
reconnecting*) with a manual *Reconnect* in the overflow menu.

**Success state.** Newly finished tasks show a green check; tapping
opens the result summary in plain English with *Show details*
revealing the full diff / output.

**Mobile behavior.** Two-line rows are 64 dp tall to hit the
thumb-target rule. Filter chips collapse on scroll.

**Safety behavior.** *Cancel* is destructive enough to require a
confirm sheet but does not require Impact Report; *Approve* on a
risky or critical task **never** completes from the swipe path
alone — the swipe opens the Approvals screen for that task. The
swipe is a shortcut to the approval, not a one-tap approval.

**Accessibility requirements.** Each row's content description is
*"Task: <title>, worker <worker>, status <status>, <relative-time>"*.
Swipe shortcuts have keyboard equivalents in the overflow menu.

**Gateway / offline behavior.** The list renders from cache with a
*last-synced* banner; *Cancel* is blocked offline with the message
*"Cancel needs MUSE online — try again in a moment."*; *Approve*
is unconditionally blocked offline (see §4.5).

### 4.5 Approvals

**Purpose.** The owner gate. Every consequential action — risky,
serious, critical — passes through this screen and only this
screen. Nothing else in the app can complete a gated action.

**Components.**

- **Pending list.** One card per pending approval, ranked
  highest-impact first. Each card shows: title, classification
  (*Risky · Serious · Critical*), proposed action in plain
  English, files / endpoints affected, requested by (MUSE
  Prime · AOS Council · worker name), time pending.
- **Card actions.** *Review* opens the approval detail screen.
- **Approval detail.** Plan summary, unified diff (no side-by-side;
  too narrow), validation gate status (✅ / ❌ / ⏳ / ⚠️), Impact
  Report toggle. Bottom action bar: *Approve* (green, 64 dp) ·
  *Reject* (red, 64 dp) · *Approve with note* (overflow).
- **Two-step confirm.** *Approve* opens a confirm sheet showing the
  plain-English action one more time and the phrase the owner must
  match (*"Approve as authorized"* or its voice equivalent
  *"Yes, with authorization."*). Sheet has *Cancel* and *Confirm
  approval*.
- **Impact Report.** For Critical approvals, the Impact Report is
  mandatory before the confirm sheet — see §6.

**Empty state.** *"Nothing waiting on you. MUSE will ping when
it needs your call."*

**Loading state.** Skeleton cards; *Approve* / *Reject* buttons
disabled with a spinner while a write is in flight.

**Error state.** Stale state (HTTP 409) refreshes the screen
silently and re-asks for confirm; the original button never fires
twice. Approval write 5xx surfaces a banner with *Retry* and *Copy
decision payload* — never silently retries.

**Success state.** Approval card fades to a green completed state
and slides into the audit ledger; voice readback (if enabled) says
*"Approved <title>. Logged to audit."*

**Mobile behavior.** Diff is unified, monospace 14 sp, horizontal
scroll, no soft-wrap. The bottom action bar is sticky to the
viewport, not the document.

**Safety behavior.**

- **Risky** = one-step gate. Two-step confirm. Single approve.
- **Serious** = two-step gate. Step one (*"I understand the impact"*)
  opens an evidence card; step two (*"Approve as authorized"*) writes
  the decision. The two steps are separate sheets — no chained taps.
- **Critical** = two-step gate **plus** Impact Report. The Impact
  Report must be acknowledged before step one is enabled. See §6.
- Approvals are **disabled while emergency stop is engaged**. The
  card shows *"MUSE is in emergency stop — resume to approve."*

**Accessibility requirements.** Confirm phrases are voice-actionable.
Reject is a red 64 dp button, *not* a small text link. Diff
viewport is screen-reader-readable line by line with file path
context preserved.

**Gateway / offline behavior.** Approvals are **never completable
offline.** The screen renders the queued list from cache, but
*Approve* and *Reject* are dimmed with the message *"Approvals need
MUSE online — they live in the gateway's audit ledger."* This is
intentional: approval = a signed write to the ledger, and the
phone is not allowed to sign in the gateway's place.

### 4.6 Memory

**Purpose.** Inspect, correct, and delete the durable memory MUSE
Prime is using to make decisions. Implements the corrections policy
in [`memory-and-personality-policy.md`](memory-and-personality-policy.md).

**Components.**

- **Memory list.** Each row is one durable fact: short title,
  category (Preference · Decision · Mission · Lesson · Skill hint ·
  Environment fact), last-confirmed date, source (chat · voice ·
  manual · automatic inference).
- **Search & filter** by category and free text.
- **Row actions.** *Correct* opens an inline edit; *Delete* opens a
  confirm sheet; *Why is this here?* shows the originating message
  / event.
- **Add memory.** Manual *"Remember this:"* entry from the FAB.
- **Pending inferences.** A separate tile of *"Should I remember
  this?"* candidates MUSE has flagged from recent conversation;
  each candidate has *Confirm* and *Reject*.

**Empty state.** *"MUSE hasn't saved anything durable yet. Once
you make decisions, set preferences, or call out a mistake, they
show up here."*

**Loading state.** Skeleton rows; pending-inferences tile shows a
small spinner.

**Error state.** A failed write (correct, delete, add) surfaces a
banner with *Retry*; the previous value is restored in the UI until
the write succeeds.

**Success state.** Edited row briefly flashes green; deleted row
slides out and a *Undo* snackbar appears for 5 s. Added row appears
at the top of the list, flashed green.

**Mobile behavior.** Inline edit avoids opening a new screen for
short edits. Long-press a row → bulk-select mode for batch delete.

**Safety behavior.**

- **Memory writes are gated by classification.** Anything classified
  as *secret-shaped* (looks like a token, key, password) is
  refused at the gateway. The app surfaces the refusal as a red
  inline note; nothing is stored.
- **Delete is one-step.** This is intentional — memory should be
  easy to remove. Undo is provided.
- **Stale memory.** Memory facts older than the policy threshold
  (configurable; default 180 days) carry a *Re-confirm?* badge.

**Accessibility requirements.** Edit field announces character count;
each row's content description includes category and date for screen
readers.

**Gateway / offline behavior.** Memory list renders from cache
offline; *Correct*, *Delete*, *Add*, *Confirm inference*, and
*Reject inference* all queue in the visible outbox. The outbox is
read-only until the owner taps *Send queued* once MUSE is back —
this is the same no-silent-replay rule that applies to Chat.

### 4.7 Audit / Proof

**Purpose.** The append-only, time-ordered ledger of consequential
actions MUSE, the AOS Council, the workers, and the gateway
have taken. The owner's record.

**Components.**

- **Ledger timeline.** Each entry: timestamp · actor (MUSE · AOS
  · worker · gateway · hook · owner) · action · classification
  (info · decision · approval · publish · deploy · memory · stop)
  · one-line plain-English summary · *Show details*.
- **Filter chips.** *All · approvals · decisions · publishes ·
  deploys · memory · stops · errors*.
- **Date range** picker (defaults to *last 7 days*).
- **Detail view.** Full structured entry: rationale, files / endpoints
  affected, link to originating task, link to the Approval card if
  the action was gated, link to memory facts referenced.
- **Export.** *Copy entry as text* and *Export filtered range as
  JSONL*.

**Empty state.** *"No audit entries yet. Approvals, publishes,
deploys, and memory changes will appear here."*

**Loading state.** Skeleton timeline; *Loading more…* shimmer at
the bottom on paginated fetch.

**Error state.** Ledger read 5xx → banner *"Audit ledger
unreachable — showing local cache up to HH:MM"*. The local cache is
clearly labelled as such.

**Success state.** Timeline renders with stable IDs so deep links
from approvals / tasks / memory always resolve.

**Mobile behavior.** Timeline supports infinite scroll with a
sticky day separator. *Copy entry as text* is a one-tap, screen-reader-
friendly action.

**Safety behavior.** The ledger is **read-only from the app**. The
app cannot edit or delete a ledger entry. Owner annotations
(*"context: this was during the outage"*) are added as **new** ledger
entries linked to the original, never as edits.

**Accessibility requirements.** Each entry's content description is
*"<actor> <action>, <classification>, <relative-time>. Tap to expand."*
Day separators are announced as headings.

**Gateway / offline behavior.** Renders the local cache offline
with a banner. *Export filtered range* works offline against the
cache. Owner annotations queue in the outbox.

### 4.8 Control

**Purpose.** The owner's hardware-style control surface for MUSE
Prime itself: emergency stop, resume, mode override, voice mode,
driving mode, mock toggle, and gateway lifecycle (when Termux is
present on the same phone).

**Components.**

- **Emergency stop tile** (top, big, red). Single-tap arms; a
  confirm sheet completes the stop. Once engaged: tile turns
  *Stopped*, all approvals are disabled across the app, the
  interactive icon enters its *stopped* state on every screen,
  and a persistent banner appears app-wide.
- **Resume tile** (visible only when stopped). Single-tap arms; a
  confirm sheet completes the resume, requiring a typed or spoken
  *"Resume MUSE"* confirmation.
- **Mode override.** *Auto · Companion · Strategy · Critic ·
  Operator · Builder · Mobile Voice*. Default *Auto* lets MUSE
  pick; manual override pins the next response.
- **Voice mode.** *Off · Push-to-talk · Continuous hands-free ·
  Driving mode.* Each option clearly states what is captured and
  when.
- **Mock mode.** *Off · On.* A persistent banner appears app-wide
  when on.
- **Gateway lifecycle (Termux-only).** When the app detects Termux
  on the device, exposes *Start Termux gateway* / *Stop Termux
  gateway* with status read from Termux IPC (see §7.4 and
  [`docs/android/termux-intent-bridge.md`](android/termux-intent-bridge.md)).
- **Resume after emergency stop** runs an automatic *self-check*
  (see §6.4) before flipping the icon back to ready.

**Empty state.** Not applicable — Control always has a current
state.

**Loading state.** Tiles render their current state immediately;
state-changing actions show inline spinners during writes.

**Error state.** Emergency stop write failure is a special case:
the local app immediately enters a *stopped* state on the device
side (no approvals, icon stopped), surfaces *"MUSE didn't
acknowledge — retrying"*, and keeps retrying the gateway-side stop
on backoff. The local stop is **never** rolled back; only resume
can clear it.

**Success state.** Emergency stop transitions the whole app to the
stopped visual state within 1 s. Resume requires the owner to
read or speak the confirmation phrase.

**Mobile behavior.** Emergency stop and Resume are both 64 dp,
high-contrast, and the *only* destructive controls on this screen.
Other toggles use standard switches.

**Safety behavior.**

- The emergency stop button is **always reachable from every
  screen** via the interactive icon's double-tap (with confirm)
  even before reaching this screen.
- Resume is **never automatic**. There is no timer-based resume.
- Mock toggle off → on shows a banner; on → off shows a confirm
  sheet (*"Switching to live — MUSE will start using your real
  gateway. Continue?"*).
- Starting a Termux gateway is **not** an owner-gate but does
  surface a *"Starting MUSE on this phone — log:" affordance*
  during boot.

**Accessibility requirements.** Emergency stop announces *"MUSE
stopped"* through `TYPE_ANNOUNCEMENT`; resume announces *"MUSE
resumed"*. Voice mode toggles each speak their new state aloud when
voice readback is on.

**Gateway / offline behavior.** Emergency stop **works offline** —
the device-side stop takes effect immediately and is reconciled
with the gateway as soon as it returns. Resume **requires the
gateway online** so the self-check can run. Mode overrides queue
offline.

### 4.9 Settings

**Purpose.** Owner-controlled configuration for connection, voice,
notifications, memory, audit, lock-screen widget, theme, behavior,
and reset.

**Components (collapsible sections).**

- **Connection.** Gateway URL · bearer token (write-only with
  obscured placeholder) · *Test connection* · *Mock mode* shortcut.
- **Provider & model.** Provider chip row · API key field
  (write-only) · *Default provider* selector. Provider keys are
  forwarded in headers, never stored on the gateway.
- **Backend secrets (read-only).** List of secret IDs the gateway
  has registered (e.g. `github.pat`, `supabase.service_role`,
  `vercel.token`); each row is a glyph + ID + last-rotated date.
  Tapping a row shows *"This secret lives on the gateway. Edit it
  on the host running MUSE."* The app cannot edit them.
- **Voice.** STT engine (*on-device default* · *cloud opt-in*),
  TTS confirmation on/off, push-to-talk button mapping, wake-word
  on/off, driving-mode auto-enter (Bluetooth A2DP heuristic).
- **Notifications.** Toggle for each notification class: approval
  pending · validation failed · emergency stop · gateway lost ·
  daily summary. Routine progress notifications are disabled
  by default and cannot be enabled (calm-by-default rule).
- **Memory.** Verbosity (*concise · standard · verbose* — controls
  how often MUSE surfaces *Should I remember this?* candidates),
  stale threshold, *Export memory* (JSONL), *Clear memory* (writes
  a confirm-phrase gate; logs the deletion in audit).
- **Audit.** Default date range, *Export audit (JSONL)*, *Pin audit
  to lock-screen widget*.
- **Lock-screen widget.** Toggle pinned widget; choose layout
  (status only / status + next approval).
- **Theme.** *System · Light · Dark · High contrast.*
- **Behavior.** Auto-subscribe to live updates on new tasks,
  always show *Show details* on assistant replies, show plain-English
  *why* expansions, confirm before switching modes.
- **About.** Build number, gateway version (from `/v1/health`),
  cleartext-allowed badge, links to product docs.
- **Reset.** *Clear secrets only · Clear settings (keep secrets) ·
  Clear everything (full reset)* — each behind a confirm sheet.

**Empty state.** Not applicable — Settings always has current
values.

**Loading state.** Fields render their current values immediately;
write actions show inline spinners.

**Error state.** Connection test failures surface the same named
diagnoses as Onboarding. Token / key writes that fail surface
inline errors; the previous value is restored.

**Success state.** Changes are saved-as-you-go for non-secret
prefs; secret writes show a *Saved* check.

**Mobile behavior.** Sections collapse to keep the surface
scannable. Search field at the top jumps to any setting by name.

**Safety behavior.** Tokens and provider keys are write-only fields
in the UI; the actual values cannot be read back. *Clear everything*
requires typing the word *RESET* and the audit ledger gets a final
entry before clearing.

**Accessibility requirements.** Every section is a labelled
heading; toggles read their current state to screen readers.

**Gateway / offline behavior.** Settings is fully functional offline
for local prefs (theme, voice, notifications, lock-screen widget).
Connection test, gateway-version display, and backend-secret listing
require the gateway online and show *"Showing cached state — last
sync HH:MM"* otherwise.

### 4.10 Diagnostics

**Purpose.** The owner's debug surface: connection state, app
version, build type, mode, mock state, in-memory log buffer, last
errors, and a one-tap *Export diagnostics bundle* for support.

**Components.**

- **Connection card.** Live `ConnectionState` (see §7), last probe
  latency, last probe outcome, gateway `/v1/health` echo.
- **Build card.** App version, build type (debug / release), build
  fingerprint, base gateway URL (compile-time + runtime override),
  cleartext-allowed flag, Termux detected (yes / no).
- **Mode card.** Mock on/off, voice mode, driving mode, current
  MUSE mode override.
- **Log buffer.** In-memory ring (the existing `LogBuffer`), most
  recent first; filter by level (info / warn / error) and source
  (gateway / app / service / voice / outbox).
- **Last errors.** Top 5 most recent errors with timestamps and
  *Copy* buttons.
- **Export diagnostics bundle.** Bundles logs + connection state +
  build info into a sharable file (no secrets, no tokens, no memory
  contents).

**Empty state.** *"Logs will appear here as MUSE works."* —
realistically rare to see, since the app emits boot logs.

**Loading state.** Connection card shows *Probing…* during a probe;
log buffer updates live.

**Error state.** Diagnostics is the place errors *go*, so the
"error state" is just a populated log buffer. Anything Diagnostics
itself fails to render (e.g. log buffer overflow) shows an inline
banner *"Log buffer truncated — newest entries preserved."*

**Success state.** All cards populated; *Export diagnostics bundle*
produces a file in under 2 s.

**Mobile behavior.** Long logs are horizontally scrollable, never
truncated silently. *Copy* buttons sit at the row level.

**Safety behavior.** The export bundle is **scrubbed**: no tokens,
no API keys, no memory contents, no audit entries. The bundle is a
support artifact, not an exfil vector.

**Accessibility requirements.** Log lines have content descriptions
*"<level> <timestamp> <source>: <message>"*. Screen reader can
traverse the buffer chronologically or by error.

**Gateway / offline behavior.** Fully functional offline — the
in-memory log buffer is local. Connection card is the one piece
that needs the gateway; it shows the last-known state otherwise.

---

## 5. The interactive icon (always-on app surface)

MUSE carries a single, persistent interactive icon — both
inside the app (on every screen) and on the lock-screen widget. It
is the owner's at-a-glance signal and the always-reachable hot
button.

### 5.1 States (six)

| State | Visual | Meaning |
|---|---|---|
| **Ready** | Steady glow, calm color | Connected, idle. Tap to chat. |
| **Listening** | Pulsing, voice color | Microphone is live (voice capture or driving mode). |
| **Thinking** | Slow rotating glyph | A stream is in flight or a worker is running. |
| **Waiting on you** | Bright, attention color | At least one approval is pending. |
| **Paused** | Dimmed, gray | Gateway offline / connecting. No writes possible. |
| **Stopped** | Red bar across, distinct shape | Emergency stop engaged. No writes possible. Approvals disabled. |

The states are **mutually exclusive** — exactly one is shown.
Priority on conflict: Stopped > Waiting on you > Thinking >
Listening > Paused > Ready.

### 5.2 Gestures

| Gesture | Action |
|---|---|
| **Single tap** | Opens Chat (or returns to Chat if already there). |
| **Long press** | Opens Voice Capture / driving-mode UI. |
| **Double tap** | Triggers Emergency stop confirm sheet. From any screen. |
| **Swipe up** | Opens the Approvals screen when in *Waiting on you*; opens Tasks otherwise. |
| **Swipe down** | Opens Audit / Proof. |

Gestures are **identical on every screen**. The icon is the
constant — its location may differ (Home: large; other screens:
bottom-right floating). Its behavior does not.

### 5.3 Accessibility

- Each state has a unique content description (see §4.2).
- Each gesture has a keyboard / talkback equivalent in the overflow
  menu of the host screen.
- The icon respects "reduce motion" — the *Thinking* rotation
  becomes a static glyph; the *Listening* pulse becomes a steady
  fill.

### 5.4 Lock-screen widget

A 2×2 widget mirroring the icon's current state, plus a one-line
text:

- Ready: *"MUSE is ready."*
- Listening: *"MUSE is listening."*
- Thinking: *"MUSE is working: <task title>."*
- Waiting on you: *"MUSE needs you: <approval title>."*
- Paused: *"MUSE is offline — last sync HH:MM."*
- Stopped: *"MUSE is stopped. Tap to resume."*

Tapping the widget jumps to the right screen:

| State | Widget tap target |
|---|---|
| Ready | Chat |
| Listening | Voice Capture |
| Thinking | Tasks |
| Waiting on you | Approvals |
| Paused | Diagnostics |
| Stopped | Control |

---

## 6. Approval system (the owner gate)

### 6.1 Classification

| Class | Examples | UI gate |
|---|---|---|
| **Risky** | Run a non-mutating audit; read a private repo; download a public artifact; cancel a running task. | One-step confirm. |
| **Serious** | Open a draft PR; write durable memory; install a new skill; change a default model; switch a profile. | Two-step confirm. |
| **Critical** | Spend money; deploy; publish; OAuth or credential change; main-branch merge; package publish; DNS change; regulated claim. | Two-step confirm **plus** Impact Report. |

Classification comes from the gateway. The app does not invent
classes. If the gateway returns a class the app does not know, the
app treats it as **Critical** and refuses to fall through.

### 6.2 Confirm phrases

- One-step: *"Approve"* / *"Reject"* tap, or spoken *"Approve"* /
  *"Reject"* in voice mode.
- Two-step: step one *"I understand the impact"*; step two
  *"Approve as authorized"*, or spoken *"Yes, with authorization."*
- Two-step + Impact Report: same as two-step, plus the Impact
  Report must be visibly acknowledged (scrolled to bottom and
  *Acknowledged* tapped) before step one is enabled.

The literal voice phrase *"Yes, with authorization."* matches the
MUSE owner-gate phrase already established in
[`jarvis-prime-operating-system.md`](jarvis-prime-operating-system.md).

### 6.3 Impact Report (critical only)

The Impact Report is mandatory for Critical actions. It is
generated server-side and rendered as:

- **What changes** — plain-English summary of the actual mutation
  (files, endpoints, repos, accounts, dollars).
- **Who sees it** — public / private / internal / paid recipients.
- **What can break** — top three failure modes the gateway
  identifies.
- **Rollback** — concrete revert path (commit hash, deploy id, etc).
- **Why now** — the chain of reasoning from the originating prompt
  to this action.

If the gateway cannot produce all five sections, the Impact Report
shows the missing sections as *"MUSE could not produce this
section."* The owner is free to reject on that basis.

### 6.4 Emergency stop self-check (resume)

Resume after emergency stop runs the gateway's resume self-check
(`/v1/control/resume?dry_run=true`) before flipping the icon back
to *Ready*. The self-check reports:

- gateway health,
- worker queue depth (zeroed during stop),
- last action before the stop,
- any approvals that were pending at stop time and need re-review.

The resume confirm sheet shows the self-check result and requires
the owner to read or speak *"Resume MUSE."*

### 6.5 Audit trail (every approval)

Every approval (and every rejection) writes one ledger entry
classified as `approval`. The entry includes:

- approval id, classification, action summary,
- decision (approved / rejected / approved-with-note),
- confirm-phrase mode (tap / voice),
- whether Impact Report was shown and acknowledged,
- the requestor (MUSE, AOS Council member, worker name),
- the originating prompt / task / chat thread id,
- timestamp and device fingerprint.

Audit entries are append-only; rejections do not delete the
proposal — they keep both the proposal and the rejection.

---

## 7. Connection, modes, and offline behavior

### 7.1 Connection state model (unchanged from Hermes module)

The existing `ConnectionState` carries forward verbatim — it is
already correct for MUSE:

| State | Meaning | UI |
|---|---|---|
| `Unknown` | Not probed | Pill: muted, *"Connecting…"* |
| `Connecting` | Probe in flight | Pill: amber, *"Connecting…"* |
| `Connected(status)` | Probe ok | Pill: green, *"Connected · <provider> · <model>"* |
| `Failed(reason, kind)` | Probe failed | Pill: red, named reason |

`kind ∈ {UNREACHABLE, WRONG_URL, TLS, HTTP, UNKNOWN}` drives the
plain-English error rendering everywhere in the app.

### 7.2 Three modes (mutually exclusive, never silently swapped)

1. **Live gateway.** App talks to a remote or LAN gateway over
   HTTP / SSE. Default for first-class use.
2. **Mock mode.** App streams canned responses locally. No
   network. Persistent banner across the app while on. Used for
   UI exploration, demos, and onboarding.
3. **Termux on-device.** Gateway runs in Termux on the same phone
   under loopback (`http://127.0.0.1:8080`). The Control screen
   exposes lifecycle (start / stop). See
   [`docs/android/termux-intent-bridge.md`](android/termux-intent-bridge.md).

The owner switches modes from Onboarding (first time), Settings →
Connection, or Control → Mock toggle. The app never falls back
silently between modes.

### 7.3 Outbox (writes while offline)

Every write the owner initiates while offline goes into a visible
outbox:

- Chat messages.
- Voice captures (audio + transcript).
- Memory writes (correct, delete, add, confirm / reject inference).
- Task drafts.
- Audit annotations.

The outbox is **visible** on a top-bar badge and on the relevant
screens. It is **not** replayed silently — the owner taps *Send
queued* to release the outbox once MUSE is back. The exceptions
are:

- **Approvals never queue.** Approvals are blocked offline.
- **Emergency stop never queues.** Emergency stop takes local
  effect immediately and reconciles with the gateway when it
  returns.

### 7.4 Termux gateway lifecycle

When the app detects Termux:

- Control exposes *Start Termux gateway* and *Stop Termux gateway*
  buttons.
- *Start* sends an Intent (see `TermuxIntentBridge`) that runs the
  `hermes gateway start` command in Termux's sandbox.
- Boot status is shown live with the in-process log buffer feeding
  the Control screen's *Termux log* affordance.
- The app considers the Termux gateway "ready" only after a
  successful `/v1/health` against `http://127.0.0.1:8080`.

The Termux integration is the same `TermuxIntentBridge` already in
the module today; the user-visible language is MUSE.

---

## 8. Memory, audit, and emergency stop (the three trust anchors)

The product promise rests on these three being *visibly trustworthy*
from the phone.

### 8.1 Memory — owner-correctable

- Every durable memory fact is visible on the Memory screen.
- Every fact can be corrected, deleted, or re-confirmed in two taps.
- Inferred memory candidates are surfaced explicitly as *"Should I
  remember this?"* — never written silently.
- Secret-shaped content is refused at the gateway and surfaced in
  the app as a rejection.

### 8.2 Audit — always reachable

- The Audit / Proof screen is one tap from Home.
- Every consequential action writes an entry.
- The ledger is read-only from the app.
- The lock-screen widget can be pinned to *"audit summary"* mode
  so the most recent consequential action is glanceable without
  unlocking the device.

### 8.3 Emergency stop — always reachable, never automatic to resume

- Reachable from every screen via the interactive icon's double-tap.
- Reachable via long-press the lock-screen widget.
- Reachable via the voice phrase *"MUSE, stop everything."*
- The device-side stop takes effect immediately, even offline.
- Resume requires the owner to explicitly confirm and runs a
  gateway self-check first. There is no timed auto-resume.

---

## 9. Accessibility, internationalization, performance

### 9.1 Accessibility

- Minimum text size: 16 sp body, 14 sp metadata.
- Minimum tap target: 48 dp standard, 64 dp destructive.
- Contrast: WCAG AA across all themes; high-contrast theme available.
- Screen reader: every interactive element has a content description
  in plain language (no "btn_approve").
- Reduce motion: respected for icon animations and screen
  transitions.
- TalkBack confirmation: destructive actions are double-confirmed
  through TalkBack's own gesture pattern, not bypassed by it.

### 9.2 Internationalization

- All user-visible strings live in `res/values/strings.xml` and are
  marked translatable.
- Voice grammar is locale-aware; the literal phrase *"Yes, with
  authorization."* is preserved in English as the canonical owner-
  gate phrase and additionally translated to the owner's locale
  with both accepted.
- Number, date, and time formats follow the device locale.

### 9.3 Performance

- Cold start to Home (with valid cached settings): ≤ 1.5 s on a
  mid-range device.
- Home tile first paint: ≤ 1.0 s with cached state.
- Chat first-byte (delta) on streaming reply: ≤ 2.0 s on a healthy
  gateway.
- Approval write latency: ≤ 2.0 s end-to-end on a healthy gateway.
- Voice capture transcript-to-screen: ≤ 1.0 s on-device.
- Emergency stop local effect: ≤ 200 ms.

---

## 10. Acceptance checks

The MUSE app build passes acceptance when *all* of the
following hold.

1. **App spec matches existing `apps/android`.** Every screen in §4
   maps to existing or renamed files under
   `apps/android/app/src/main/java/com/aci/hermes/ui/screens/` and
   no other Android module exists in the repo.
2. **No duplicate app module.** `settings.gradle.kts` declares
   exactly one app module (`:app`). No parallel `apps/jarvis-prime/`
   or `apps/android-jarvis/` directory exists.
3. **All prior research translated.** Every concept previously
   surfaced as "Hermes cockpit" (prompt command center, worker
   dashboard, decision ledger, validation gate, GitHub publisher,
   deploy planner, voice capture, driving mode, lock-screen widget,
   logs / events) is folded into one of the ten MUSE
   screens or one of the three trust anchors (memory, audit,
   emergency stop). No legacy "cockpit" name appears in user-visible
   strings.
4. **Mobile-first behavior explicit.** The §2 operating principles
   are reflected in every screen's spec in §4: glanceable,
   status-first, one-thumb, voice-equivalent, calm by default.
5. **Approval system explicit.** Classes (Risky · Serious ·
   Critical), confirm phrases, Impact Report contents, audit
   payload, and offline behavior are all defined in §6 and
   referenced from §4.5.
6. **Icon behavior explicit.** Six states, five gestures, lock-
   screen widget mapping, and accessibility behavior are defined
   in §5 and referenced from every screen in §4.
7. **Memory / audit / emergency stop explicit.** §4.6, §4.7, §4.8,
   and §8 define each in full; the home screen and every other
   screen reach them in one tap.
8. **Externally MUSE; internally legacy compatibility
   preserved.** The package id `com.aci.hermes`, the gateway path
   `/v1/*`, the `HermesService` class, and the `HermesGatewayClient`
   identifier are unchanged. No user-visible string says "Hermes".
9. **Mock mode and Termux gateway mode** are reachable, banner-
   indicated when active, and never silently activated.
10. **Companion docs exist and cross-link.** The four companion docs
    listed at the top of this file all exist in `docs/` and
    cross-link to this spec and to each other.

---

## 11. Cross-references

- [`jarvis-prime-app-user-flows.md`](jarvis-prime-app-user-flows.md)
  — twenty primary user flows.
- [`jarvis-prime-app-screen-map.md`](jarvis-prime-app-screen-map.md)
  — navigation, deep links, route table, component inventory per
  screen.
- [`jarvis-prime-app-onboarding-spec.md`](jarvis-prime-app-onboarding-spec.md)
  — the five-step onboarding pager spec.
- [`jarvis-prime-app-launch-standard.md`](jarvis-prime-app-launch-standard.md)
  — release readiness, app store metadata, and the launch checklist.
- [`jarvis-prime-operating-system.md`](jarvis-prime-operating-system.md)
  — the runtime identity and modes MUSE in this app
  surfaces.
- [`jarvis-verification-gates.md`](jarvis-verification-gates.md)
  — the eight verification gates the gateway enforces, surfaced
  on the Validation portion of the approval detail screen.
- [`memory-and-personality-policy.md`](memory-and-personality-policy.md)
  — the policy the Memory screen enforces visually.
- [`apps/android/README.md`](../apps/android/README.md)
  — current Hermes module README; remains accurate as the
  technical compatibility layer.
- [`apps/android/docs/ARCHITECTURE.md`](../apps/android/docs/ARCHITECTURE.md)
  — Android module architecture; unchanged.
