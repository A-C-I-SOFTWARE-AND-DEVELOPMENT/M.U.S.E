# Voice-first user guide

Hermes is **voice-first** in the sense that you can drive every
orchestrated workflow by speaking. This guide is the plain-English
walkthrough: how voice capture works, how driving mode works
safely, how to keep audio on-device, and what to say when.

> The corresponding mobile app guide is
> [mobile/mobile-app-guide.md](../mobile/mobile-app-guide.md). This
> page is voice-specific; that one is the cockpit overall.

---

## What voice does (and doesn't)

Voice gives you a **hands-free input path** for the same agent the
CLI talks to. It does not change what the agent can do. A spoken
*"Audit this repo"* and a typed *"Audit this repo"* produce the
exact same job — same orchestrator, same phases, same ledger.

The voice layer adds:

- **Capture.** Hold-to-talk in the cockpit, push-to-talk on a desktop
  headset, voice-memo replies to a gateway DM (Telegram), wake-word
  on supported platforms.
- **Transcription (STT).** Server-side or on-device, configurable.
- **Speech output (TTS).** The agent's reply can be read back to you,
  with reasonable defaults and a strict cap in driving mode.
- **Driving mode.** A focused subset of the UI with motion-aware
  safety guardrails.

Everything else — model choice, profiles, orchestration, GitHub /
Supabase / Vercel integrations — is unchanged.

---

## How voice capture works

Three capture surfaces. All three end up as a normal Hermes turn on
the same backend.

### 1. Mobile cockpit (hold-to-talk)

1. Open the **Voice** tab.
2. Hold the mic button. The app records Opus audio (~32 kbps).
3. Release. The audio uploads to the gateway over TLS.
4. The gateway routes audio to the configured STT engine.
5. The transcript becomes the user's turn. The agent replies in
   text (and audio if TTS is enabled).

### 2. Telegram / Discord / WhatsApp voice memos

Send a voice memo to your Hermes bot DM exactly as you'd send one
to a human. The platform delivers it as an audio file; the gateway
transcribes it; the transcript becomes the turn. No app required.

### 3. Desktop / Termux push-to-talk

Some shells ship a push-to-talk wrapper:

```bash
hermes voice listen --device default --hotkey f9
```

Holding F9 captures, releasing submits. Same gateway endpoint.

### What about wake-words?

The mobile cockpit supports an **optional** wake word ("Hey Hermes"
by default, configurable). It is **off by default**. Once enabled,
the wake word arms a **single capture** — it does not stream the
mic continuously. After the capture completes, the wake-word listener
re-arms. No always-on cloud streaming.

If you want zero always-on listening, leave the wake word off and
use hold-to-talk only.

---

## STT — where transcription happens

Three options, configured under `voice.stt` in
`~/.hermes/config.yaml`:

```yaml
voice:
  stt:
    engine: whisper-local   # whisper-local | whisper-server | deepgram | groq | openai
    whisper_local:
      model: base.en        # or small.en / medium.en / large-v3
      device: cpu           # or cuda
    whisper_server:
      url: http://127.0.0.1:9000/v1/audio/transcriptions
    deepgram:
      api_key: ${DEEPGRAM_API_KEY}
    groq:
      api_key: ${GROQ_API_KEY}
    openai:
      api_key: ${OPENAI_API_KEY}
```

| Engine | Where audio goes | When to pick |
|--------|------------------|--------------|
| `whisper-local` | Stays on the backend host | Default. Fully local. ~1× realtime on a modern CPU. |
| `whisper-server` | A separate Whisper server (e.g. faster-whisper) | When the backend is a small VPS and Whisper is too slow there. |
| `deepgram` | Deepgram cloud | When you want lowest-latency cloud STT. |
| `groq` | Groq cloud | When you have a Groq key already. |
| `openai` | OpenAI cloud | When you have an OpenAI key already. |

> **Privacy choice.** If you don't want any audio leaving the backend
> host, use `whisper-local` or `whisper-server` (on your own
> infrastructure). The
> [private-local security guide](../security/private-local-security-guide.md)
> covers the full lockdown.

---

## TTS — when the agent speaks back

Off by default. Enable per-surface:

```yaml
voice:
  tts:
    enabled: true
    engine: elevenlabs      # elevenlabs | openai | piper | coqui
    voice: hermes-default
    cap_seconds: 60         # truncate longer replies to a summary
```

