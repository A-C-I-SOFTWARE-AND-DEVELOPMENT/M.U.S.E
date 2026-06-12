"""Minimal stdlib client for llama-server's NATIVE ``/completion`` API.

The template fast path needs llama.cpp features the OpenAI-compatible surface
(and Ollama) do not expose: per-request GBNF ``grammar``, slot pinning via
``id_slot`` (per-cluster prompt-cache reuse), and ``cache_prompt``. This module
is the native-API sibling of ``hermes_cli/local_models/server_adapters.py``
(which only builds launch plans for the ``/v1`` surface) — keep them distinct.

stdlib-only (urllib), with an injectable ``post`` seam so tests never open
sockets. Speculative decoding is a *server-launch-time* concern
(``--spec-draft-model``/``-md`` flags, verified against llama.cpp build
``1593d56``), so it lives on :func:`build_launch_command` /
:class:`SpecDecodeConfig`, not on the per-request call.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional


class LlamaServerError(RuntimeError):
    """The server was unreachable or returned a non-OK response."""


@dataclass(frozen=True)
class CompletionResult:
    text: str
    tokens_predicted: int
    tokens_cached: int
    prompt_ms: float
    predict_ms: float
    raw: dict[str, Any]


@dataclass(frozen=True)
class SpecDecodeConfig:
    """Speculative-decoding launch flags (small Gemma draft for a big target).

    Flag spellings verified against llama.cpp build 1593d56 (the spec's
    ``--draft-max`` family was renamed upstream to ``--spec-draft-*``).
    """

    draft_model_path: str
    draft_max: int = 16  # --spec-draft-n-max (upstream default is 3)
    draft_min: int = 1  # --spec-draft-n-min
    p_min: float = 0.75  # --spec-draft-p-min

    def to_server_args(self) -> tuple[str, ...]:
        return (
            "--spec-draft-model",
            self.draft_model_path,
            "--spec-draft-n-max",
            str(self.draft_max),
            "--spec-draft-n-min",
            str(self.draft_min),
            "--spec-draft-p-min",
            str(self.p_min),
        )


def build_launch_command(
    model_path: str,
    *,
    port: int = 8080,
    host: str = "127.0.0.1",
    ctx: int = 4096,
    n_slots: int = 4,
    slot_save_path: Optional[str] = None,
    cache_reuse: int = 256,
    spec: Optional[SpecDecodeConfig] = None,
    swa_full: bool = False,
) -> tuple[str, ...]:
    """llama-server launch command for the template fast path.

    ``swa_full`` works around the Gemma sliding-window-attention prefix-cache
    reuse bug (llama.cpp #21468) — set it if the cache probe shows no reuse.
    """

    cmd: list[str] = [
        "llama-server",
        "-m",
        model_path,
        "--host",
        host,
        "--port",
        str(port),
        "-c",
        str(ctx),
        "--parallel",
        str(n_slots),
        "--cache-reuse",
        str(cache_reuse),
    ]
    if slot_save_path:
        cmd += ["--slot-save-path", slot_save_path]
    if swa_full:
        cmd.append("--swa-full")
    if spec is not None:
        cmd += list(spec.to_server_args())
    return tuple(cmd)


def _default_post(url: str, payload: Mapping[str, Any], timeout: float) -> dict[str, Any]:
    body = json.dumps(dict(payload)).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise LlamaServerError(f"POST {url} failed: {exc}") from exc


class LlamaServerClient:
    """Tiny native-API client: ``health()`` + ``completion(...)``."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 120.0,
        post: Optional[Callable[[str, Mapping[str, Any], float], dict[str, Any]]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._post = post or _default_post

    def health(self) -> bool:
        try:
            request = urllib.request.Request(f"{self.base_url}/health", method="GET")
            with urllib.request.urlopen(request, timeout=min(self.timeout, 5.0)) as response:
                return json.loads(response.read().decode("utf-8")).get("status") == "ok"
        except Exception:
            return False

    def completion(
        self,
        prompt: str,
        *,
        grammar: Optional[str] = None,
        id_slot: Optional[int] = None,
        cache_prompt: bool = True,
        n_predict: int = 512,
        temperature: float = 0.0,
        seed: int = 0,
    ) -> CompletionResult:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "n_predict": n_predict,
            "cache_prompt": cache_prompt,
            "temperature": temperature,
            "seed": seed,
        }
        if grammar is not None:
            payload["grammar"] = grammar
        if id_slot is not None:
            payload["id_slot"] = id_slot
        raw = self._post(f"{self.base_url}/completion", payload, self.timeout)
        if "content" not in raw:
            raise LlamaServerError(f"unexpected /completion response keys: {sorted(raw)}")
        timings = raw.get("timings") or {}
        return CompletionResult(
            text=str(raw["content"]),
            tokens_predicted=int(raw.get("tokens_predicted") or timings.get("predicted_n") or 0),
            tokens_cached=int(raw.get("tokens_cached") or timings.get("cache_n") or 0),
            prompt_ms=float(timings.get("prompt_ms") or 0.0),
            predict_ms=float(timings.get("predicted_ms") or 0.0),
            raw=raw,
        )


__all__ = [
    "LlamaServerError",
    "CompletionResult",
    "SpecDecodeConfig",
    "build_launch_command",
    "LlamaServerClient",
]
