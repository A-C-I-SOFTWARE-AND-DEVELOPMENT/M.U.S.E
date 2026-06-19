# muse — App Microcopy

Every user-facing string in the muse Android app, with the
rationale for the wording. This is the editorial bible — if you are
adding a new string, match the voice in this document or update the
document.

The canonical strings live in
`apps/android/app/src/main/res/values/strings.xml`. This document is
the **why** behind those strings.

---

## 1. Voice rules

1. **The agent is "muse"** First-person from the agent is fine
   ("I'm listening", "muse is thinking"). Third-person is also fine
   ("muse remembered…").
2. **Plain words, no jargon.** Say "bring online", not "instantiate."
   Say "halt", not "terminate process."
3. **Consent before action.** Approval / serious / critical copy makes
   it clear *who* is acting and *what* will happen.
4. **Calm, never breathless.** No exclamation marks, no emoji in
   default copy, no "Great!" or "Awesome!".
5. **No outside-product names in UI.** External tools the user has
   subscriptions to (ChatGPT, Claude, Codex) appear as labels for *their*
   handoff cards — that's their literal product name — but unrelated
   open-source projects, GitHub usernames, or internal codenames must
   stay out of the UI surface.

---

## 2. Brand & welcome

| Key | Copy | Why |
|---|---|---|
| `app_name` | **muse** | The product name |
| `app_tagline` | Your command-center agent. | Sets expectation: tool, not toy |
| `welcome_title` | Welcome to muse | Plain greeting |
| `welcome_subtitle` | An agent that asks permission, confirms intent, and shows the work. | Three trust signals in one line |
| `welcome_continue` | Begin | Single, decisive verb |

---

## 3. Ask muse (text/voice input)

| Key | Copy | Why |
|---|---|---|
| `ask_jarvis_hint` | Ask muse… | Lower-effort than "Type a command" |
| `ask_jarvis_voice_cd` | Tap to dictate to muse | Spell out the gesture for screen readers |
| `ask_jarvis_send_cd` | Send to muse | Confirms destination |
| `ask_jarvis_listening` | Listening… speak naturally | Reassurance that there's no command grammar |
| `ask_jarvis_thinking` | muse is thinking… | "Thinking" beats "Processing" — feels less robotic |

---

## 4. Voice capture

| Key | Copy | Why |
|---|---|---|
| `voice_title` | Voice intake | Match the technical surface name; users learn it |
| `voice_prompt_ready` | Ready when you are. | Calm |
| `voice_prompt_listening` | I'm listening. | Live first-person |
| `voice_prompt_processing` | Processing what you said… | Past-tense reflects the just-finished utterance |
| `voice_prompt_error` | I didn't catch that. Try once more. | "Try once more" beats "retry" — softer |

---

## 5. Approval

| Key | Copy | Why |
|---|---|---|
| `approval_title` | Approval needed | Direct |
| `approval_body` | muse wants to proceed. Review and approve before anything runs. | Two clauses: *what's blocking*, *what to do* |
| `approval_approve` | Approve | One word |
| `approval_deny` | Decline | "Decline" is gentler than "Deny" — same outcome |
| `approval_details` | See details | Pull-detail, not push-detail |

---

## 6. Serious action

| Key | Copy | Why |
|---|---|---|
| `serious_title` | Serious action | Honest naming of the tier |
| `serious_body` | This will make a meaningful change. Confirm intent before muse proceeds. | Names the change as meaningful; names the user as the intent-holder |
| `serious_confirm` | Confirm | |
| `serious_review` | Review change | Verb-noun, matches "Confirm intent" |

---

## 7. Critical action

| Key | Copy | Why |
|---|---|---|
| `critical_title` | Critical action | One step up from "Serious" |
| `critical_body` | This action is destructive or irreversible. muse will not proceed without explicit go-ahead. | "Destructive or irreversible" is the legal-grade phrase. "Explicit go-ahead" tells the user *they* are the gate. |
| `critical_confirm` | I understand — proceed | First-person acknowledgement; harder to fat-finger |
| `critical_cancel` | Hold | Distinct from generic "Cancel"; sounds like a flight-deck call |

---

## 8. Emergency stop

| Key | Copy | Why |
|---|---|---|
| `emergency_stop` | Emergency stop | Industry-standard phrase. Avoid cute. |
| `emergency_stop_cd` | Halt every active task immediately | Screen-reader full intent |
| `emergency_stop_confirm_title` | Halt everything? | Question form — forces a moment of thought |
| `emergency_stop_confirm_body` | muse will stop every running task and stand down. You can bring it back online at any time. | Names the consequence (stop + stand down) and names the recovery (bring back online) so the user is not afraid the button is final |
| `emergency_stop_confirm_yes` | Halt now | Active verb; matches the title |
| `emergency_stop_confirm_no` | Keep going | The "keep" verb makes the safer choice feel like the default |
| `emergency_stop_engaged` | All tasks halted. muse is standing by. | Closes the loop |

