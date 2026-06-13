"""Default edit providers — the autoresearch loop's built-in idea sources.

v1 shipped ``EditProvider`` as an injectable seam only (the skill-driven agent
proposes ideas, matching upstream's model). This module adds working defaults:

- :class:`CatalogEditProvider` — a deterministic, curated catalog of
  hyperparameter-block knob tweaks (drawn from the vendored README's guidance
  and program.md's own examples: LRs, warmdown, weight decay, window pattern,
  depth, device batch). It patches ONLY constants in the workspace
  ``train.py``'s hyperparameter block, validates the result parses, never
  repeats a tried idea, and skips ideas whose knobs no longer exist (e.g.
  renamed by a previous kept edit).
- :class:`LlmEditProvider` — wraps any ``(prompt) -> str`` runner (the Gemma
  runner, a frontier model, …) and asks it for a complete replacement
  ``train.py``; output is fenced-code-extracted and must ``ast.parse`` and
  still import the read-only harness, else the idea is discarded.
- :func:`default_edit_provider` — catalog first, then the LLM (when a runner
  is supplied); ``None`` when every source is exhausted, which ends the run
  with ``stopped_reason="edit_provider_exhausted"``.

Everything here is offline and deterministic except the optional LLM hook;
nothing imports torch.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from .engine import EditContext, EditProvider, ExperimentEdit


@dataclass(frozen=True)
class KnobIdea:
    """One catalog idea: set hyperparameter-block constants to new values."""

    description: str
    knobs: tuple[tuple[str, str], ...]  # (CONSTANT_NAME, new_value_repr)


# Drawn from the vendored README's small-platform guidance and program.md's
# example experiments. Ordered: cheap/safe single-knob ideas first.
DEFAULT_IDEAS: tuple[KnobIdea, ...] = (
    KnobIdea("raise Muon matrix LR to 0.06", (("MATRIX_LR", "0.06"),)),
    KnobIdea("lower Muon matrix LR to 0.02", (("MATRIX_LR", "0.02"),)),
    KnobIdea("raise embedding LR to 0.8", (("EMBEDDING_LR", "0.8"),)),
    KnobIdea("full-context attention everywhere", (("WINDOW_PATTERN", '"L"'),)),
    KnobIdea("shorter LR warmdown (0.4)", (("WARMDOWN_RATIO", "0.4"),)),
    KnobIdea("longer LR warmdown (0.7)", (("WARMDOWN_RATIO", "0.7"),)),
    KnobIdea("stronger cautious weight decay (0.3)", (("WEIGHT_DECAY", "0.3"),)),
    KnobIdea("weaker cautious weight decay (0.1)", (("WEIGHT_DECAY", "0.1"),)),
    KnobIdea("one layer deeper (DEPTH 9)", (("DEPTH", "9"),)),
    KnobIdea("one layer shallower (DEPTH 7)", (("DEPTH", "7"),)),
    KnobIdea(
        "halve device batch (64), same total batch",
        (("DEVICE_BATCH_SIZE", "64"),),
    ),
    KnobIdea("milder Adam beta1 (0.9)", (("ADAM_BETAS", "(0.9, 0.95)"),)),
    KnobIdea("lower scalar LR (0.25)", (("SCALAR_LR", "0.25"),)),
    KnobIdea(
        "smaller total batch (2**18) with shorter warmdown",
        (("TOTAL_BATCH_SIZE", "2**18"), ("WARMDOWN_RATIO", "0.4")),
    ),
)


def set_constant(source: str, name: str, value_repr: str) -> Optional[str]:
    """Set ``NAME = <value>`` in the hyperparameter block, keeping comments.

    Returns the new source, or None when the constant assignment isn't found
    (renamed/removed by a previous edit) or the edit would be a no-op.
    """

    pattern = re.compile(
        rf"^(?P<lhs>{re.escape(name)}\s*=\s*)(?P<value>[^#\n]*?)(?P<comment>\s*#.*)?$",
        re.MULTILINE,
    )
    match = pattern.search(source)
    if match is None:
        return None
    if match.group("value").strip() == value_repr:
        return None  # no-op edit
    replacement = f"{match.group('lhs')}{value_repr}{match.group('comment') or ''}"
    return source[: match.start()] + replacement + source[match.end() :]


def _parses(source: str) -> bool:
    try:
        ast.parse(source)
        return True
    except SyntaxError:
        return False


class CatalogEditProvider:
    """Deterministic knob-tweak ideas; never repeats, never emits broken code."""

    def __init__(self, ideas: Sequence[KnobIdea] = DEFAULT_IDEAS) -> None:
        self.ideas = tuple(ideas)

    def __call__(self, ctx: EditContext) -> Optional[ExperimentEdit]:
        train_path = Path(ctx.workspace) / "train.py"
        try:
            current = train_path.read_text(encoding="utf-8")
        except OSError:
            return None
        tried = {r.description for r in ctx.history}
        for idea in self.ideas:
            if idea.description in tried:
                continue
            edited: Optional[str] = current
            for knob, value_repr in idea.knobs:
                edited = set_constant(edited, knob, value_repr) if edited else None
                if edited is None:
                    break
            if edited is None or not _parses(edited):
                continue
            return ExperimentEdit(description=idea.description, train_py=edited)
        return None


_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


class LlmEditProvider:
    """Ask an LLM runner for a full replacement train.py; validate hard.

    The runner is any ``(prompt) -> str`` callable (Gemma runner, frontier
    model). Invalid output (no code, doesn't parse, drops the harness import)
    is discarded — the provider returns None and the chain moves on. Bounded
    by ``max_ideas`` so a chatty model can't extend the run on its own.
    """

    def __init__(self, runner: Callable[[str], str], *, max_ideas: int = 4) -> None:
        self.runner = runner
        self.max_ideas = max_ideas
        self._asked = 0

    def __call__(self, ctx: EditContext) -> Optional[ExperimentEdit]:
        if self._asked >= self.max_ideas:
            return None
        train_path = Path(ctx.workspace) / "train.py"
        try:
            current = train_path.read_text(encoding="utf-8")
        except OSError:
            return None
        history_lines = [
            f"- #{r.index} {r.description}: "
            f"{'val_bpb %.6f' % r.val_bpb if r.val_bpb is not None else r.status}"
            f" ({r.status})"
            for r in ctx.history[-10:]
        ]
        prompt = (
            "You are improving a single-file GPT pretraining script to minimize "
            "val_bpb (validation bits per byte, LOWER is better) under a fixed "
            "5-minute training budget. prepare.py is read-only; you may change "
            "anything in train.py (architecture, optimizer, hyperparameters).\n\n"
            f"Best val_bpb so far: {ctx.best_bpb}\n"
            "Recent experiments:\n" + "\n".join(history_lines) + "\n\n"
            "Reply with a one-line description on the first line, then the "
            "COMPLETE new train.py in a ```python fenced block.\n\n"
            "Current train.py:\n```python\n" + current + "\n```\n"
        )
        self._asked += 1
        try:
            reply = self.runner(prompt)
        except Exception:
            return None
        match = _FENCE_RE.search(reply or "")
        if match is None:
            return None
        candidate = match.group(1)
        if not _parses(candidate) or "from prepare import" not in candidate:
            return None
        if candidate.strip() == current.strip():
            return None
        description = (reply.strip().splitlines() or ["llm idea"])[0].strip()
        description = description.lstrip("#- ").strip() or "llm idea"
        return ExperimentEdit(description=f"llm: {description[:120]}", train_py=candidate)


class ChainEditProvider:
    """First provider with an idea wins; None when all are exhausted."""

    def __init__(self, providers: Sequence[EditProvider]) -> None:
        self.providers = tuple(providers)

    def __call__(self, ctx: EditContext) -> Optional[ExperimentEdit]:
        for provider in self.providers:
            edit = provider(ctx)
            if edit is not None:
                return edit
        return None


def default_edit_provider(
    llm_runner: Optional[Callable[[str], str]] = None,
    *,
    ideas: Sequence[KnobIdea] = DEFAULT_IDEAS,
    max_llm_ideas: int = 4,
) -> EditProvider:
    """The built-in idea source: curated catalog, then the optional LLM."""

    providers: list[EditProvider] = [CatalogEditProvider(ideas)]
    if llm_runner is not None:
        providers.append(LlmEditProvider(llm_runner, max_ideas=max_llm_ideas))
    return ChainEditProvider(providers)


__all__ = [
    "KnobIdea",
    "DEFAULT_IDEAS",
    "set_constant",
    "CatalogEditProvider",
    "LlmEditProvider",
    "ChainEditProvider",
    "default_edit_provider",
]
