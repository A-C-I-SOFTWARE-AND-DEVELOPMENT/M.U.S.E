# Driving-mode safety policy

`driving_capture` is the only M.U.S.E. voice mode designed for use
while the user is operating a vehicle. It exists because the
alternative — letting people fall back to `push_to_talk` or unlock
the phone to type — is *less* safe in practice. The mode is
deliberately constrained: if you want to ship a richer in-vehicle
experience, the rule is "make the constraints stricter, not looser".

This document is the canonical safety contract. The pipeline
implementation in `hermes_cli/voice_intake.py` enforces it; this doc
is what the safety review measures the implementation against.

## 1. Scope and disclaimers

- This policy is **not legal advice.** Distracted-driving laws vary
  by jurisdiction. Surfaces that ship `driving_capture` are
  responsible for confirming that the way they expose it complies
  with the user's local rules (hands-free, mounted device,
  voice-only interaction).
- M.U.S.E. ships `driving_capture` as **opt-in**. A factory build
  with no user configuration will run `push_to_talk` and refuse
  driving-mode requests with an explicit "you have not enabled
  driving mode" message rather than silently turning it on.
- This policy applies to voice intake only. It does not authorise
  M.U.S.E. to *do* anything risky on the user's behalf — see the
  publish gate in §5.

## 2. Non-negotiable invariants

The pipeline enforces these in code. Any change to the pipeline must
preserve all of them; a CI review that loosens one of these requires
an explicit sign-off in the PR description.

1. **No manual phone interaction is required at any point in the
   driving-mode flow.** Wake → speak → hear summary → say yes/no.
   The user never looks at or touches the screen.
2. **Background listening is opt-in.** The default mode is
   `push_to_talk`. `wake_word` and `driving_capture` require an
   explicit configuration step (`HERMES_VOICE_MODE=driving_capture`
   plus the wake-engine env vars) and the user is shown a
   confirmation screen the first time the mode is selected.
3. **Wake events are bounded.** A wake event opens at most one
   capture window. The window auto-closes on the first complete
   utterance or after a configurable silence period (default 3 s,
   same as the VAD silence in `hermes_cli/voice.py`).
4. **Raw audio is discarded.** Driving-mode intakes never write a
   WAV to disk. The pipeline only ever receives a `VoiceTranscript`;
   the audio buffer that produced it is released in the recorder
   loop and never serialised.
5. **Read-back is mandatory.** `build_readback` runs before
   `record_decision`. A surface that calls `record_decision` without
   first calling `build_readback` is treated as a bug — there is no
   "skip the read-back" affordance.
6. **Confirmation is explicit.** The pipeline accepts only the
   words listed as affirmative (`yes`, `confirm`, `approve`,
   `go ahead`, `do it`, `proceed`, `ship it`, `publish it`).
   Anything else in driving mode is treated as a cancel, including
   silence (`record_decision(intake, None)` → `expired`).
7. **Unknown intent degrades to "capture note".** The agent never
   guesses a `create_job` action in driving mode for an ambiguous
   transcript. The captured note is reviewable from the cockpit
   when the user is no longer driving.
8. **Publish/merge actions require an out-of-band confirmation.**
   Even an approved driving-mode intake that would publish, merge,
   ship, or release raises `DrivingSafetyVeto` at `finalize` time.
   The orchestrator queues the action for a follow-up confirmation
   step that runs after the device leaves driving mode.

## 3. Mode entry and exit

`driving_capture` is selected one of three ways:

- A persisted setting (`voice.mode: driving_capture` in
  `~/.hermes/config.yaml`).
- An environment variable (`HERMES_VOICE_MODE=driving_capture`).
- An explicit cockpit toggle (the *Driving mode* card on the
  cockpit home screen).

The cockpit toggle is the only one that the user can flip without a
keyboard. The cockpit must show the read-back string from
`build_readback({"prompt": "enable driving mode"})` before changing
the persisted setting — the same one-step-back-out contract used for
job approvals applies to enabling the mode itself.

The mode exits when:

- The user says "exit driving mode" / "disable driving mode" — the
  wake engine treats this as a built-in command.
- The cockpit detects the device leaving the car mount (where the
  platform supports it).
- M.U.S.E. restarts (the mode is not sticky across process restarts
  unless the persisted setting is set; the env var alone is
  per-session).

## 4. Transcript handling

- Transcripts are passed through `voice_models.redact_transcript`
  before they reach disk. The redaction regexes target API keys,
  bearer tokens, AWS access keys, and password-style assignments;
  they are intentionally conservative. False positives (a chunk of
  number-and-letter text replaced with `[REDACTED]`) are an
  acceptable cost.
- Transcripts longer than `driving_max_transcript_chars` (default
  600) are truncated for the read-back so the spoken summary fits in
  a single utterance. The full text is what's written to
  `voice/transcript.txt`.
- The transcript file is created with mode `0o700` (folder
  permission inherits to the file on POSIX). The cockpit and CLI
  read it through the gateway, not via direct filesystem access.

## 5. The publish gate

The pipeline classifies a draft as a publish action when the
transcript contains any of: `publish`, `ship it`, `deploy`, `merge`,
`release`, `send the pr`, `open the pr`. In every mode, a publish
draft is subject to `require_voice_confirmation`. Driving mode adds
the second gate from §2(8): `DrivingSafetyVeto`.

The veto is recoverable. The orchestrator can queue the action and
re-present the read-back the next time the user is in a non-driving
context (cockpit, CLI, normal `push_to_talk`). The user re-confirms
*there*, not while driving.

## 6. Audit trail

Every driving-mode intake leaves:

- `voice/transcript.txt` — the redacted transcript.
- `voice/plain-english-confirmation.md` — exactly what the user
  heard, in Markdown form for cockpit review.
- `voice/approval-state.json` — the terminal decision with
  `decided_at`, the confirmation phrase (if any), and any
  pipeline notes (e.g. *"ambiguous response in driving mode
  treated as cancel"*, *"orchestrator-job:orc-12345678"*).

If a privacy review needs to confirm "no raw audio was kept", the
inspection is: list the intake folder and assert that the only files
present are the three above plus `intake.json`. No `.wav`, no `.ogg`,
no `.mp3`.

## 7. Things this policy deliberately does not allow

The following are common asks that have been declined. If you think
one of them should change, open an issue and reference this section
so reviewers can see the original reasoning.

- **No "voice macro" affordance** — chaining several commands into
  one utterance ("publish the last PR and merge the open one") is
  rejected because each command needs its own read-back. The intake
  pipeline only ever produces one draft per transcript.
- **No live-audio streaming to a remote LLM.** Even when remote STT
  is enabled, the gateway sends discrete utterances; the cockpit
  never opens a long-lived microphone-to-cloud socket. See
  `stt-provider-policy.md`.
- **No "I've been silent for 30 minutes, let me check in" prompts.**
  Driving mode is reactive: the user wakes M.U.S.E., not the other way
  around. The agent never speaks unsolicited in driving mode.
- **No screen unlock prompts from voice.** A spoken request that
  would require the device to be unlocked (open a website, launch an
  app) is captured as a note, not executed.

## 8. See also

- `docs/voice/voice-first-architecture.md` — the overall pipeline.
- `docs/voice/stt-provider-policy.md` — when remote STT is allowed,
  what gets sent, and what gets kept.
- `hermes_cli/voice_intake.py` — the implementation of every
  safety bullet in this doc.
- `hermes_cli/voice_models.py` — the dataclasses + redaction
  patterns referenced above.