---

## 9. Gateway / connection

| Key | Copy | Why |
|---|---|---|
| `gateway_pill_label` | Gateway | The pill always reads "Gateway · <state>" so users learn the term |
| `gateway_status_online` | Online | |
| `gateway_status_listening` | Listening | |
| `gateway_status_working` | Working | |
| `gateway_status_disconnected` | Disconnected | |
| `gateway_status_mock` | Mock | |
| `gateway_status_termux` | Termux | |
| `gateway_disconnected_title` | muse is offline | Subject + state; no panic |
| `gateway_disconnected_body` | I can't reach the local gateway right now. Existing work is safe. I'll reconnect as soon as it's available. | Three beats: *what failed*, *what's safe*, *what's next* |
| `gateway_disconnected_retry` | Try again | Plain |
| `gateway_disconnected_diagnose` | Run diagnostics | Names the existing diagnostics screen |

---

## 10. Mock mode

| Key | Copy | Why |
|---|---|---|
| `mock_mode_title` | Mock mode | |
| `mock_mode_body` | muse is running on simulated data. Nothing you do here touches your real accounts or files. | The user must know nothing real is happening |

---

## 11. Termux gateway mode

| Key | Copy | Why |
|---|---|---|
| `termux_mode_title` | Termux gateway | "Termux" is named because the user explicitly opted into it |
| `termux_mode_body` | muse is talking to the Hermes runtime hosted in Termux on this device. Everything stays local. | Mentions Hermes-as-runtime — this is the one place the developer-facing name leaks into UI, deliberately, because the user installed Hermes |

---

## 12. Memory

| Key | Copy | Why |
|---|---|---|
| `memory_card_title` | Memory updated | |
| `memory_card_body` | muse remembered: %1$s | Subject-verb-object |
| `memory_corrected_title` | Memory corrected | |
| `memory_corrected_body` | Got it. muse updated what it remembered about "%1$s". | Acknowledges the user's correction first |
| `memory_view` | Review memory | |
| `memory_forget` | Forget this | Match the agent verb "forget" used in the runtime |

---

## 13. Audit

| Key | Copy | Why |
|---|---|---|
| `audit_card_title` | Audit trail | |
| `audit_card_subtitle` | Every action muse takes is logged here. | Sets the trust promise |
| `audit_open` | Open audit log | |

---

## 14. Task lifecycle

| Key | Copy | Why |
|---|---|---|
| `task_status_drafting` | Drafting | Pre-handoff |
| `task_status_awaiting_approval` | Awaiting approval | |
| `task_status_running` | Running | |
| `task_status_complete` | Complete | "Complete" not "Done" — matches existing internal status `COMPLETE` |
| `task_status_blocked` | Blocked | |
| `task_complete_title` | Task complete | |
| `task_complete_body` | muse finished "%1$s". Tap to review what changed. | Names the task, invites review |
| `task_complete_view` | View result | |
| `worker_failed_title` | Worker failed | "Worker" is the runtime term; users see it in logs |
| `worker_failed_body` | Something went wrong while muse was working on "%1$s". Nothing destructive happened — you can retry or open diagnostics. | Three beats: *what happened*, *what's safe*, *what to do* |
| `worker_failed_retry` | Retry | |
| `worker_failed_diagnose` | Diagnose | |

---

## 15. Permission education

| Key | Copy | Why |
|---|---|---|
| `permission_education_title` | Why muse needs this | Asks the user's *implicit* question |
| `permission_education_microphone_body` | muse listens only while you hold the dictate button. No background recording. No upload off-device unless you ask for it. | Three explicit guarantees, in order: scope, persistence, exfiltration |
| `permission_education_notifications_body` | Notifications let muse tell you when an approval is needed or a task finishes. You can turn them off anytime in Settings. | Use-case + reversibility |
| `permission_education_continue` | Continue | |
| `permission_education_not_now` | Not now | Reversibility implied |

---

## 16. Notification (foreground service)

| Key | Copy | Why |
|---|---|---|
| `orchestrator_notification_title` | muse is on duty | "On duty" matches the command-center voice |
| `orchestrator_notification_text` | Coordinating local AI workflow on this device. | Lowercase, factual |
| `orchestrator_notification_stop` | Stand down | Reused throughout the surface |

---

## 17. Anti-pattern reference

Things that **must not** appear in UI strings:

- "Sorry," / "Oops," — muse is competent, not apologetic
- "AI" as a noun ("the AI thinks") — muse is the agent
- "Powered by …" / "Built with …"
- Emoji in default copy
- Exclamation marks except in clearly emotive places (none currently
  ship)
- Sentence-case headings followed by sentence-case bodies that re-state
  the heading
- Backend names (Hermes, Termux) outside the two contexts that
  explicitly mention them (`app_backend_label`, `termux_mode_body`)
