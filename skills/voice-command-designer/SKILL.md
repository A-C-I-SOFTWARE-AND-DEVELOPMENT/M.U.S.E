---
name: voice-command-designer
description: Playbook for adding a new voice command without breaking the Hermes voice-first safety contract.
platforms: [linux, macos, android, termux]
---

# Voice command designer

Use this skill when you are adding a new voice-triggered behaviour to
Hermes — a new wake-word phrase, a new intent the read-back should
understand, or a new orchestrator action that should be reachable
from voice. The skill keeps you inside the safety envelope laid out
in `docs/voice/driving-mode-safety.md` and the pipeline contract in
`docs/voice/voice-first-architecture.md`.

## When to use

- You're tempted to add a regex to
  `hermes_cli/voice_models._INTENT_PATTERNS`.
- A reviewer asked for "this should also work hands-free".
- A user filed a feature request that starts with "Hermes should
  just …" and ends with an action.

## When not to use

- For changes to the *audio* stack (recording, TTS, beep cues) —
  that lives in `hermes_cli/voice.py` and `tools/voice_mode.py`.
- For changes to the orchestrator's job model — voice intake is a
  consumer of the orchestrator, not the place to redesign it.

## Steps

### 1. Write the phrase down before you write code

In one sentence, the user's spoken request. Include filler words
they would actually say ("uh", "okay so", "hey Hermes"). The voice
intake pipeline never sees "hey Hermes" — the wake engine strips it
— so write down what the transcript will actually contain.

### 2. Decide the intent

Pick exactly one of the existing intents from
`hermes_cli/voice_models.VOICE_INTENTS`. The seven intents cover:

- `capture_note` — passive, no orchestrator job is created.
- `create_job` — active, eligible for orchestrator submission.
- `query_status` — read-only; the answer is the read-back.
- `cancel` / `confirm` / `repeat` — only used inside step 4 of the
  pipeline.
- `unknown` — only as a last resort; in driving mode this degrades
  to `capture_note`.

**Default to `capture_note` if you can.** Adding actions to
`create_job` increases the safety surface area. A note that the user
can review later is almost always the safer first ship.

### 3. Add the regex *only if* the existing patterns miss it

Open `hermes_cli/voice_models.py` and check
`_INTENT_PATTERNS`. If a real user transcript would already match
the right intent (e.g. "build the release script" already matches
`create_job` via `build`), do not add a new pattern. The regex list
is ordered by specificity; adding one entry can shift another.

If you do add a pattern:

- Keep it a small, anchored, case-insensitive regex. No look-around,
  no backreferences.
- Add a test in `tests/test_voice_intake.py` that asserts both the
  positive case ("phrase X classifies as Y") and the negative case
  ("phrase X *no longer* classifies as the previous intent").

### 4. Write the read-back

`_summarize_for_readback` produces the spoken summary. The summary
must:

- Start with a verb describing what would happen.
- Mention the thing being acted on, not just the verb.
- Avoid jargon, IDs, or any token the user would not have spoken.
- Be one sentence. The TTS layer reads it aloud verbatim.
- For `create_job` / publish-style intents, end with "say yes to
  proceed or no to cancel" — `_compose_spoken_readback` already
  appends this; do not duplicate.

### 5. Decide the confirmation contract

If the new behaviour writes anything, communicates anything to a
third party, or spends money: it requires explicit confirmation.

| Action class | Confirmation in `push_to_talk` | Confirmation in `driving_capture` |
|--------------|-------------------------------|----------------------------------|
| Read-only (`query_status`) | None | None |
| Local capture (`capture_note`) | Implicit | Explicit "yes" |
| Create orchestrator job (`create_job`) | Explicit "yes" | Explicit "yes" |
| Publish / merge / deploy | Explicit "yes" | Explicit "yes" **plus** out-of-band confirmation after exiting driving mode (`DrivingSafetyVeto` enforces this) |

If you find yourself wanting to relax any cell in this table, file
an issue and reference `docs/voice/driving-mode-safety.md` §2 — the
non-negotiable invariants — so the review trail captures the ask.

### 6. Test the driving-mode degradation

Driving mode rewrites two things automatically:

- An `unknown` intent becomes `capture_note`.
- A long transcript is trimmed for the read-back.

Add a test in `tests/test_voice_intake.py` that demonstrates the new
phrase still does the right thing in driving mode. Run:

```bash
python -m pytest tests/test_voice_intake.py -q
```

### 7. Update the docs

Add a one-line entry to the intent table in
`docs/voice/voice-first-architecture.md` §5. If the new behaviour
changes the publish gate, add a row to
`docs/voice/driving-mode-safety.md` §5.

### 8. Don't ship a wake-word change without the safety review

New wake-word phrases (and any wake-engine change) trigger a
safety review because they change the threshold for *when* Hermes
starts listening. Open a PR with `voice-safety` in the title and
copy `docs/voice/driving-mode-safety.md` §2 into the PR description
so reviewers see the invariants their change is being measured
against.

## Common mistakes (do not do these)

- Adding an LLM-based intent classifier "just for ambiguous cases".
  The safety story relies on the classifier being auditable; an LLM
  call also makes the read-back too slow to be usable hands-free.
- Adding a "skip the read-back if the user has already confirmed
  this command type once" affordance. The read-back is per-utterance,
  not per-command-type. Don't cache confirmations.
- Treating silence as a yes. Silence is `expired`, which is treated
  as a cancel in driving mode and as "still waiting" elsewhere.
- Storing the raw audio "just for debugging". Diagnostics live in
  `voice/intake.json`; the WAV must be released by the recorder.
- Adding a new spoken affirmative ("sure", "of course"). The
  affirmative list is short on purpose; "sure" is too easy to mis-hear
  in a noisy car.

## See also

- `docs/voice/voice-first-architecture.md`
- `docs/voice/driving-mode-safety.md`
- `docs/voice/stt-provider-policy.md`
- `hermes_cli/voice_models.py`
- `hermes_cli/voice_intake.py`
- `tests/test_voice_intake.py`
