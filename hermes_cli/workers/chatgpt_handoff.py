"""ChatGPT manual-handoff worker adapter.

ChatGPT does not expose a usable headless CLI on the user's own paid
subscription, so this worker is **always** a handoff: it materializes a
structured prompt the user copies into their existing ChatGPT session
(web or mobile app) — exactly the same pattern the Android local
orchestrator uses today (see ``docs/hermes-local-orchestrator.md``).

There is no execution path. The adapter:

1. Never tries to detect a ``chatgpt`` binary (none ships).
2. Writes a worker-tuned ``prompt.md`` into the workspace.
3. Writes ``status.json`` with ``status="handoff_required"``.
4. Surfaces a copy/paste instruction as the "handoff command" — there
   is no shell command to run, just a human action.
5. Provides a :func:`score` stub for the orchestrator's scoring layer;
   ChatGPT artifacts are reviewed by humans, not auto-scored.

The framing of the prompt deliberately leans on the *roles* ChatGPT
is best suited for in a Hermes flow:

* **Product / UX** — turn an engineering brief into user-visible
  language, surface UX trade-offs, propose copy.
* **Strategy** — second-opinion on direction, scope, sequencing,
  go/no-go calls.
* **Final review** — pre-merge review focused on what an engineer
  might miss after staring at the diff too long.

No subscription is automated. No cookies are scraped. No browser is
driven. The loop is closed by the user pasting Hermes' prompt into
their own ChatGPT session and returning with the response.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional

from hermes_cli.workers.base import (
    WorkerArtifacts,
    WorkerResult,
    WorkerScore,
    WorkerStatus,
    WorkerTask,
    ensure_workspace,
    render_acceptance_block,
    render_context_block,
    render_files_block,
    write_prompt,
    write_status,
)

WORKER_NAME = "chatgpt-handoff"

# Default role framing. Callers can override per invocation via
# ``ChatGPTHandoffConfig.role``.
DEFAULT_ROLE = "product/UX/strategy/final review"

# Filenames the user is asked to drop back into the workspace so the
# orchestrator can collect the human-mediated response.
RESPONSE_FILENAME = "response.md"
NOTES_FILENAME = "notes.md"


@dataclass(frozen=True)
class ChatGPTHandoffConfig:
    """Per-invocation knobs for the ChatGPT handoff worker.

    Attributes:
        role: Short description of the reviewer role we want ChatGPT to
            adopt. Defaults to ``"product/UX/strategy/final review"``;
            callers can narrow it (e.g. ``"strategy"`` or
            ``"final review"``) when the task is clearly one of the
            sub-roles.
        deep_link: Optional URL the user can click to open ChatGPT in
            the right context (e.g. ``https://chat.openai.com/``). The
            adapter never *opens* the URL itself — it's surfaced as
            part of the handoff instructions so the user can act on it.
        response_filename: Where the user should save ChatGPT's reply
            inside the workspace. Defaults to ``response.md``.
    """

    role: str = DEFAULT_ROLE
    deep_link: Optional[str] = None
    response_filename: str = RESPONSE_FILENAME


def render_prompt(
    task: WorkerTask,
    *,
    config: Optional[ChatGPTHandoffConfig] = None,
) -> str:
    """Build the worker-tuned ``prompt.md`` body for ChatGPT handoff.

    The prompt explicitly tells ChatGPT this is a manual paste from a
    larger orchestration system, asks for a product/UX/strategy/review
    framing, and requests a structured response so Hermes can read the
    answer back.
    """
    cfg = config or ChatGPTHandoffConfig()
    title = task.title.strip() or "Untitled task"
    instructions = task.instructions.strip() or "(no instructions provided)"
    role = cfg.role.strip() or DEFAULT_ROLE
    body = (
        f"# {title}\n\n"
        f"You are acting as ChatGPT in a **{role}** capacity for the "
        "muse orchestrator. A human is pasting this prompt into your "
        "session manually — there is no automation around your reply, "
        "so be explicit and self-contained. Lead with the answer, then "
        "show your reasoning.\n\n"
        "## Task\n"
        f"{instructions}\n"
        + render_files_block(task.files)
        + render_context_block(task.context)
        + render_acceptance_block(task.acceptance_criteria)
        + "\n## What we want from you\n"
        "- A clear top-line recommendation in the first paragraph.\n"
        "- Product/UX considerations a code-focused agent might miss\n"
        "  (user-visible copy, error states, accessibility, naming).\n"
        "- Strategic trade-offs: scope, sequencing, what to defer.\n"
        "- A final-review checklist the engineer should run through\n"
        "  before merging.\n"
        "- Open questions, flagged explicitly — do not paper over\n"
        "  ambiguity.\n\n"
        "## Response format\n"
        "Return a single Markdown document with these sections in\n"
        "this order so the orchestrator can parse it:\n\n"
        "1. **Recommendation** — one paragraph.\n"
        "2. **Product / UX notes** — bullet list.\n"
        "3. **Strategy notes** — bullet list.\n"
        "4. **Final review checklist** — bullet list.\n"
        "5. **Open questions** — bullet list (empty list is fine).\n\n"
        "## Guardrails\n"
        "- Do not invent repository facts. If you need code we did not\n"
        "  show you, say so under *Open questions* instead of guessing.\n"
        "- Do not propose destructive shell commands\n"
        "  (``rm -rf``, ``git reset --hard``, ``git push --force``).\n"
        "- Do not claim to have run anything — you are reasoning from\n"
        "  the text above, nothing else.\n"
        "- If the task is ambiguous, ask one focused question at the\n"
        "  top of *Open questions* and answer conservatively otherwise.\n"
    )
    return body


def build_handoff_command(
    workspace: Path,
    *,
    config: Optional[ChatGPTHandoffConfig] = None,
) -> str:
    """Return a copy/paste instruction (there is no CLI to invoke)."""
    cfg = config or ChatGPTHandoffConfig()
    prompt_path = (workspace / "prompt.md").as_posix()
    response_path = (workspace / cfg.response_filename).as_posix()
    target = cfg.deep_link or "your ChatGPT session (web or mobile app)"
    return (
        f"# Manual handoff — no command to run.\n"
        f"# 1. Open {target}.\n"
        f"# 2. Paste the contents of {prompt_path}.\n"
        f"# 3. Save ChatGPT's reply as {response_path}."
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_extended_status(
    workspace: Path,
    result: WorkerResult,
    *,
    config: ChatGPTHandoffConfig,
) -> Path:
    """Persist status.json with ChatGPT-handoff specific extras."""
    payload = result.to_status_dict()
    payload["role"] = config.role
    payload["response_filename"] = config.response_filename
    payload["deep_link"] = config.deep_link
    payload["expected_artifacts"] = [
        "prompt.md",
        "status.json",
        config.response_filename,
        NOTES_FILENAME,
    ]
    payload["handoff_instructions"] = (
        "Paste prompt.md into your ChatGPT session, then save the "
        f"reply as {config.response_filename} in this workspace. "
        f"Optional reviewer notes go in {NOTES_FILENAME}."
    )
    payload["created_at"] = _now_iso()
    status_path = workspace / "status.json"
    status_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return status_path


def run(
    task: WorkerTask,
    workspace: Path,
    *,
    config: Optional[ChatGPTHandoffConfig] = None,
) -> WorkerResult:
    """Prepare a ChatGPT manual-handoff workspace.

    There is no ``execute`` flag — ChatGPT cannot be driven headlessly
    against a user's own subscription, and we will not invent a way to
    do so. The worker always returns ``WorkerStatus.HANDOFF_REQUIRED``
    after writing ``prompt.md`` and ``status.json``.
    """
    cfg = config or ChatGPTHandoffConfig()
    workspace = ensure_workspace(workspace)

    prompt_body = render_prompt(task, config=cfg)
    prompt_path = write_prompt(workspace, prompt_body)
    handoff_command = build_handoff_command(workspace, config=cfg)

    result = WorkerResult(
        worker=WORKER_NAME,
        status=WorkerStatus.HANDOFF_REQUIRED,
        workspace=workspace,
        prompt_path=prompt_path,
        status_path=workspace / "status.json",
        # No CLI to detect — we set this False so consumers know there
        # is nothing to invoke, only something to paste.
        command_available=False,
        handoff_command=handoff_command,
    )
    result.status_path = _write_extended_status(workspace, result, config=cfg)
    return result


# ── artifact collection ───────────────────────────────────────────────


_ARTIFACT_FILENAMES: tuple[str, ...] = (
    "prompt.md",
    "status.json",
    RESPONSE_FILENAME,
    NOTES_FILENAME,
)


def collect_artifacts(
    workspace: Path,
    *,
    config: Optional[ChatGPTHandoffConfig] = None,
) -> WorkerArtifacts:
    """Gather whatever the user dropped back into ``workspace``.

    Looks for ``prompt.md``, ``status.json``, the configured response
    filename, and ``notes.md``. Missing files are silently omitted —
    handoffs frequently come back with only the response file.
    """
    cfg = config or ChatGPTHandoffConfig()
    found: list[str] = []
    notes_parts: list[str] = []

    for name in _ARTIFACT_FILENAMES + (cfg.response_filename,):
        candidate = workspace / name
        if candidate.is_file() and str(candidate) not in found:
            found.append(str(candidate))

    response_path = workspace / cfg.response_filename
    if not response_path.is_file():
        notes_parts.append(
            f"No {cfg.response_filename} found yet — handoff still pending."
        )

    return WorkerArtifacts(
        files=tuple(found),
        workspace_path=str(workspace),
        notes=" ".join(notes_parts),
        details={
            "response_filename": cfg.response_filename,
            "response_present": response_path.is_file(),
        },
    )


# ── score stub ────────────────────────────────────────────────────────


def score(
    artifacts: WorkerArtifacts,
    *,
    components: Optional[Mapping[str, float]] = None,
) -> WorkerScore:
    """Return a stub :class:`WorkerScore` for a handoff workspace.

    Auto-scoring a ChatGPT reply requires running another model over
    it; that's a downstream concern. The stub returns:

    * ``0.0`` with ``confidence=0.0`` when the response file is missing
      (the handoff is still pending — there is nothing to score).
    * ``0.5`` with ``confidence=0.1`` when the response file exists
      (a placeholder mid-point so the scoring layer can tell "human
      replied" from "still pending"). Callers that have a real judge
      should replace this with their own score.

    Pass ``components`` to merge per-axis self-reports (e.g. from a
    judge that already ran). Unknown axes are clamped to [0.0, 1.0].
    """
    response_present = bool(artifacts.details.get("response_present"))
    if not response_present:
        return WorkerScore(
            value=0.0,
            confidence=0.0,
            rationale="ChatGPT handoff still pending — no response file yet.",
            components=dict(_clamp_components(components or {})),
        )
    return WorkerScore(
        value=0.5,
        confidence=0.1,
        rationale=(
            "Stub score: human reply received but not auto-judged. "
            "Replace with a downstream judge score for a real value."
        ),
        components=dict(_clamp_components(components or {})),
    )


def _clamp_components(components: Mapping[str, float]) -> Iterable[tuple[str, float]]:
    for axis, raw in components.items():
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = 0.0
        yield axis, max(0.0, min(1.0, value))


__all__ = [
    "ChatGPTHandoffConfig",
    "DEFAULT_ROLE",
    "NOTES_FILENAME",
    "RESPONSE_FILENAME",
    "WORKER_NAME",
    "build_handoff_command",
    "collect_artifacts",
    "render_prompt",
    "run",
    "score",
]
