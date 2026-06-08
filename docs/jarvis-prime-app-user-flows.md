# MUSE — Android App User Flows

> **Status:** product spec, v1. Companion to
> [`jarvis-prime-app-product-spec.md`](jarvis-prime-app-product-spec.md),
> [`jarvis-prime-app-screen-map.md`](jarvis-prime-app-screen-map.md),
> [`jarvis-prime-app-onboarding-spec.md`](jarvis-prime-app-onboarding-spec.md),
> [`jarvis-prime-app-launch-standard.md`](jarvis-prime-app-launch-standard.md).
>
> Twenty primary flows for the MUSE Android app. Each flow
> is a contract: trigger, happy path, fallback paths, safety
> behavior, accessibility behavior, and offline behavior must all be
> supported end-to-end before the flow is considered done.
>
> The interactive icon (six states, five gestures) is referenced as
> *the icon* throughout — see `jarvis-prime-app-product-spec.md` §5.

---

## Conventions

- *Owner* is the user — Jeremiah by default.
- *MUSE* is MUSE, the operating partner running in the
  gateway.
- *Gateway* is the Hermes Python core / AOS Council / MUSE
  runtime that the app talks to over HTTP + SSE.
- *Confirm phrase* is the literal tap or spoken phrase the owner
  must match to complete a gated action — see product spec §6.2.
- Plain-English readbacks (TTS) are on by default and may be
  disabled in *Settings → Voice*; the visual confirm sheet is
  always shown.

---

## Index