The driving-mode cap (below) overrides this with a stricter limit.
Hermes will choose a short-form summary path automatically when TTS
runs into the cap.

---

## Driving mode

Driving mode is a **focused subset of the UI** designed to be used
at a glance, with audio replacing visual prompts. Activated from the
cockpit or by voice command.

### Activate / deactivate

- *"Hey Hermes, start driving mode."*
- Cockpit → **Settings → Driving mode → On.**
- *"Hey Hermes, stop driving mode."*
- Cockpit → tap the lock icon at the top.

### What changes when it's on

1. **No HIGH-risk approvals.** Anything the policy gate would
   normally escalate (a PR open, a Vercel deploy, a Supabase
   migration, an outbound DM) is **automatically deferred** while
   driving mode is on. The cockpit shows the queue but does not
   prompt you. You review them after you stop.
2. **No keyboard.** Text input is hidden. The only inputs are the
   mic and a big red **Cancel** button.
3. **TTS is short-form.** Replies cap to ~30 seconds of speech (or
   the `voice.tts.driving_cap_seconds` value). Longer replies are
   compressed to a one-sentence summary plus *"full reply queued
   for review."*
4. **Wake-word is single-shot.** Even if you've enabled continuous
   wake-word elsewhere, driving mode forces single-shot.
5. **Critical-only notifications.** Push notifications for `failed`
   and `escalated` phases (the latter just queue, since they auto-
   defer) are suppressed unless they're marked `critical=true` by
   the orchestrator skill.

### The motion guardrail

If the phone's motion sensors stop reporting sustained motion
(thresholds in `voice.driving_mode.auto_off_after_stop_minutes`,
default 3 minutes), driving mode disables itself. You'll hear:
*"Driving mode off."*

The motion check exists because the dangerous failure mode is
*"forgot driving mode was on, made a real change two days later."*
The auto-off is the safety net for that.

### What's safe to do while driving

The intent of driving mode is **dictation and triage**, not
execution:

- *"Remind me when I get home: open the laptop and review the
  Auth refactor PR."* — recorded in memory, no external side effects.
- *"Open an issue on my-org/web saying onboarding is broken on iOS
  18."* — orchestrator queues an issue create. It will ask for
  approval after you stop driving.
- *"What's blocking my draft PRs?"* — pure read, TTS reads the
  summary.
- *"Start orchestrating: investigate the timeout in test_api.py."*
  — orchestrator runs, but any publishing phase queues for approval.

What is **not** safe while driving and the system enforces:

- *"Deploy to production."* — Vercel deploy is HIGH risk → queued.
- *"Merge the PR."* — GitHub merge is HIGH risk → queued.
- *"Delete the staging database."* — Supabase destructive → queued
  and probably refused outright by the policy.

---

## Voice command vocabulary

Spoken phrases the cockpit and gateway recognize as control commands
(matched after STT, before submitting as a turn):

| Phrase | Effect |
|--------|--------|
| *"Hey Hermes, start driving mode."* | Activates driving mode. |
| *"Hey Hermes, stop driving mode."* | Deactivates driving mode. |
| *"Hermes, cancel."* | Cancels the current capture before submission. |
| *"Hermes, cancel job."* | Cancels the most recent job. |
| *"Hermes, what's the status?"* | Reads back `hermes orchestrator status` summary. |
| *"Hermes, repeat that."* | Re-plays the last TTS reply. |
| *"Hermes, save that as a memory."* | Stores the previous turn as a memory entry. |
| *"Hermes, new conversation."* | Starts a fresh session (same as `/new` in chat). |
| *"Hermes, approve."* | Approves the topmost queued approval (only when not driving). |

Everything else after the wake word is treated as a normal prompt.

---

## Prompt examples for voice

Voice prompts work best when they sound like dictation, not chat.

| You say | What happens |
|---------|--------------|
| *"Summarize the GitHub notifications since this morning."* | Read-only summary, TTS reads it back. |
| *"Open an issue on `my-org/web`: onboarding broken on iOS 18, screenshot attached."* | Orchestrated job; orchestrator decomposes; you approve the issue create when you stop driving. |
| *"Remind me when I get home to merge the auth PR."* | Stored as a memory + a one-shot reminder. |
| *"What did I ship last week?"* | Reads from `github_assistant` history. |
| *"Start orchestrating: profile this repo's bundle size and propose a fix."* | Full orchestration; phases visible on the dashboard. |
| *"Deploy preview of the current feature branch."* | Queued for approval — Vercel deploy is HIGH risk. |

