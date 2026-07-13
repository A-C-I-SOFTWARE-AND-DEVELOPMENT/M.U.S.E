# Sprint 8 — Voice-First Duplex Android/Gateway Loop

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Make voice the primary interaction mode: phone-recorded audio goes to Hermes, Hermes responds with streamed speech, and approvals can be handled by voice with safeguards.

## Target flow

```text
User holds mic on Android
  -> audio chunk stream/upload
  -> gateway STT route
  -> Hermes chat/job command
  -> streaming text response
  -> TTS synthesis
  -> audio stream back to Android
  -> transcript + response stored as redacted events
```

## Files likely touched

- `tools/voice_mode.py`
- `tools/transcription_tools.py`
- `tools/tts_tool.py`
- `hermes_cli/voice.py`
- `gateway/platforms/api_server.py`
- Android `voice/` package new
- Android UI mic components
- Android audio playback service
- tests for voice API boundaries

## Parallel agent lanes

| Lane | Agent | Branch | Mission |
|---|---|---|---|
| A | Voice Backend Agent | `sprint/8-voice-backend` | Extract non-CLI voice service for STT/TTS request handling. |
| B | Gateway Agent | `sprint/8-audio-routes` | Add audio upload/stream routes and transcript events. |
| C | Android Voice Agent | `sprint/8-android-voice` | Implement mic capture, upload, playback, interruption. |
| D | Approval Voice Agent | `sprint/8-voice-approvals` | Add voice yes/no flow with confirmation phrase safeguards. |
| E | Privacy Agent | `sprint/8-voice-privacy` | Define storage, redaction, retention, no always-on default. |
| F | QA Agent | `sprint/8-voice-tests` | Mock STT/TTS tests and Android state tests. |
| G | Reviewer Agent | `sprint/8-review` | Review privacy, latency, and approval safety. |

## Voice API

```text
POST /v1/cockpit/voice/transcribe
POST /v1/cockpit/voice/command
GET  /v1/cockpit/voice/responses/{id}/audio
POST /v1/cockpit/voice/approval/{id}/confirm
```

For MVP, use upload chunks or complete audio files before WebRTC. WebRTC can be a later optimization.

## Privacy rules

- No always-on wake word in first release.
- Push-to-talk first.
- User can disable transcript storage.
- Audio retention defaults to delete after transcription.
- Transcript events must be redacted.
- Voice approvals require explicit confirmation and phrase matching for high-risk actions.
- Never approve remote execution from a single ambiguous utterance.

## Latency targets

- Push-to-talk starts capture immediately.
- Partial transcript visible if streaming STT exists; otherwise show processing state.
- TTS starts as soon as enough response text is available, if provider supports it.
- User can interrupt playback and redirect.

## Acceptance criteria

- Android can record and send voice command to gateway.
- Gateway returns transcript and agent response.
- Android plays TTS response.
- Voice command can start a job.
- Voice approval works only after confirmation safeguards.
- Audio is not retained by default.
- Offline/missing STT provider fails visibly and recoverably.

## Reviewer prompt

```text
Review voice loop. Check audio retention, transcript redaction, approval spoofing, accidental always-on behavior, interruption handling, and missing provider fallback. Verify voice approval cannot bypass the decision engine.
```

## Definition of done

Hermes is usable from a phone by voice for creating jobs, tracking them, and handling safe approvals.