1. [Open app and see MUSE status](#1-open-app-and-see-jarvis-status)
2. [Ask MUSE a casual question](#2-ask-jarvis-a-casual-question)
3. [Use voice capture](#3-use-voice-capture)
4. [Convert rough voice idea into a task](#4-convert-rough-voice-idea-into-a-task)
5. [View active tasks](#5-view-active-tasks)
6. [Approve a risky action once](#6-approve-a-risky-action-once)
7. [Approve a serious action — step one](#7-approve-a-serious-action--step-one)
8. [Approve a serious action — step two](#8-approve-a-serious-action--step-two)
9. [Review a critical impact report](#9-review-a-critical-impact-report)
10. [Reject an action](#10-reject-an-action)
11. [Trigger emergency stop](#11-trigger-emergency-stop)
12. [Correct memory](#12-correct-memory)
13. [Delete memory](#13-delete-memory)
14. [View audit / proof history](#14-view-audit--proof-history)
15. [Use the interactive icon](#15-use-the-interactive-icon)
16. [Handle gateway disconnected state](#16-handle-gateway-disconnected-state)
17. [Use mock mode](#17-use-mock-mode)
18. [Use Termux gateway mode](#18-use-termux-gateway-mode)
19. [Decline optional permissions and continue](#19-decline-optional-permissions-and-continue)
20. [Resume after emergency stop](#20-resume-after-emergency-stop)

---

## 1. Open app and see MUSE status

**Trigger.** Owner taps the MUSE app icon, or unlocks the
phone with the MUSE widget pinned.

**Happy path.**

1. Cold start ≤ 1.5 s. Splash → Home.
2. Home renders the **status header pill** before tiles: *Connected
   · openrouter · claude-3.5-sonnet*.
3. The **interactive icon** renders its current state (Ready,
   Listening, Thinking, Waiting on you, Paused, or Stopped) within
   1 s.
4. **Active tasks tile** lists up to 3 running / waiting tasks.
5. **Approvals tile** shows pending-approval count and a primary
   *Review approvals* CTA when ≥ 1.
6. **Last consequential action tile** shows the most recent ledger
   entry classified as consequential.
7. Owner now has full situational awareness in under 2 s of paint.

**Fallback paths.**

- **Cached state only.** Gateway probe fails; tiles render last-
  known cached values with *"Showing cached state — last sync
  HH:MM"* banner. Icon enters *Paused*.
- **First launch, no settings.** Splash → Onboarding (see flow
  19 / onboarding spec).
- **Emergency stop engaged from a prior session.** Icon enters
  *Stopped*; persistent banner *"MUSE is stopped. Tap to
  resume."* across the app.

**Safety.** Home never auto-dispatches anything on open. No write
fires from open.

**Accessibility.** Status pill announces *"MUSE: connected"*
through TalkBack. Icon announces its state. Tiles are traversable
top-to-bottom in priority order.

**Offline.** Tiles render from cache. *Voice* quick action is
dimmed and labelled *"Voice (offline — capture queued)"*.

---

## 2. Ask MUSE a casual question

**Trigger.** Owner taps the icon (single tap) or the *New chat*
quick action on Home.

**Happy path.**

1. App navigates to **Chat** with a fresh thread or the most recent
   open thread.
2. Composer is focused; soft keyboard rises; primary *Send* button
   sits in the bottom 25%.
3. Owner types *"What's the weather like for my logistics audit
   timeline?"* and taps *Send*.
4. MUSE classifies the request as Companion / Strategy and routes
   through the appropriate mode (mode chip in header reflects the
   choice).
5. Streaming dots appear in a new assistant bubble; tokens arrive
   in deltas; *Abort* button visible.
6. Reply finishes on `done` event; mode chip stays visible; reply
   is copyable.

**Fallback paths.**

- **Stream interruption.** Inline red note under the partial reply
  with a *Tap to retry* banner. Partial reply is preserved.
- **Out-of-scope (touches an Owner Gate).** MUSE classifies the
  request as touching a gated action (e.g. "deploy", "publish",
  "spend"). The reply contains a *Risky action proposed* card with
  a *Review in Approvals* CTA. Nothing is dispatched from chat.
- **Rate limit / 429.** Banner *"MUSE is rate-limited by the
  provider — retrying in <s>s"* with manual *Retry now*.

**Safety.** No destructive action completes from chat. Even if the
owner says *"go ahead and do it"* to a gated proposal, the proposal
goes to Approvals first.

**Accessibility.** Streaming text is announced in chunks, not
characters. *Abort* reads as *"Stop MUSE"*.

**Offline.** Compose works; the message goes to the outbox; banner
*"Offline — messages will send when MUSE is back"*. The owner
taps *Send queued* on reconnect — never silent replay.

---

## 3. Use voice capture

**Trigger.** Owner long-presses the icon (push-to-talk) or taps the
mic FAB on Chat, or says the wake phrase if Continuous mode is on.

**Happy path.**

1. App opens **Voice Capture** (driving-mode-style UI): one large
   mic button (200 dp), single-line phase label ("**Listening —
   speak now**"), live partial transcript in 32 sp.
2. Phase transitions: `idle → listening → transcribing →
   confirming → dispatching → done`.
3. STT runs on-device by default. Cloud STT only if the owner
   opted in for this session; banner *"Audio sent to <provider>"*
   visible while in use.
4. Transcript renders incrementally; owner can tap to edit before
   confirming.
5. Owner taps **Confirm & dispatch** (or speaks *"Confirm"* in
   driving mode). Capture is sent to Chat as a user message.

**Fallback paths.**

- **STT fails.** Phase label *"STT failed — type instead"*. Capture
  buffer is saved locally so the owner can replay or type from it.
  The app never silently swaps to cloud STT.
- **Out-of-grammar in driving mode.** MUSE speaks *"I only take a
  small set of commands while you're driving. Say 'MUSE, end
  driving mode' when you can use the screen."*
- **Mic permission denied.** Banner *"Microphone permission is
  off. Tap to fix in Settings."* Voice features remain disabled.

**Safety.** Voice capture cannot complete an approval by itself —
even *"MUSE, approve"* opens the relevant approval screen, never
fires the write. The exception is *"MUSE, stop everything"* which
triggers the emergency-stop confirm sheet (see flow 11).

**Accessibility.** Phase label is announced through
`TYPE_VIEW_TEXT_CHANGED`. Live transcript is announced as a polite
live region. TTS confirmations are togglable.

**Offline.** Capture works fully offline; transcript and audio go
to the visible outbox for later send. The mic-hot indicator is
unchanged so the owner cannot misread the offline state as
"listening to nothing."

---

## 4. Convert rough voice idea into a task

**Trigger.** Owner is in Chat (or just dispatched a voice capture)
and MUSE surfaces a *Convert to task* chip beneath the latest
assistant reply.

**Happy path.**

1. Owner taps *Convert to task*. **Task draft sheet** opens with:
   - **Captured idea** (the raw transcript or owner message),
   - **Clean task title** (MUSE-suggested),
   - **Short summary** (MUSE-generated),
   - **Recommended agent** (e.g. *AOS Principal Systems Architect*),
   - **Recommended worker** (e.g. *Claude Code Builder*).
2. Owner reviews and edits any field inline.
3. Owner taps **Create task**. App POSTs to the gateway; a new task
   appears at the top of the Tasks screen with status *Queued*.
4. If the task immediately enters a *waiting for approval* state
   (gateway policy), the **Approvals** tile on Home increments and
   a push notification fires (calm-by-default applies — only the
   "approval pending" class).

**Fallback paths.**

- **Gateway 5xx on create.** Task draft is preserved; banner
  *"Couldn't reach MUSE — kept as draft"*. Drafts live under
  *Tasks → Drafts* and replay only when the owner taps *Create now*.
- **Mode is Mobile Voice.** The task draft sheet is collapsed to
  the **Mobile Voice format** (captured idea · clean title · summary
  · recommended agent · recommended worker · next focused action)
  per [`jarvis-prime-operating-system.md`](jarvis-prime-operating-system.md).
- **Owner explicitly defers.** *Save for later* button keeps the
  draft locally; never auto-dispatches.

**Safety.** Creating a task is not itself an Owner Gate — but any
action the task proposes is. Task creation never bypasses approval.

**Accessibility.** The Task draft sheet's primary action is
reachable in the bottom 25%; all fields are labelled; voice
readback (if on) speaks the clean title and summary back before
the *Create task* confirm.

**Offline.** Drafts are local. Creation is queued in the visible
outbox; the owner must tap *Send queued* to release.

---

## 5. View active tasks

**Trigger.** Owner taps the *Active tasks* tile on Home, the
*Tasks* quick action, or swipes the icon up (when not in *Waiting
on you*).

**Happy path.**

1. App navigates to **Tasks**.
2. Filter chip row sticks to the top: *all · running · waiting ·
   done · failed · cancelled*. Default *all*.
3. Task rows render two-line: title + worker chip on line one;
   status badge + relative time on line two.
4. Live SSE feed turns the *live* pill green; status badges update
   in place as workers progress.
5. Tap a row → Task detail with plan, files affected, validation
   gate status, decision-ledger summary, and *Open in Approvals*
   button when applicable.

**Fallback paths.**

- **SSE drop.** *Live* pill turns amber: *"Live updates paused —
  reconnecting"*. Manual *Reconnect* in overflow menu. List still
  renders.
- **Empty.** *"No tasks yet. Ask MUSE to do something."* with a
  *Start a task* primary button.
- **Failed task.** Red glyph on the row; tap *View why* opens the
  audit ledger filtered to that task id.

**Safety.** Swipe-right *Approve* on a *waiting for approval* row
**does not** complete the approval — it shortcuts to the Approvals
screen for that task. Swipe-left *Cancel* shows a confirm sheet.

**Accessibility.** Row content descriptions include status and
relative time. Swipe actions have keyboard equivalents in the
overflow menu.

**Offline.** Cached list renders with last-synced banner. *Cancel*
is blocked offline (see product spec §4.4).

---

## 6. Approve a risky action once

**Trigger.** A task or chat surfaces an approval card. The owner
taps *Review* (from Approvals, from the Approvals tile, from the
Tasks swipe shortcut, or from the icon's *Waiting on you* swipe-up).

**Happy path.**

1. App navigates to the **Approval detail** screen for that
   approval.
2. Header shows classification badge: **Risky**.
3. Body shows the plain-English action, files / endpoints affected,
   validation gate status (✅ pass etc.), and the requested-by
   attribution.
4. Bottom action bar: **Approve** (green, 64 dp) · **Reject** (red,
   64 dp).
5. Owner taps **Approve**. Confirm sheet rises with the action
   summary and the confirm phrase *"Approve"*.
6. Owner taps **Confirm approval** (or speaks *"Approve"* in voice
   mode).
7. Write fires with an `Idempotency-Key`. Card transitions to
   completed (green); a ledger entry is written; voice readback
   (if on) says *"Approved <title>. Logged to audit."*

**Fallback paths.**

- **Stale state (HTTP 409).** App silently refreshes the approval
  card and re-asks for confirm. The original button never fires
  twice.
- **Approval revoked between view and confirm.** Sheet shows
  *"This approval was withdrawn by MUSE — nothing to approve."*
  Approve button is hidden.
- **Write 5xx.** Banner with *Retry* and *Copy decision payload*.
  No silent retry.

**Safety.** The confirm sheet is a separate sheet, not an inline
button — the owner cannot complete the approval without crossing
two layers of UI. Approvals are blocked while emergency stop is
engaged.

**Accessibility.** *Reject* is a 64 dp red button, not a small text
link. Confirm phrase is voice-actionable.

**Offline.** Approvals are **never completable offline.** Buttons
are dimmed with *"Approvals need MUSE online — they live in the
gateway's audit ledger."*

---

## 7. Approve a serious action — step one

**Trigger.** Owner opens the Approval detail for a Serious-class
approval (e.g. "open a draft PR", "write durable memory", "install
a new skill", "change a default model").

**Happy path.**

1. Header shows classification badge: **Serious**.
2. Body shows the plain-English action, files / endpoints,
   validation gate status, requested-by.
3. **Step one** sheet appears below the body: *"I understand the
   impact"* — an evidence card listing what changes, what can
   break, and the recommended rollback path.
4. Owner reads the evidence card and taps *I understand the impact*.
5. The button enables **Approve as authorized** in the bottom
   action bar; the evidence-card acknowledgement is visible on
   the screen so the owner sees they have completed step one.

**Fallback paths.**

- **Owner closes the screen before step two.** The step-one
  acknowledgement is **not** persisted across navigation. Re-opening
  the approval requires re-reading the evidence card. This is
  intentional — the acknowledgement is *fresh consent*.
- **Evidence card cannot be rendered.** Banner *"MUSE could not
  produce the impact summary. You can still reject this approval."*
  *Approve as authorized* stays disabled.

**Safety.** Step one alone never writes. Step one is also never
inferred from a tap on a different part of the screen — only the
explicit *I understand the impact* control counts.

**Accessibility.** The evidence card is scrollable and screen-
reader-readable in document order; *I understand the impact*
control is announced as *"Step one of two: confirm you understand
the impact"*.

**Offline.** Same as flow 6 — approvals are not completable
offline. Step one cannot be acknowledged offline either; the screen
shows the offline banner instead.

---

## 8. Approve a serious action — step two

**Trigger.** Owner has completed step one in flow 7 and *Approve
as authorized* is enabled.

**Happy path.**

1. Owner taps **Approve as authorized**.
2. Confirm sheet rises with the full plain-English action, the
   classification badge, and the confirm phrase: *"Approve as
   authorized"* (tap) or *"Yes, with authorization."* (voice).
3. Owner matches the phrase. Write fires with an `Idempotency-Key`
   that bundles the step-one acknowledgement, the step-two confirm,
   and the originating approval id.
4. Card transitions to completed (green). Ledger entry includes
   *two-step* annotation. Voice readback (if on) says *"Approved
   <title>. Logged to audit. This was a two-step approval."*

**Fallback paths.**

- **Step-one expired** (owner left and came back). Sheet refuses
  with *"Re-confirm the impact first."* Owner returns to step one.
- **Stale state (HTTP 409).** Same recovery as flow 6.
- **Wrong confirm phrase** (voice path). TTS says *"That wasn't the
  confirm phrase. Say 'Yes, with authorization' to approve."*
  Owner re-attempts or taps *Cancel*.

**Safety.** The two steps are deliberately not chained — there is
no way to dispatch a Serious approval from a single gesture.

**Accessibility.** Confirm sheet uses dialog semantics
(`Role.Dialog`); confirm and cancel are both reachable with one
thumb.

**Offline.** Approvals are not completable offline.

---

## 9. Review a critical impact report

**Trigger.** Owner opens the Approval detail for a Critical-class
approval (e.g. "deploy", "publish", "OAuth change", "main-branch
merge", "spend money", "package publish", "DNS change", "regulated
claim").

**Happy path.**

1. Header shows classification badge: **Critical**.
2. The full **Impact Report** is displayed inline at the top of
   the body, with the five mandatory sections:
   - **What changes** — plain-English summary of the actual
     mutation.
   - **Who sees it** — public / private / internal / paid
     recipients.
   - **What can break** — top three failure modes.
   - **Rollback** — concrete revert path (commit hash, deploy id).
   - **Why now** — chain of reasoning from prompt to action.
3. Owner scrolls to the bottom of the Impact Report. *Acknowledged*
   button enables.
4. Owner taps *Acknowledged*. Step one (*I understand the impact*)
   enables.
5. Owner completes step one (flow 7) and step two (flow 8). Ledger
   entry includes both *two-step* and *impact-report-shown:true*
   annotations.

**Fallback paths.**

- **Impact Report missing a section.** That section renders as
  *"MUSE could not produce this section."* Owner can still
  reject. *Acknowledged* still requires scrolling to the bottom
  to enable, but the owner is informed about what was missing.
- **Impact Report fails to load.** Banner *"Impact report
  unreachable — cannot approve critical action."* Approve buttons
  stay disabled. Reject is still available.

**Safety.** *Acknowledged* must be earned by scrolling to the
bottom — a sentinel scroll listener confirms the owner reached the
end. Auto-scroll does not count.

**Accessibility.** The Impact Report is read in document order;
the sentinel is announced as *"End of impact report. Tap Acknowledged
to continue."*

**Offline.** Critical approvals are not completable offline.

---

## 10. Reject an action

**Trigger.** Owner is on any approval (Risky, Serious, or Critical)
and chooses not to authorize it.

**Happy path.**

1. Owner taps **Reject** (red, 64 dp, in the bottom action bar).
2. Confirm sheet rises with a single optional **Why?** field
   (text or voice). No phrase to match — rejecting is intentionally
   low-friction.
3. Owner taps *Confirm rejection*. Write fires with
   `Idempotency-Key`.
4. Card transitions to rejected (gray); ledger entry is written
   with classification *approval*, decision *rejected*, and the
   *Why?* note if provided. Voice readback (if on) says *"Rejected
   <title>. Logged to audit."*

**Fallback paths.**

- **Stale state (HTTP 409).** App silently refreshes and re-asks.
- **Write 5xx.** Banner with *Retry* and *Copy decision payload*.

**Safety.** Rejecting is one-step and easy on purpose. The original
proposal is not deleted — the audit keeps both the proposal and the
rejection. MUSE is allowed to propose again with new context.

**Accessibility.** *Reject* is a destructive-style button with red
fill and high-contrast text; screen reader announces *"Reject this
proposal"*.

**Offline.** Reject is treated the same as approve — **not
completable offline.** Rejection is also a signed ledger write.

---

## 11. Trigger emergency stop

**Trigger.** Owner is on **any screen** and wants to stop all
MUSE activity immediately.

**Happy path.**

1. Owner **double-taps the interactive icon** (any screen) or
   long-presses the lock-screen widget, or speaks *"MUSE, stop
   everything"* if voice mode is on.
2. **Emergency stop confirm sheet** rises immediately. The sheet
   shows: *"Stop MUSE right now? All running tasks pause, all
   approvals are blocked, and MUSE won't take any new action
   until you Resume."*
3. Owner taps **Stop now** (or speaks *"Stop now"*).
4. Local effect (≤ 200 ms): icon flips to *Stopped* (red bar)
   across the app; persistent banner *"MUSE is stopped"* appears
   app-wide; all approval buttons are disabled; outgoing writes
   are blocked at the source.
5. Gateway-side stop is dispatched; if the gateway acknowledges,
   the banner shows *"Stopped — gateway acknowledged HH:MM"*. If
   not, retries fire on backoff; the local stop is **not** rolled
   back during retry.
6. Ledger entry classified as *stop* is written when the gateway
   acknowledges (or queued in the outbox if offline).

**Fallback paths.**

- **Owner triggers stop on a screen that already shows Stopped.**
  No-op. Sheet shows *"MUSE is already stopped. Tap to resume."*
- **Owner cancels the confirm sheet.** No state change; banner not
  shown.
- **Gateway never acknowledges.** Local state remains Stopped
  indefinitely. Banner reads *"Stopped — gateway not reachable.
  Will keep retrying."* Resume still requires the gateway online
  (see flow 20).

**Safety.** This is the only flow where a single gesture (double-
tap) triggers a destructive-looking sheet. The confirm sheet is
still required — there is no double-tap-to-fire. The icon's
double-tap is mapped specifically because a single accidental
tap should not pause MUSE.

**Accessibility.** Stop announces *"MUSE stopped"* through
`TYPE_ANNOUNCEMENT`. The confirm sheet has dialog semantics. Voice
trigger *"MUSE, stop everything"* is honored in every voice mode.

**Offline.** Stop **works offline.** Device-side stop is immediate
and reconciles when the gateway returns. The outbox holds the
gateway-side write.

---

## 12. Correct memory

**Trigger.** Owner navigates to **Memory** (from Home quick
actions, from the icon's swipe-down then *Memory* breadcrumb, or
from the Settings *Memory* section).

**Happy path.**

1. Memory list renders categorized rows: Preference · Decision ·
   Mission · Lesson · Skill hint · Environment fact.
2. Owner finds the row to correct (search or scroll).
3. Owner taps **Correct** on the row. Inline edit opens with the
   fact text editable. Category and last-confirmed date are also
   editable.
4. Owner edits and taps *Save*.
5. Write fires. Row briefly flashes green and the audit ledger
   gets an entry classified as *memory* with action *correct*.

**Fallback paths.**

- **Conflict.** Another correction landed in the meantime. App
  silently refetches and shows *"This fact changed while you were
  editing — review the new version."* Owner re-edits.
- **Secret-shaped content.** Gateway refuses with classification
  *secret-shaped*; inline red note: *"That looks like a secret.
  MUSE won't store secrets. Edit out the credential and try
  again."* Local edit is preserved so the owner can sanitize.

**Safety.** Memory writes are gated by the gateway's
classification. Correcting a fact does not delete the original —
the audit keeps the prior version for rollback.

**Accessibility.** Inline edit announces *"Editing memory: <title>
in <category>"*. Save and Cancel are both reachable with one
thumb.

**Offline.** Correction queues in the visible outbox; banner
*"Memory edit queued — send when MUSE is back"*. The local
list shows the queued value with an *Outbox* badge until released.

---

## 13. Delete memory

**Trigger.** Owner is on the Memory screen and wants to remove a
durable fact.

**Happy path.**

1. Owner taps **Delete** on the row. Confirm sheet rises with
   the fact text and *"Delete this memory? It will be removed from
   MUSE's context immediately."*
2. Owner taps **Delete now**.
3. Row slides out. *Undo* snackbar appears for 5 s.
4. If the owner does not tap *Undo* within 5 s, write fires and
   the audit ledger gets an entry classified as *memory* with
   action *delete*. The original text is preserved in the ledger
   entry so the owner can restore from audit.

**Fallback paths.**

- **Undo.** Snackbar tap before 5 s. Local row is restored; no
  write fires.
- **Bulk delete.** Long-press a row to enter bulk-select mode;
  select N rows; tap **Delete**. One combined confirm sheet for
  the count: *"Delete N memories?"* One ledger entry per row.

**Safety.** Delete is one-step on purpose — memory should be easy
to remove. *Undo* exists because intent matters. The audit ledger
preserves the deleted content; it is not unrecoverable.

**Accessibility.** Undo snackbar is announced as *"Memory deleted.
Tap to undo."* and is reachable with TalkBack within the 5 s
window.

**Offline.** Delete queues in the outbox. The local row is hidden
but not gone; Undo is available until the outbox releases.

---

## 14. View audit / proof history

**Trigger.** Owner taps the *Last consequential action* tile on
Home, the *Audit* quick action, the icon's swipe-down gesture, or
opens the lock-screen widget pinned in *audit summary* mode.

**Happy path.**

1. App navigates to **Audit / Proof**.
2. Timeline renders most-recent-first with day separators.
3. Each entry: timestamp · actor · action · classification ·
   one-line plain-English summary · *Show details*.
4. Filter chips: *all · approvals · decisions · publishes ·
   deploys · memory · stops · errors*. Default *all*.
5. Owner taps *Show details* on an entry to see the full
   structured payload: rationale, files / endpoints, link to
   originating task, link to the Approval card if gated, link to
   memory facts referenced.

**Fallback paths.**

- **Ledger read 5xx.** Banner *"Audit ledger unreachable — showing
  local cache up to HH:MM"*. The local cache is clearly labelled.
- **Export.** Owner taps *Export filtered range as JSONL*; file
  saves to Downloads and is shared via system share sheet. Export
  works against cache offline.

**Safety.** Read-only from the app. No edit, no delete. Owner
annotations are added as **new** linked entries — never as edits.

**Accessibility.** Each entry's content description is *"<actor>
<action>, <classification>, <relative-time>. Tap to expand."* Day
separators are heading-roled.

**Offline.** Local cache renders; export works against cache.
Owner annotations queue in the outbox.

---

## 15. Use the interactive icon

**Trigger.** Owner is on any screen and uses one of the five
gestures on the icon.

**Happy path (per gesture).**

| Gesture | Result |
|---|---|
| **Single tap** | Navigates to Chat (or back to Chat if already there). |
| **Long press** | Opens Voice Capture / driving-mode UI. |
| **Double tap** | Opens Emergency stop confirm sheet (flow 11). |
| **Swipe up** | If icon state is *Waiting on you*, opens Approvals. Otherwise opens Tasks. |
| **Swipe down** | Opens Audit / Proof. |

**Fallback paths.**

- **State changes mid-gesture.** Gesture is interpreted against
  the state at the moment the gesture begins, not when it ends.
- **Gesture conflict with system gestures (back, edge swipe).**
  The icon respects the system gesture region — the icon is
  positioned so neither swipe up nor swipe down conflicts with
  the system navigation areas on the device's current
  configuration.
- **Reduce motion enabled.** Icon animations become static; the
  same gestures still work.

**Safety.** Gestures are consistent across every screen — the
owner does not have to relearn them. Double-tap → Emergency stop
confirm (not direct stop) so a misfire does not pause MUSE. Long
press → Voice (a hold) so an accidental brush of the icon does not
start the mic.

**Accessibility.** All five gestures have overflow-menu equivalents
labelled *"Open chat"*, *"Open voice"*, *"Emergency stop"*, *"Open
approvals / tasks"*, *"Open audit"*.

**Offline.** Single tap, long press, swipe-up to Tasks, and
swipe-down to Audit all work offline (against cache). Double tap
to emergency stop works offline (local effect immediate; gateway
reconciliation queued).

---

## 16. Handle gateway disconnected state

**Trigger.** Owner is using the app and the gateway becomes
unreachable (Wi-Fi dropped, gateway crashed, cellular dead zone).

**Happy path.**

1. App's foreground service notices `/v1/health` failures within
   ~8 s thanks to the short-timeout client.
2. Status pill on Home transitions to red *Offline* (or amber
   *Degraded* if SSE drops only).
3. Icon transitions to *Paused* across the app.
4. Each screen displays its offline behavior (see product spec §4):
   - Home tiles show cached state with a *Last sync* banner.
   - Chat compose works; messages queue in outbox.
   - Tasks renders cached list.
   - Approvals blocks Approve / Reject.
   - Memory blocks writes; queues in outbox.
   - Audit renders cached entries.
   - Control still works for emergency stop and mock toggle.
   - Settings works for local prefs.
   - Diagnostics works fully.
5. When connectivity returns, status pill flips to *Connecting…*
   then *Connected*. Icon flips to *Ready*. Outbox badge in the
   top bar offers *Send queued*.

**Fallback paths.**

- **Wrong backend URL** (e.g. emulator-only URL on a real device).
  Status pill shows *"Wrong backend URL"* with a *Fix in Settings*
  link.
- **TLS error.** Pill shows *"TLS error — tap Details"*.
- **HTTP 401.** Pill shows *"Gateway token rejected"* with a *Fix
  in Settings → Connection* link.

**Safety.** Writes are **blocked at the source**, not silently
queued for approvals or emergency stop. The owner always sees true
state.

**Accessibility.** Pill announces state changes through
`AccessibilityEvent`. Banners are screen-reader-readable.

**Offline.** This *is* the offline behavior. The app is designed
for this case.

---

## 17. Use mock mode

**Trigger.** Owner taps *Use mock mode and look around* on
Onboarding, or toggles *Mock mode* in **Control** or **Settings →
Connection**.

**Happy path.**

1. **Persistent banner** appears across the app: *"Mock mode is on
   — MUSE is not connected to a real gateway."*
2. Status pill on Home shows *Mock* (distinct color from any live
   state).
3. Chat streams canned responses; Tasks shows demo tasks;
   Approvals shows demo approvals (Risky, Serious, Critical
   examples); Memory shows demo facts; Audit shows demo entries.
4. Approvals in mock mode behave exactly like live approvals at
   the UI layer — two-step, Impact Report, confirm phrase — but
   complete locally without writing to a real ledger. The mock
   ledger is clearly labelled *(mock)*.
5. Toggling mock off opens a confirm sheet: *"Switching to live —
   MUSE will start using your real gateway. Continue?"* On
   confirm, the banner disappears and live behavior resumes.

**Fallback paths.**

- **Owner forgets mock is on.** The persistent banner is visible
  on every screen and the status pill always shows *Mock*. The
  app does not let this be a quiet state.

**Safety.** Mock mode is opt-in and noisy. No write hits a real
gateway. No real money, no real deploys, no real publishes —
everything is local. Emergency stop in mock mode is local only.

**Accessibility.** Banner is the first thing TalkBack announces
on every screen.

**Offline.** Mock mode is fully offline by definition.

---

## 18. Use Termux gateway mode

**Trigger.** Owner has Termux installed on the device and wants
MUSE running fully on the phone, with the app talking to
`http://127.0.0.1:8080`.

**Happy path.**

1. Owner opens **Control**.
2. App detects Termux (Intent resolves) and shows the **Gateway
   lifecycle** card: *Termux detected — gateway not running*.
3. Owner taps **Start Termux gateway**. App sends an Intent to
   Termux to run `muse gateway start` (per
   [`docs/android/termux-intent-bridge.md`](android/termux-intent-bridge.md)).
4. The Termux log streams into the app's *Termux log* affordance
   on Control.
5. App polls `http://127.0.0.1:8080/v1/health` on backoff. On
   first 2xx, status pill flips to *Connected* and the gateway
   lifecycle card shows *Gateway running on this phone*.
6. Owner uses the app exactly as in any other live mode. Tasks,
   approvals, memory, audit all work; the Python core, AOS
   Council, MUSE runtime are all on this phone.

**Fallback paths.**

- **Termux not installed.** Gateway lifecycle card is hidden;
  Settings → Connection still shows the URL field so the owner
  can point at a remote gateway.
- **Termux Intent rejected** (Termux's `allow-external-apps` not
  enabled). Banner *"Termux blocked the start command. Open Termux
  and enable allow-external-apps, then try again."* with a
  *Termux setup help* link.
- **Gateway never reaches healthy.** App keeps polling; the
  *Termux log* affordance is the owner's debugging surface.
- **Termux killed by Android Doze.** Status pill goes red; the
  gateway lifecycle card flips to *Gateway not running*. App offers
  *Start Termux gateway* again.

**Safety.** Termux start is not an Owner Gate but is logged in the
audit ledger as a *control* entry. Stop is the same.

**Accessibility.** Lifecycle card actions are labelled *"Start
MUSE on this phone"* and *"Stop MUSE on this phone"* for
TalkBack rather than the technical *Termux gateway* label.

**Offline.** Termux mode is by definition not internet-dependent
(loopback). The app's offline-vs-online state is determined by
loopback `/v1/health`, not by network state.

---

## 19. Decline optional permissions and continue

**Trigger.** Owner is on the Onboarding *Voice & permissions* step
(or in Settings later) and is asked for microphone, notifications,
foreground service, optional Bluetooth (driving mode), or widget
pin.

**Happy path.**

1. Each permission is requested **with context first**: the app
   explains, in plain English, what is gained by granting and what
   is lost by declining.
   - **Microphone.** *Gained: voice capture, driving mode. Lost:
     all voice features.*
   - **Notifications.** *Gained: approval pending, validation
     failed, emergency stop, gateway lost alerts. Lost: you must
     open the app to see these.*
   - **Foreground service.** *Gained: MUSE can keep the gateway
     connection alive in the background and queue voice. Lost:
     disconnects when the app is closed.*
   - **Bluetooth.** *Gained: driving mode auto-enter when your car
     pairs. Lost: you toggle driving mode manually.*
   - **Widget pin.** *Gained: glanceable status on the lock screen.
     Lost: you must open the app to see status.*
2. Owner taps **Skip** (or denies via the system permission
   dialog).
3. The decline is recorded with a date and a one-tap *Revisit*
   shortcut placed in **Settings → Voice** (or *Notifications*,
   *Background*, etc.).
4. Onboarding **continues to the next step**. The decline never
   blocks entry into the app.
5. Affected features show a clear *"<feature> needs <permission>.
   Tap to fix."* affordance everywhere they would otherwise be
   used — never silently broken.

**Fallback paths.**

- **Owner permanently denies via system dialog (don't ask again).**
  App detects the permanent denial and the *Revisit* shortcut now
  opens Android system settings for the app, with a one-line
  explanation.

**Safety.** Declining permissions cannot create a state where
MUSE silently fails. Every feature that depends on a
declined permission either:

- shows the inline *Tap to fix* affordance,
- degrades clearly (e.g. voice mode disappears from Voice options),
- or is completely absent and labelled as such.

**Accessibility.** Permission rationales are read by TalkBack
before the system dialog appears. The *Revisit* shortcuts are
labelled with the actual feature that depends on the permission.

**Offline.** Permissions flow is fully local; no network required.

---

## 20. Resume after emergency stop

**Trigger.** MUSE is in *Stopped* state. Owner is on **Control**
(or taps the persistent *"MUSE is stopped. Tap to resume."*
banner from any screen, which navigates to Control).

**Happy path.**

1. Owner taps **Resume**. The app dispatches the gateway resume
   self-check (`/v1/control/resume?dry_run=true`).
2. Resume confirm sheet rises with:
   - **Gateway health** — ok / degraded / unreachable.
   - **Worker queue depth** (zeroed during stop).
   - **Last action before the stop**.
   - **Approvals pending at stop time** that need re-review (with
     direct links).
   - The confirm phrase: *"Resume MUSE"* (tap) or *"Resume
     MUSE"* (voice).
3. Owner reads the self-check, matches the phrase, and taps
   **Confirm resume**.
4. Local state flips: icon goes from *Stopped* to *Ready* (or to
   *Waiting on you* if there are pending approvals); the persistent
   banner disappears; approvals are re-enabled across the app.
5. Ledger entry classified as *control* with action *resume* is
   written, including the self-check result.

**Fallback paths.**

- **Self-check fails** (gateway unreachable). Sheet shows *"MUSE
  can't be resumed yet — the gateway isn't reachable."* Resume is
  blocked until the gateway comes back. No timer-based auto-resume.
- **Self-check degraded.** Sheet shows the degradation reasons;
  owner can still resume by matching the phrase, but the audit
  entry records the degraded state.
- **Owner cancels.** No state change; banner remains; icon remains
  *Stopped*.

**Safety.** Resume is **never automatic**. There is no scheduled
resume, no timeout-based resume, no "tap and we resume in 5
minutes." The phrase must be matched every time. Stop is sticky
on purpose.

**Accessibility.** Resume confirm announces *"Confirm resume.
Read the self-check first."* The self-check is screen-reader-read
in document order before the confirm button is reachable.

**Offline.** Resume requires the gateway online. While offline,
the *Resume* button is dimmed with *"Resume needs MUSE online —
the self-check runs on the gateway."* Emergency stop is still
sticky and still reachable.

---

## Cross-references

- [`jarvis-prime-app-product-spec.md`](jarvis-prime-app-product-spec.md)
  — the product promise, the ten screens, the icon, the approval
  system, and the trust anchors.
- [`jarvis-prime-app-screen-map.md`](jarvis-prime-app-screen-map.md)
  — every navigation target, deep link, and component referenced
  by the flows above.
- [`jarvis-prime-app-onboarding-spec.md`](jarvis-prime-app-onboarding-spec.md)
  — the five-step onboarding pager that flows 1 and 19 traverse.
- [`jarvis-prime-app-launch-standard.md`](jarvis-prime-app-launch-standard.md)
  — the launch readiness checklist; every flow above must pass
  before release.
- [`jarvis-prime-operating-system.md`](jarvis-prime-operating-system.md)
  — the runtime modes and the owner-gate phrase the flows honor.
