"""Model-backed eval runner (EVAL-1, live).

Wires the eval harness's model-dependent cases to a real model call over the
OpenAI-compatible interface Hermes already uses (`agent/auxiliary_client.py`
loads the same `openai` client). The runner is injectable for tests and
env-configured for real use; it only spends when an owner runs it with real
credentials.

A runner has the shape ``Callable[[str], dict]`` and returns
``{"text": str, "name": str|None, "arguments": dict|None}`` so the harness's
``tool_call_correctness`` case can inspect a tool call when the model emits one.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

Runner = Callable[[str], dict]


def _parse_response(resp: Any) -> dict:
    """Normalize an OpenAI-style chat completion into the harness runner shape."""
    out: dict = {"text": "", "name": None, "arguments": None}
    try:
        choice = resp.choices[0]
        msg = choice.message
        out["text"] = getattr(msg, "content", None) or ""
        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:
            fn = tool_calls[0].function
            out["name"] = getattr(fn, "name", None)
            raw_args = getattr(fn, "arguments", None)
            if isinstance(raw_args, str):
                try:
                    out["arguments"] = json.loads(raw_args)
                except ValueError:
                    out["arguments"] = {"_raw": raw_args}
            elif isinstance(raw_args, dict):
                out["arguments"] = raw_args
    except (AttributeError, IndexError, TypeError) as err:
        logger.debug("[evals] could not parse model response: %s", err)
    return out


def build_model_runner(
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    client: Any = None,
    tools: Optional[list] = None,
) -> Runner:
    """Build a runner that calls a real model.

    ``client`` may be injected (tests / a pre-configured client). Otherwise an
    OpenAI-compatible client is constructed from the arguments or the
    ``HERMES_EVAL_MODEL`` / ``HERMES_EVAL_BASE_URL`` / ``HERMES_EVAL_API_KEY``
    (falling back to ``OPENAI_*``) environment. Raises ``RuntimeError`` only when
    actually invoked without a usable client/key — building is always safe.
    """
    resolved_model = model or os.environ.get("HERMES_EVAL_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    resolved_base = base_url or os.environ.get("HERMES_EVAL_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    resolved_key = api_key or os.environ.get("HERMES_EVAL_API_KEY") or os.environ.get("OPENAI_API_KEY")

    def _client():
        if client is not None:
            return client
        if not resolved_key:
            raise RuntimeError(
                "no API key for eval runner — set HERMES_EVAL_API_KEY (or pass client=...)"
            )
        # Reuse the same OpenAI client the rest of Hermes loads.
        from agent.auxiliary_client import _load_openai_cls

        openai_cls = _load_openai_cls()
        kwargs: dict[str, Any] = {"api_key": resolved_key}
        if resolved_base:
            kwargs["base_url"] = resolved_base
        return openai_cls(**kwargs)

    def runner(prompt: str) -> dict:
        cli = _client()
        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        if tools:
            kwargs["tools"] = tools
        resp = cli.chat.completions.create(**kwargs)
        return _parse_response(resp)

    return runner
