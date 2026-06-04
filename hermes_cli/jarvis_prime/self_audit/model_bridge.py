"""Stdlib OpenAI-compatible model bridge for the live self-audit lane.

Turns a prompt into a completion via any OpenAI-compatible
``/chat/completions`` endpoint (OpenAI, OpenRouter, NovitaAI, NIM, a local
llama.cpp server, …), configured entirely by environment:

- ``SELF_AUDIT_MODEL_BASE_URL`` — e.g. ``https://api.openai.com/v1``
- ``SELF_AUDIT_MODEL_NAME``     — e.g. ``gpt-4o-mini`` / ``anthropic/claude-…``
- ``SELF_AUDIT_MODEL_KEY``      — API key (omit for keyless local servers)

stdlib-only (``urllib``), so the live audit runs in CI without installing the
full agent stack. :func:`main` reads a prompt on stdin and writes the
completion to stdout, so it can also serve as ``HERMES_SELF_AUDIT_MODEL_CMD``.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Optional

ENV_BASE_URL = "SELF_AUDIT_MODEL_BASE_URL"
ENV_MODEL = "SELF_AUDIT_MODEL_NAME"
ENV_KEY = "SELF_AUDIT_MODEL_KEY"


def is_configured() -> bool:
    """True if a base URL and model name are both set in the environment."""

    return bool(os.environ.get(ENV_BASE_URL) and os.environ.get(ENV_MODEL))


def build_request(
    prompt: str,
    *,
    base_url: str,
    model: str,
    api_key: Optional[str] = None,
    temperature: float = 0.0,
) -> tuple[str, bytes, dict[str, str]]:
    """Build the (url, body, headers) for a chat-completions POST."""

    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return url, data, headers


def parse_completion(body: str) -> str:
    """Extract the assistant message text from a chat-completions response."""

    obj = json.loads(body)
    return obj["choices"][0]["message"]["content"]


def complete(prompt: str, *, timeout: int = 120) -> str:
    """Send ``prompt`` to the configured endpoint and return the completion."""

    base_url = os.environ.get(ENV_BASE_URL)
    model = os.environ.get(ENV_MODEL)
    if not base_url or not model:
        raise RuntimeError(
            f"set {ENV_BASE_URL} and {ENV_MODEL} to use the live model bridge"
        )
    url, data, headers = build_request(
        prompt, base_url=base_url, model=model, api_key=os.environ.get(ENV_KEY)
    )
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return parse_completion(body)


def main(argv: Optional[list[str]] = None) -> int:
    """stdin (prompt) -> stdout (completion); for HERMES_SELF_AUDIT_MODEL_CMD."""

    prompt = sys.stdin.read()
    if not is_configured():
        print(f"error: {ENV_BASE_URL} / {ENV_MODEL} not set", file=sys.stderr)
        return 2
    try:
        sys.stdout.write(complete(prompt))
    except Exception as exc:  # surface the failure to the caller, don't crash
        print(f"error: model bridge failed: {exc}", file=sys.stderr)
        return 1
    return 0


__all__ = [
    "ENV_BASE_URL",
    "ENV_MODEL",
    "ENV_KEY",
    "is_configured",
    "build_request",
    "parse_completion",
    "complete",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
