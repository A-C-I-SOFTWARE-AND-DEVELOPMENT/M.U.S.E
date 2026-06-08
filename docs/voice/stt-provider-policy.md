# STT provider policy

How M.U.S.E. chooses a speech-to-text provider, what it sends, what it
stores, and when the user has to opt in.

> **One-line policy:** local STT is preferred, remote STT is
> opt-in, raw audio is discarded by default, and transcripts live in
> the per-intake folder under `~/.hermes/voice/`.

## 1. Provider taxonomy

`VoiceIntakeConfig.stt_provider` is a plain string. The voice
pipeline does not care which backend produced the transcript — that
choice lives in `hermes_cli/voice.py` (and, on Android, in the
cockpit's audio module). The intake pipeline only records the
provider name for the audit trail.

The recognised tiers are:

| Tier | Examples | Default? | Network? |
|------|----------|----------|----------|
| Local | `faster-whisper` (on-device), `whisper.cpp`, Android `SpeechRecognizer` (when on-device mode is available) | **Yes** | No |
| Remote (privacy-reviewed) | Groq Whisper v3, OpenAI Whisper API, Deepgram | No | Yes — opt-in |
| Remote (BYO) | Any OpenAI-compatible STT endpoint configured by the user | No | Yes — opt-in |

The pipeline never auto-selects a remote provider. The user (or the
operator running the gateway) must set `allow_remote_stt: true` in
their config *and* configure provider credentials before the
gateway will even consider falling back to a remote engine.

## 2. Default behaviour

With no configuration:

- `VoiceIntakeConfig.stt_provider == "local"`.
- `allow_remote_stt == False`.
- `store_raw_audio == False`.
- `redact_secrets == True`.

The gateway uses whichever local provider is installed (the existing
`tools.voice_mode` module picks one). If no local provider is
available, the gateway returns a structured `stt_unavailable` error;
it does **not** silently retry against a remote endpoint.

## 3. Opting in to remote STT

The user opts in by either:

- Setting `voice.allow_remote_stt: true` in `~/.hermes/config.yaml`
  and configuring the provider's API key in `~/.hermes/.env`, or
- Toggling the *Allow cloud transcription* switch in the cockpit's
  *Settings → Voice* screen. The toggle writes the same persisted
  config value.

Both surfaces show the same first-time confirmation copy:

> Cloud transcription sends short audio clips of your spoken commands
> to {provider}. M.U.S.E. never streams continuous audio. Each utterance
> is sent as a single clip after a wake event or push-to-talk press,
> and the clip is discarded as soon as the transcript is returned.
> The transcript itself is stored locally under `~/.hermes/voice/`.

That copy is the source of truth — if the implementation drifts from
it, the doc is wrong and the change needs review.

## 4. What gets sent on the wire

When remote STT is on:

- **Each utterance** is sent as one short clip (≤ 30 s by default,
  bounded by the VAD silence trigger). No stream-the-mic socket.
- **Wake words** are detected entirely on-device — the wake clip is
  not forwarded.
- **No metadata beyond the audio** is sent. The pipeline does not
  attach user identifiers, device IDs, location, or contact lists to
  the STT request.
- **Provider-side retention** follows the chosen provider's
  documented policy. Operators choosing a remote provider are
  expected to review that policy before enabling it; the cockpit
  links to each provider's data-handling page from the toggle.

When remote STT is off (the default):

- No audio leaves the device.

## 5. What gets stored locally

For every intake (independent of which STT tier produced the
transcript):

- `voice/transcript.txt` — redacted, plain UTF-8 text.
- `voice/plain-english-confirmation.md` — the read-back the user was
  asked to confirm.
- `voice/approval-state.json` — terminal record (`approved`,
  `cancelled`, `expired`), including the confirmation phrase.
- `voice/intake.json` — diagnostics blob the cockpit uses for the
  "Review last voice intake" screen.

Raw audio is **not** stored unless `store_raw_audio` is explicitly
set to `true`. Driving-mode config forces `store_raw_audio = False`
in `VoiceIntakeConfig.__post_init__` — even a caller that tries to
set it true is overridden.

If `store_raw_audio` is enabled in a non-driving mode, the captured
WAV is written to `voice/audio.wav` inside the same folder. The
cockpit shows a banner whenever raw audio is being kept so the user
sees, every time they enable it, that the recording is on disk.

## 6. Redaction

`voice_models.redact_transcript` runs before the transcript hits
disk. It replaces likely API keys, bearer tokens, AWS access keys,
and password-style assignments with `[REDACTED]`. The patterns are
conservative — they prefer to over-redact rather than leak. The
pipeline marks the transcript as `redacted=True` whenever the
substitution actually changed the text so callers can show a
"redacted secrets" hint in the cockpit.

Redaction is on by default in every mode. Driving mode pins it on.
The toggle exists only so a non-driving user transcribing a long
note can opt out for that one session if their text genuinely
matches one of the patterns by coincidence.

## 7. Provider failure modes

| Failure | Behaviour |
|---------|-----------|
| Local provider not installed, remote not allowed | `stt_unavailable` error; cockpit shows install hint. |
| Local provider returns empty / hallucinated text | Same path as silence: read-back is "I did not hear anything to act on." and the intake is cancelled. |
| Remote provider returns 401 / 403 | Disable the provider for the session; cockpit prompts the user to re-auth. |
| Remote provider times out | Surface the timeout; do **not** retry. Voice retries should be user-initiated. |
| Remote provider returns text but the audio was clipped | Treat as a partial transcript: read-back acknowledges the cut-off and the user can retry. |

## 8. Tests and validation

`tests/test_voice_intake.py` exercises:

- The default config has `stt_provider == "local"`,
  `allow_remote_stt == False`, `store_raw_audio == False`.
- Driving-mode config forces `store_raw_audio` and `redact_secrets`
  regardless of caller input.
- Redaction replaces API-key-shaped strings and bearer tokens with
  `[REDACTED]` and marks the transcript as redacted.

End-to-end remote-STT tests live alongside the audio-stack tests
(`tests/hermes_cli/test_voice_wrapper.py` and friends) — they are
out of scope for the intake pipeline.

## 9. See also

- `docs/voice/voice-first-architecture.md` — overall pipeline.
- `docs/voice/driving-mode-safety.md` — why driving mode pins the
  conservative defaults.
- `tools/voice_mode.py` — the local audio + transcription stack.
- `hermes_cli/voice.py` — the gateway wrapper that drives the local
  recorder.
