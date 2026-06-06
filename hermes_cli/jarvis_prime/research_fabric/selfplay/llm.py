"""Live LLM solver / mutator — the drop-in behind the self-play interfaces.

The self-play loop (`solve(task) -> code`) and the evolutionary loop
(`propose_variants(code) -> [code]`) are model-agnostic; this module supplies the
real implementation backed by any provider callable ``Provider = (prompt) -> text``.

:func:`load_openai_provider` wires an **OpenAI-compatible** endpoint, which covers
vLLM, Ollama (``/v1``), OpenRouter, NovitaAI, NIM, etc. — so a real Qwen3-Coder /
DeepSeek backend plugs in via configuration, not code. Tests inject a fake
provider, so no network is required and the offline reference path keeps working.

Correctness is still enforced downstream by the executable verifier — a model's
output is a *candidate*, never trusted on its own.
"""

from __future__ import annotations

import os
import re
from typing import Callable, Optional

from ..verifier.algorithms import AlgorithmTask

# A provider turns a prompt into a completion string.
Provider = Callable[[str], str]

_CODE_FENCE = re.compile(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    """Pull the first fenced code block, or fall back to the stripped text."""

    if not text:
        return ""
    m = _CODE_FENCE.search(text)
    if m:
        return m.group(1).strip() + "\n"
    return text.strip() + "\n"


def load_openai_provider(
    model: str,
    *,
    base_url: Optional[str] = None,
    api_key_env: str = "OPENAI_API_KEY",
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> Provider:
    """Build a Provider against any OpenAI-compatible server (vLLM/Ollama/etc.).

    ``base_url`` defaults to ``$OPENAI_BASE_URL``. Raises ``RuntimeError`` if the
    ``openai`` package is unavailable so callers fail loudly rather than silently.
    """

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "openai package not available; install it or inject a Provider directly"
        ) from exc

    client = OpenAI(
        base_url=base_url or os.environ.get("OPENAI_BASE_URL"),
        api_key=os.environ.get(api_key_env, "not-needed-for-local"),
    )

    def provider(prompt: str) -> str:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    return provider


def _solve_prompt(task: AlgorithmTask) -> str:
    examples = "\n".join(
        f"  solve(*{c.args!r}) == {c.expected!r}" for c in task.public_cases
    )
    return (
        f"Write a single Python function named `{task.entrypoint}` that solves:\n"
        f"{task.prompt}\n\n"
        f"It must satisfy these examples:\n{examples}\n\n"
        f"Return ONLY the function in a ```python code block, no prose."
    )


def _mutate_prompt(code: str) -> str:
    return (
        "Improve the following Python function to be more efficient (fewer "
        "operations) while keeping identical behavior. Return ONLY the rewritten "
        "function in a ```python code block, no prose.\n\n"
        f"```python\n{code}```"
    )


class LLMSolver:
    """Implements ``solve(task) -> code`` via a Provider."""

    def __init__(self, provider: Provider) -> None:
        self._provider = provider

    def __call__(self, task: AlgorithmTask) -> str:
        return extract_code(self._provider(_solve_prompt(task)))


class LLMMutator:
    """Implements ``propose_variants(code) -> [code]`` via a Provider."""

    def __init__(self, provider: Provider, *, n: int = 1) -> None:
        self._provider = provider
        self._n = max(1, n)

    def __call__(self, code: str) -> list[str]:
        out: list[str] = []
        for _ in range(self._n):
            variant = extract_code(self._provider(_mutate_prompt(code)))
            if variant:
                out.append(variant)
        return out


__all__ = [
    "Provider",
    "extract_code",
    "load_openai_provider",
    "LLMSolver",
    "LLMMutator",
]
