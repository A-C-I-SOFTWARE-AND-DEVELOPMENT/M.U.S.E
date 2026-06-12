# Voice-first architecture

Phase 19 — voice-to-text job intake and the contract between M.U.S.E.
and the mobile cockpit / Termux gateway.

> **Audience:** anyone wiring a voice surface (Android cockpit, Termux
> gateway, CLI, an external app talking to the gateway) to M.U.S.E..
> Implementers of the *audio* side (sounddevice, faster-whisper,
> Groq, etc.) — see `hermes_cli/voice.py`.

## 1. Goals

- Let a user create a M.U.S.E. job by talking — including hands-free
  while driving — without surprising them.
- Keep raw audio off M.U.S.E.' disk unless the user explicitly opts in.
- Make every step auditable: a single intake folder per interaction
  with three text artefacts (transcript, plain-English read-back,
  approval state).
- Treat the orchestrator as the only path to action. Voice intake
  drafts and *describes* what would happen; the orchestrator is the
  one that actually does it, and only after explicit confirmation.

## 2. Non-goals

- M.U.S.E. does **not** ship its own audio capture stack. The platform
  (Android, Termux, desktop CLI) captures the bytes and sends a
  transcript or audio blob to the gateway. The intake pipeline only
  ever consumes text.
- M.U.S.E. does **not** continuously upload raw audio. If a user enables
  remote STT, only the chunked audio that follows a wake event or
  push-to-talk press is forwarded — see `stt-provider-policy.md`.
- Voice intake is **not** an "always-on assistant" surface.
  Background listening is opt-in and bounded by mode (see §3).

## 3. Voice modes

The four modes live in `hermes_cli/voice_models.py` as
`VOICE_MODES`. Every gateway, CLI surface, and cockpit must accept
all four spellings exactly as written here so the same config value
binds the same behaviour everywhere.

| Mode | Trigger | Safe while driving? | Notes |
|------|---------|---------------------|-------|
| `push_to_talk` | User key / button | Only when the device is mounted and the button is on the wheel | Default. The user is the explicit start signal. |
| `wake_word` | Local wake engine | Yes, if the wake engine runs entirely on-device | Requires `HERMES_VOICE_WAKE_WORD` *and* an on-device wake detector. |
| `driving_capture` | Local wake engine **plus** a "captured" indicator on the surface | Yes — this is the mode designed for it | Forces the strictest safety defaults; see `driving-mode-safety.md`. |
| `disabled` | — | — | Voice intake is off. Any pipeline call raises `VoiceDisabledError`. |

A surface that sends `mode: "ptt"`, `mode: "wake"`, `mode: "drive"`,
or `mode: null` is normalised by `voice_models.normalize_mode` — the
fallback for an unknown value is `push_to_talk`, never
`driving_capture`. Picking the loosest default would let a typo
silently unlock background listening.

## 4. Pipeline

The pipeline lives in `hermes_cli/voice_intake.py`. There are five
explicit steps, and the surface is expected to drive them one at a
time so the read-back and confirmation are observable.

```
audio capture       ──── platform (app, Termux, sounddevice)
        │
        ▼
   STT provider     ──── local Whisper preferred, remote opt-in
        │  text
        ▼
1. begin_intake     ──── open ~/.hermes/voice/<voice-id>/, mode 0o700
        │
        ▼
2. ingest_transcript ─── redact secrets, classify intent, build draft
        │
        ▼
3. build_readback   ──── persist plain-english-confirmation.md, return spoken summary
        │
        ▼
4. record_decision  ──── interpret yes / no / silence; persist approval-state.json
        │
        ▼
5. finalize         ──── if approved: hermes_cli.orchestrator.submit_job(prompt)
                                      → returns orchestrator job ID
                         if cancelled/expired: returns None, leaves transcript on disk
```

The per-interaction folder always contains:

- `voice/transcript.txt` — the **redacted** text the agent acted on.
  Raw audio is never written here.
- `voice/plain-english-confirmation.md` — the read-back exactly as
  it was presented for confirmation (also rendered in the cockpit
  review screen).