A pattern that works: lead with the verb. *"Summarize…",
"Open…", "Start orchestrating…", "Remember…", "Remind me…",
"Cancel…"*. The orchestrator does fine with prose, but it does
better with explicit verbs because the policy classifier reads
those keywords too.

---

## Privacy

Voice gets its own privacy considerations because audio is sensitive.

- **Where audio goes.** Whatever you set `voice.stt.engine` to. The
  default `whisper-local` keeps audio on the backend host. If you
  pick a cloud STT, audio bytes leave the host.
- **What stays after transcription.** By default the backend stores
  the transcript with the turn (for replay/audit) and **deletes the
  raw audio** within
  `voice.retention.raw_audio_minutes` (default 60). Set it to `0`
  to delete on transcription.
- **On the phone.** The app caches audio only during the upload. As
  soon as the gateway acks, the local file is deleted.
- **The wake word listener** (if on) processes audio entirely on
  the device. It never uploads until it has matched.

The full lockdown — wake word off, local STT only, audio
retention zero, no TTS — is documented in
[../security/private-local-security-guide.md](../security/private-local-security-guide.md).

---

## Disconnect recovery for voice

If you lose network mid-capture:

1. The cockpit holds the audio locally for up to 10 minutes.
2. On reconnect, it auto-uploads.
3. The backend transcribes and processes as if it had arrived
   immediately. If the prompt has already been duplicated (rare,
   from a manual retry), the gateway de-dupes by capture-id.

If you lose network mid-reply:

1. The agent keeps generating on the backend.
2. The reply lands in the conversation log.
3. On reconnect, the cockpit fetches and TTS reads the missed reply
   (unless you're in driving mode and the reply post-dates the
   driving-off transition).

If voice gives wrong transcripts repeatedly: switch STT engine. A
70-row config change with `voice.stt.engine` → another engine.
Restart the gateway and retry.

---

## Wake-word, optional and explicit

Off by default. Enable like:

```yaml
voice:
  wake_word:
    enabled: true
    phrase: "hey hermes"
    sensitivity: 0.6
    single_shot: true       # required in driving mode
```

The detector is an on-device model. It never leaves the phone. When
it matches, it arms a single capture, records ~10s (or until silence),
and uploads. Then it re-arms.

If you don't want any always-listening behavior, leave it off and
use hold-to-talk only — this is the default.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Hold-to-talk records but nothing happens | Gateway can't reach STT | Check `voice.stt` config; restart gateway. |
| Wrong transcript repeatedly | Wrong STT model size for the language / accent | Try `whisper-server` with `medium.en`, or switch to Deepgram for a noisy environment. |
| Driving mode won't disable on stop | Motion sensor permission off | Cockpit → **Settings → Permissions → Motion** → grant. |
| TTS is cut off mid-sentence | `voice.tts.cap_seconds` hit | Increase, or read the queued long-form reply after the drive. |
| Wake word triggers on TV ads | Sensitivity too high | Lower `voice.wake_word.sensitivity` to ~0.5. |
| Voice command isn't matched | Wake-word audio quality | Re-record the wake-word sample, increase sensitivity, or hold-to-talk instead. |
| Audio uploaded but no turn appears | Network drop mid-upload | The cockpit retries automatically; if not, restart the upload from **Voice → Failed captures**. |

For everything else, see
[../troubleshooting/hermes-orchestration-troubleshooting.md](../troubleshooting/hermes-orchestration-troubleshooting.md).

---

## See also

- [presence-mode.md](presence-mode.md) — JARVIS Presence Mode: the
  hands-free, avatar-over-the-launcher cockpit, the attention → wake →
  mic trigger fallback chain, gestures, and approval-by-voice.
- [mobile/mobile-app-guide.md](../mobile/mobile-app-guide.md) — the
  cockpit overall.
- [security/private-local-security-guide.md](../security/private-local-security-guide.md)
  — keeping voice fully on-device.
- [orchestration/getting-started.md](../orchestration/getting-started.md)
  — the underlying job model the voice path drives.
