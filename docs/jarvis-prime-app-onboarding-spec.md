# muse — Android App Onboarding Specification

> **Status:** product spec, v1. Companion to
> [`jarvis-prime-app-product-spec.md`](jarvis-prime-app-product-spec.md),
> [`jarvis-prime-app-user-flows.md`](jarvis-prime-app-user-flows.md),
> [`jarvis-prime-app-screen-map.md`](jarvis-prime-app-screen-map.md),
> [`jarvis-prime-app-launch-standard.md`](jarvis-prime-app-launch-standard.md).
>
> Five-step onboarding pager that takes the owner from a fresh
> install to a usable, trusted muse — Connect (real
> gateway), Termux on this phone, or Mock. No required step blocks
> entry into the app.

---

## Goals (the only ones)

1. **Get the owner to the Home screen in under 90 seconds**
   if they have a gateway URL ready.
2. **Get the owner to a usable Mock-mode Home screen in under
   30 seconds** if they don't.
3. **Set up muse's identity** — the owner knows what
   *talk · command · approve · monitor · remember · verify · stop*
   means, and which of those needs which permission.
4. **No silent fallbacks.** Every choice the owner makes is
   visible — gateway URL, mode, permissions, voice opt-ins.
5. **Every step is skippable** from step 2 onward. Skipping always
   lands the owner in a working state (Mock) with a banner saying
   so.

## Non-goals

- Onboarding is **not** a marketing tour. No animated explainer of
  every feature.
- Onboarding does **not** demand the owner pick a provider, a
  model, a memory verbosity, a theme, or any other tweakable
  default. Those live in Settings.
- Onboarding does **not** dispatch any tasks, write any memory, or
  make any approval. Read-only health probes are the only
  outbound writes during onboarding.

---

## Pager structure

Five steps. Each step is a full-screen card with a swipe-pager
underneath, a *Skip* affordance from step 2 onward, and a primary
action in the bottom 25%.

```
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ 1. Welcome           │  │ 2. Connect           │  │ 3. Choose mode       │
│ Brand · tagline      │  │ URL · token · test   │  │ Live · Termux · Mock │
│ [Get started]        │  │ [Test connection]    │  │ [Continue]           │
│ [Use mock and look]  │  │ Skip →               │  │ Skip →               │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐
│ 4. Voice & perms     │  │ 5. You're in         │
│ Mic · notif · fg     │  │ Quick tour ·         │
│ · BT · widget        │  │ icon · approvals     │
│ [Allow each]         │  │ · stop               │
│ Skip →               │  │ [Open muse]        │
└──────────────────────┘  └──────────────────────┘
```

The pager dot indicator sits in the top right of the top bar
(not at the bottom — the bottom 25% is reserved for the primary
action).

---

## Step 1 — Welcome

**Purpose.** Set the product identity in one screen. Make the
owner feel like this is *their* operating partner, not a tour.

**Components.**

- **Brand mark.** *muse* Centered.
- **Tagline.** *"Talk. Command. Approve. Stop."*
- **Body copy (3 short lines).**
  - *"A mobile-first AI operating partner."*
  - *"Built for you to stay in control."*
  - *"Set up takes less than a minute."*
- **Primary action.** *Get started* — advances to step 2.
- **Secondary action.** *Use mock mode and look around* — sets
  mock-mode on, marks onboarding complete, lands on Home with the
  mock banner.

**Empty / loading / error states.** Not applicable — fully static.

**Mobile behavior.** Both actions are 64 dp tall, stacked
vertically, primary on top.

**Safety.** No outbound writes from this step.