- `voice/approval-state.json` — the terminal record of how the user
  resolved the read-back. Pending intakes don't write this file
  until they reach a terminal state.

The pipeline also writes `voice/intake.json` for the gateway's
`/cockpit/voice/last` debug view — that file is for diagnostics, not
contract, and may grow new fields.

## 5. Intent classification

`voice_models.classify_intent` returns one of:

| Intent | Triggered by | Pipeline effect |
|--------|--------------|-----------------|
| `capture_note` | "note", "remember", "todo", "remind me" | Persists, never auto-implements. |
| `create_job` | "create", "implement", "build", "publish", "fix", "refactor" | Eligible for orchestrator submission after approval. |
| `query_status` | "status", "what's the status", "update me" | Read-only; the read-back contains the answer. |
| `cancel` | "cancel", "abort", "never mind", "stop" | Used in step 4 to interpret a confirmation utterance. |
| `confirm` | "yes", "confirm", "go ahead", "approve" | Same — step 4 only. |
| `repeat` | "repeat", "say again", "read back" | Re-runs `build_readback` against the same intake. |
| `unknown` | anything else | In `driving_capture` mode this is degraded to `capture_note`; elsewhere the read-back asks for a clearer phrasing. |

Classification is deliberately a small set of regex heuristics. The
safety story relies on it being easy to audit; an LLM-based classifier
would tempt callers to skip the read-back.

## 6. The orchestrator hand-off

`finalize(intake, submitter=…)` is the only seam that turns a voice
intake into action. By default it calls
`hermes_cli.orchestrator.submit_job(prompt)`. The cockpit can pass a
different submitter to route the request through the local API
backend, but the *contract* — "approved transcripts become
orchestrator jobs, nothing else does" — does not move.

The orchestrator job that comes back is tagged in the intake's
approval notes (`orchestrator-job:<job-id>`) so a follow-up audit can
trace a job back to the voice utterance that triggered it.

## 7. Surface contract for cockpit and gateway

The Android cockpit and the Termux gateway both speak to the pipeline
through the same surface:

- `POST /v1/cockpit/voice/intake` — body is a `VoiceTranscript` plus
  a `VoiceIntakeConfig`. The gateway calls `begin_intake` +
  `ingest_transcript` + `build_readback` and returns the read-back
  string and intake ID.
- `POST /v1/cockpit/voice/intake/{id}/confirm` — body is `{"phrase":
  "yes"}` or `{"phrase": "cancel"}`. The gateway calls
  `record_decision` then `finalize`. Returns either the new
  orchestrator job ID or a structured cancellation reason.
- `GET /v1/cockpit/voice/intake/{id}` — returns the intake JSON for
  cockpit review.

These routes are spec — they sit alongside `/v1/cockpit/runtime/...`
in `docs/android/muse-apk-api-contract.md`. Implementations land
together with the gateway work.

## 8. Tests and validation

`tests/test_voice_intake.py` covers the pipeline end-to-end against
a tmp `HERMES_HOME`:

- Mode normalisation and disabled-mode rejection.
- Intent classification across all seven cases.
- Driving-mode redaction + transcript trimming + "capture as note"
  degradation for unknown intent.
- Approval state machine: approve, cancel, ambiguous (driving →
  cancel; non-driving → still awaiting), and timeout.
- Finalize routing to a fake submitter and the driving-mode
  publish veto.

Run with `python -m pytest tests/test_voice_intake.py -q`.

## 9. See also

- `docs/voice/driving-mode-safety.md` — the safety policy enforced
  in driving mode.
- `docs/voice/stt-provider-policy.md` — local-first STT defaults and
  the remote opt-in rules.
- `skills/voice-command-designer/SKILL.md` — playbook for designing
  new voice commands without breaking the safety contract.
- `hermes_cli/voice.py` — the existing audio/TTS layer.
- `hermes_cli/voice_models.py` — the dataclasses that this doc
  describes.
- `hermes_cli/voice_intake.py` — the pipeline implementation.
