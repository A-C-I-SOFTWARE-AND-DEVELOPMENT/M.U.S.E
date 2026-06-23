# ChatGPT manual-handoff worker

The ChatGPT handoff worker is the muse adapter for **manual** paste
into a user's own ChatGPT session — web or mobile app, signed in with
their own subscription. It ships as
[`hermes_cli/workers/chatgpt_handoff.py`](../../../hermes_cli/workers/chatgpt_handoff.py)
and is the canonical example of a *handoff-only* worker: there is no
execution path, ever.

## Why handoff-only

ChatGPT does not expose a headless CLI that runs against the user's
own paid subscription. Driving the web UI, scraping cookies, or
proxying through a personal account would all break OpenAI's terms
of service and violate the user's trust. So this worker does what the
Android local orchestrator already does today (see
[`docs/hermes-local-orchestrator.md`](../../hermes-local-orchestrator.md)):
prepares a structured prompt, surfaces it to the user, and waits for
the user to drop the reply back into the workspace.

## When to use it

Reach for ChatGPT handoff when the task is one of:

- **Product / UX review** — turn an engineering brief into user-visible
  language, surface UX trade-offs, propose copy, audit error states.
- **Strategy** — second-opinion on direction, scope, sequencing,
  go/no-go calls before committing engineering effort.
- **Final pre-merge review** — fresh eyes on a diff after the
  engineer has stared at it too long.

Reach for a different worker when the task wants headless execution
(use Codex, Aider, or Goose), git-native patching (Aider), or
extension-driven local automation (Goose).

## What this worker does

1. Writes a worker-tuned ``prompt.md`` to the workspace, framed for
   product/UX/strategy/final-review work and explicitly telling
   ChatGPT this is a manual paste with no surrounding automation.
2. Writes ``status.json`` with ``status="handoff_required"`` and a
   list of expected artifacts the user will drop back.
3. Surfaces a **paste instruction** as the "handoff command" — there
   is nothing to ``$ run``; the field contains human-readable steps.
4. Provides ``collect_artifacts`` so the orchestrator can pick up
   whatever the user saved back into the workspace.
5. Provides a ``score`` stub so the scoring layer treats this worker
   like any other; a real judge can replace the stub later.

## What it never does

- Detects a CLI (there is none).
- Spawns a subprocess.
- Opens a browser.
- Reads cookies, browser storage, or another app's credentials.
- Calls an OpenAI API endpoint to impersonate the user's
  subscription.
- Falls back to any of the above if "execution" is requested. The
  ``run()`` signature does not accept an ``execute`` keyword — there
  is no automation path to opt into.

## Workspace layout

```
workspace/
├── prompt.md        # always written — the body the user pastes
├── status.json      # always written — machine-readable handoff state
├── response.md      # user-supplied — ChatGPT's reply
└── notes.md         # optional — reviewer's own notes
```

The response filename is configurable via
``ChatGPTHandoffConfig.response_filename``; both ``status.json`` and
the handoff command reflect the override so the user pastes into the
right file.

## Lifecycle

```
workers.chatgpt_handoff.run(task, workspace, config=...)
  │
  ├─ ensure_workspace(workspace)
  ├─ render_prompt(task, config=cfg)   ➜ workspace/prompt.md
  ├─ build_handoff_command(workspace, config=cfg)
  └─ _write_extended_status(...)       ➜ workspace/status.json
        with status="handoff_required"
                │
                ▼
  caller surfaces WorkerResult; user opens ChatGPT, pastes prompt.md,
  saves reply as response.md, optional notes.md alongside.

  later: workers.chatgpt_handoff.collect_artifacts(workspace, config=cfg)
         ➜ WorkerArtifacts (files, response_present, notes)
         workers.chatgpt_handoff.score(artifacts)
         ➜ WorkerScore stub
```

## Default handoff command

```text
# Manual handoff — no command to run.
# 1. Open your ChatGPT session (web or mobile app).
# 2. Paste the contents of /tmp/ws/prompt.md.
# 3. Save ChatGPT's reply as /tmp/ws/response.md.
```

When a ``deep_link`` is configured (e.g. a ChatGPT GPT URL), it
replaces the generic "your ChatGPT session" phrase so the user can
click straight through.

## Prompt shape

The prompt opens with the configured role framing
(``product/UX/strategy/final review`` by default) and asks for a
five-section reply in a fixed order so downstream tooling can parse
it:

1. **Recommendation** — one paragraph.
2. **Product / UX notes** — bullet list.
3. **Strategy notes** — bullet list.
4. **Final review checklist** — bullet list.
5. **Open questions** — bullet list (empty list is fine).

It also forbids destructive shell suggestions
(``rm -rf``, ``git reset --hard``, ``git push --force``) and tells
ChatGPT not to claim it ran anything — it is reasoning from text
only.

## Python API

```python
from pathlib import Path
from hermes_cli.workers import WorkerTask
from hermes_cli.workers.chatgpt_handoff import (
    ChatGPTHandoffConfig, run, collect_artifacts, score,
)

result = run(
    WorkerTask(
        title="Pre-merge review of the auth refactor",
        instructions="Strategic go/no-go plus UX notes for PR #1234.",
        files=["docs/auth-refactor.md", "app/auth.py"],
    ),
    workspace=Path("/tmp/hermes/chatgpt-001"),
    config=ChatGPTHandoffConfig(role="final review"),
)

print(result.handoff_command)   # paste instructions

# … user pastes prompt.md into ChatGPT, drops the reply into response.md …

artifacts = collect_artifacts(result.workspace)
verdict   = score(artifacts)
```

``ChatGPTHandoffConfig`` fields:

- ``role`` — short string describing the reviewer hat
  (``"product"``, ``"ux"``, ``"strategy"``, ``"final review"``, or
  the combined default).
- ``deep_link`` — optional URL the user should open to land in the
  right ChatGPT context (e.g. a custom GPT).
- ``response_filename`` — where the user saves ChatGPT's reply
  (default ``response.md``).

## Failure modes

| `WorkerStatus`        | When                                                                   |
| --------------------- | ---------------------------------------------------------------------- |
| `handoff_required`    | Always. The worker has no other terminal state.                        |

``command_available`` is always ``False`` so consumers do not assume
there is a binary to invoke. ``status.json`` is always written so the
dashboard can render the pending handoff.

## Score stub

``score()`` returns ``WorkerScore(value=0.0, confidence=0.0)`` while
the response file is missing, and ``WorkerScore(value=0.5,
confidence=0.1)`` once it appears. The placeholder mid-point lets
downstream code distinguish "still pending" from "human replied" even
before a real judge runs. Callers that have a judge available should
replace this stub with their own scoring pass.

Per-axis ``components`` passed in via the optional keyword are
clamped to ``[0.0, 1.0]`` and non-numeric values are coerced to
``0.0`` — the score layer never propagates noisy inputs.

## Limits

- The worker assumes the user can copy/paste between muse and
  ChatGPT. Air-gapped or read-only contexts will not benefit from
  this worker.
- We do not parse the response file ourselves. Downstream code is
  free to look for the five fixed section headings the prompt asks
  for, but the worker does not enforce that contract.
- The score stub is intentionally crude; do not use it as the only
  signal in a merge gate.