**Accessibility.** Tagline and body copy are announced once on
focus. Both actions have plain-language content descriptions
(*"Continue to set up muse"* / *"Open muse in mock mode without
connecting"*).

**Offline.** Fully functional — no network needed.

---

## Step 2 — Connect

**Purpose.** Get a real connection to a muse gateway, or
skip to mock.

**Components.**

- **Gateway URL field.** Default seeded from
  `BuildConfig.DEFAULT_GATEWAY_URL` (which is `$HERMES_GATEWAY_URL`,
  `$ANDROID_API_BASE_URL`, or the debug-only `http://10.0.2.2:8080`
  fallback). The seed is shown grayed; the moment the owner touches
  the field, the seed is replaced.
- **Gateway token field** (optional, write-only with obscured
  placeholder).
- **Provider chip row** (optional — default *OpenRouter*; can be
  skipped and set later in Settings).
- **API key field** (optional, write-only) — only shown if the
  owner expands *Provider & API key (optional)*.
- **Test connection** button. Probes `/v1/health` with the short-
  timeout client (5 s connect, 8 s call). Renders a live status
  pill below the button.
- **Status pill** — the same `ConnectionStatePill` from the shell.
- **Primary action.** *Save & continue* — enabled only when a
  successful `/v1/health` returns within the session, or if the
  owner taps *Skip*.
- **Skip.** *Skip — I'll set this up later* — sets mock-mode on,
  advances to step 3 with the *Mock* mode preselected.

**Empty state.** Fields blank with the seed value visible (or
empty in release builds).

**Loading state.** *Testing connection…* spinner inside the *Test
connection* button; status pill shows *Connecting…*.

**Error state.** Plain-English error rendered under the status
pill, mapped from the existing `Failed.kind`:

| `kind` | Owner message | Suggested fix link |
|---|---|---|
| `UNREACHABLE` | *"I can't reach muse at this URL. Check the gateway is running, then tap Test connection."* | *Open setup help* (links to docs) |
| `WRONG_URL` | *"That URL only works inside the Android emulator. Enter your gateway's LAN or public address."* | *Open setup help* |
| `TLS` | *"The gateway's certificate did not verify. Tap Details to see why."* | *Open setup help* |
| `HTTP` (401) | *"The gateway rejected this token. Re-enter it or clear and continue without one."* | (inline) |
| `HTTP` (other) | *"The gateway returned HTTP <code>. Tap Details to see the response."* | *Open setup help* |
| `UNKNOWN` | *"Something went wrong reaching the gateway. Tap Details for the technical reason."* | *Open setup help* |

**Success state.** Green status pill: *"Connected · <version> ·
<provider> · <model>"*. *Save & continue* enabled.

**Mobile behavior.** Soft keyboard never overlaps *Test connection*
or *Save & continue*. The keyboard's *Done* action triggers *Test
connection* when the URL field is focused.

**Safety.** This step's only network call is `/v1/health`. No
writes. Tokens entered here go into EncryptedSharedPreferences
only on *Save & continue* — not on *Test connection*.

**Accessibility.** Each field is labelled; the URL field has an
*"example: https://your-gateway.example.com"* hint that is
announced once. The status pill announces its state every time it
changes.

**Offline.** Allowed. *Test connection* will fail with `UNREACHABLE`
and the owner can still tap *Skip* to fall through to step 3 with
mock preselected.

---

## Step 3 — Choose mode

**Purpose.** Make the mode choice an explicit, visible decision.
No mode is silently picked.

**Components.**

- **Mode cards** (one tappable card each, mutually exclusive
  radio behavior):

  **Live gateway** (default if step 2 connected successfully)
  - Subtitle: *"Talk to muse running on a server or remote
    machine."*
  - Body: *"All conversation, tasks, approvals, memory, and audit
    live on the gateway. Best for full-power use."*
  - Status row: green pill if step 2 connected; gray if not.

  **Termux on this phone** (visible only if Termux is detected on
  the device)
  - Subtitle: *"Run muse inside Termux on this phone."*
  - Body: *"The gateway runs on your phone. Loopback only. No
    internet required."*
  - Status row: detected / not detected; *Start Termux gateway* if
    detected and not running.

  **Mock mode**
  - Subtitle: *"Look around without connecting."*
  - Body: *"Streams canned responses locally. Approvals, tasks, and
    memory are demo data. Switch later from Settings."*
  - Status row: always available.

- **Primary action.** *Continue* — advances to step 4.
- **Skip.** *Skip — I'll choose later* — defaults to Live if
  step 2 connected, otherwise Mock.

**Empty state.** Not applicable — at least Mock is always present.

**Loading state.** When Live is selected, the screen re-probes
`/v1/health` to ensure the saved URL is still reachable; spinner
under the Live card.

**Error state.** If Live re-probe fails on this step, the card
shows the same plain-English error from step 2; the owner can pick
another mode or go back to step 2 to fix the URL.

**Success state.** Selected card has a distinct highlight; mode
preference is written on *Continue*.

**Mobile behavior.** Cards are vertically stacked and tap-target
sized (≥ 64 dp tall).

**Safety.** Mock requires an extra acknowledgement — selecting
Mock and tapping *Continue* shows an inline note: *"Mock mode is on
— muse will not connect to a real gateway. You can switch in
Settings or Control."*

**Accessibility.** Each mode card has a content description that
includes the body copy, not just the title. Selection state is
announced (*"Selected: Live gateway"*).

**Offline.** Mock is always offered. Termux is offered if detected
(no internet needed). Live is offered with the "unreachable"
status; the owner can still complete onboarding in Live mode and
will see the offline banner on Home.

---

## Step 4 — Voice & permissions

**Purpose.** Ask, **with context**, for the permissions muse
Prime can use, and let the owner decline each one without breaking
the rest of the app.

**Components.**

- **Permission list.** Five rows, each tappable:

  1. **Microphone.**
     - *Why:* voice capture, push-to-talk, driving mode.
     - *If you decline:* all voice features stay off. You can fix
       it later in Settings → Voice.
     - Action: *Allow microphone* / *Skip*.

  2. **Notifications.**
     - *Why:* approval pending, validation failed, emergency stop
       engaged, gateway lost. Calm by default — no routine progress
       spam.
     - *If you decline:* you must open the app to see these.
     - Action: *Allow notifications* / *Skip*.

  3. **Foreground service.**
     - *Why:* keeps the gateway connection alive in the background
       and queues voice while the screen is off.
     - *If you decline:* muse disconnects when the app is closed.
     - Action: *Allow background* / *Skip*.

  4. **Bluetooth (optional).**
     - *Why:* driving-mode auto-enter when your car pairs.
     - *If you decline:* driving mode stays manual.
     - Action: *Allow Bluetooth* / *Skip*.

  5. **Pin lock-screen widget (optional).**
     - *Why:* glanceable muse status without unlocking.
     - *If you decline:* you must open the app to see status.
     - Action: *Pin widget* / *Skip*.

- **Primary action.** *Continue* — advances to step 5 regardless
  of how many were allowed or skipped.
- **Skip all.** *Skip all — set up later* — equivalent to tapping
  *Skip* on each row, then *Continue*.

**Empty state.** Not applicable.

**Loading state.** Each row briefly shows a spinner while the
system permission dialog is in flight.

**Error state.** *"Don't ask again"* (permanent denial) is
detected and the row updates: *"Microphone is permanently denied.
Open system settings to allow."* Tapping opens Android system
settings for the app.

**Success state.** Granted rows show a green check; declined rows
show a *Revisit later* link that opens the relevant Settings
section.

**Mobile behavior.** Rows are tap-large (≥ 56 dp). The system
permission dialog is the only modal that interrupts the flow.

**Safety.** Permission rationale is shown **before** the system
dialog — the rationale is the *Why* line — so the owner is never
asked to grant a permission without context. Declining never
silently breaks a flow elsewhere; affected features show the
inline *"<feature> needs <permission>"* affordance.

**Accessibility.** Each row's *Why* line is announced on focus;
the *If you decline* line is announced on long-focus.

**Offline.** Fully offline — permissions are a local concern.

---

## Step 5 — You're in

**Purpose.** Tiny tour. Two paragraphs and one quick visual of the
interactive icon and the emergency stop gesture. Then land on
Home.

**Components.**

- **Heading.** *"You're in."*
- **Subhead.** *"Here are three things to know before you start."*
- **Three explainer cards** (compact, one-thumb scrollable):

  1. **The icon is your shortcut.**
     *"Tap to chat. Long-press for voice. Swipe up for approvals
     (or tasks). Swipe down for the audit ledger. Double-tap to
     trigger emergency stop."*
     A small animation of the icon cycling through its six states.

  2. **Approvals stay with you.**
     *"muse will never spend, deploy, publish, merge to main,
     change a credential, or make a regulated claim without
     asking. Approvals live on the Approvals screen and the
     interactive icon turns bright when one is waiting."*

  3. **Stop is one gesture, anytime.**
     *"From any screen, double-tap the icon to stop muse
     Resume needs you to say or tap 'Resume muse' — no
     automatic resume."*

- **Primary action.** *Open muse* — writes the onboarding-complete
  flag to DataStore and navigates to **muse Home**.

**Empty / loading / error states.** Not applicable.

**Mobile behavior.** Cards are 1-tap to expand for more detail.
Primary action sits in the bottom 25%.

**Safety.** No outbound writes other than the onboarding-complete
flag.

**Accessibility.** The icon animation has a `Role.Image` with a
content description *"muse icon cycling through its six states:
ready, listening, thinking, waiting, paused, stopped."* Reduce
motion shows a static glyph instead.

**Offline.** Fully offline.

---

## Onboarding state machine

```
                        first-launch
                              │
                              ▼
                          ┌────────┐
                          │ Splash │
                          └───┬────┘
                              │
                  onboarding-complete?
                   /                \
                no                   yes
                 │                    │
                 ▼                    ▼
            ┌─────────┐           ┌──────┐
            │ Step 1  │           │ Home │
            └───┬─────┘           └──────┘
                │
   ┌────────────┴─────────────────────┐
   │ Get started        Mock & look   │
   ▼                                  ▼
┌─────────┐                      mark complete +
│ Step 2  │                      mock = on
└───┬─────┘                          │
    │                                ▼
    │ Save / Skip                ┌──────┐
    ▼                            │ Home │ (mock banner)
┌─────────┐                      └──────┘
│ Step 3  │
└───┬─────┘
    │
    ▼
┌─────────┐
│ Step 4  │
└───┬─────┘
    │
    ▼
┌─────────┐
│ Step 5  │
└───┬─────┘
    │ Open muse
    ▼
mark complete +
mode written +
land on Home
```

The onboarding-complete flag is a single boolean in DataStore
(`hermes_settings`). Once true, the splash routes to Home directly.
A *Re-run onboarding* affordance is available in **Settings →
About** so the owner can revisit the flow without resetting
everything.

---

## Persistence summary

| Onboarding choice | Storage | Key |
|---|---|---|
| Gateway URL | DataStore (non-secret) | `gateway_url` |
| Gateway bearer token | EncryptedSharedPreferences | `gateway_token` |
| Provider id | DataStore | `provider_id` |
| Provider API key | EncryptedSharedPreferences | `provider_api_key` |
| Mode (Live / Termux / Mock) | DataStore | `mode` |
| Onboarding complete | DataStore | `onboarding_complete` |
| Permissions decisions | Android system + DataStore (revisit shortcuts) | `permission_<name>_decided_at` |
| Widget pinned | Android system (`AppWidgetManager`) | n/a |

Nothing else is persisted from onboarding — defaults for voice
verbosity, memory verbosity, notification classes, theme, and
behavior are written on first launch with sensible defaults and
edited in Settings.

---

## Validation rules

The pager enforces these rules before allowing advance:

| Step | Rule |
|---|---|
| 1 | None — both actions advance. |
| 2 | *Save & continue* enabled only after a successful `/v1/health` in this session, **or** *Skip* tapped (which forces Mock for step 3). |
| 3 | A mode is always selected (Live · Termux · Mock). *Continue* always enabled. |
| 4 | Always advanceable. Declining permissions never blocks. |
| 5 | *Open muse* always enabled. |

---

## Accessibility summary

- Pager dots are reachable as buttons; each announces *"Step N of
  5"*.
- Every primary action is ≥ 64 dp; every secondary action ≥ 48 dp.
- Reduce-motion respected for the step-5 icon animation.
- High-contrast theme is honored across all steps.
- Plain-language content descriptions on every interactive element.
- The voice grammar to advance is enabled only if step 4 grants
  microphone — the owner can say *"Continue"* to advance between
  steps once voice is on.

---

## Cross-references

- [`jarvis-prime-app-product-spec.md`](jarvis-prime-app-product-spec.md)
  — the product promise the onboarding teaches.
- [`jarvis-prime-app-user-flows.md`](jarvis-prime-app-user-flows.md)
  — flow #1 (open and see status), #11 (emergency stop), #17 (mock
  mode), #18 (Termux), #19 (decline optional permissions) all
  start or pass through onboarding.
- [`jarvis-prime-app-screen-map.md`](jarvis-prime-app-screen-map.md)
  — the route table includes onboarding (`onboarding`) and its
  components.
- [`jarvis-prime-app-launch-standard.md`](jarvis-prime-app-launch-standard.md)
  — the launch checklist requires onboarding to be reachable, to
  finish in under 90 s on a connected device, and to land
  somewhere usable on a skip.
- [`apps/android/README.md`](../apps/android/README.md)
  — the existing first-run section is superseded by this spec for
  muse builds.
