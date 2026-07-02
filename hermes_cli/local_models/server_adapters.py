"""Local inference server adapters — describe how to serve a model.

Each adapter knows three things for one runtime: how to detect whether it is
installed, how to build the (read-only, *not executed here*) launch command,
and what OpenAI-compatible base URL it exposes. This module **never starts a
server and never downloads anything** — it only produces the plan. The
bootstrap layer and the CLI decide whether to actually run it.

Supported runtimes: Ollama, llama.cpp, vLLM, SGLang, DSpark speculative
decoding (llama.cpp/vLLM with a DeepSeek DSpark draft model), and any
OpenAI-compatible local endpoint.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class LaunchPlan:
    runtime: str
    command: tuple[str, ...]
    base_url: str
    notes: str = ""
    pull_command: tuple[str, ...] = ()  # download step, run only with consent

    def to_dict(self) -> dict[str, object]:
        return {
            "runtime": self.runtime,
            "command": list(self.command),
            "base_url": self.base_url,
            "notes": self.notes,
            "pull_command": list(self.pull_command),
        }


@dataclass(frozen=True)
class ServerAdapter:
    runtime: str
    binary: str
    default_port: int
    base_url_template: str = "http://127.0.0.1:{port}/v1"

    def is_installed(self) -> bool:
        return shutil.which(self.binary) is not None

    def base_url(self, port: Optional[int] = None) -> str:
        return self.base_url_template.format(port=port or self.default_port)

    def launch_plan(self, model: str, *, port: Optional[int] = None) -> LaunchPlan:
        raise NotImplementedError


class OllamaAdapter(ServerAdapter):
    def __init__(self) -> None:
        super().__init__(
            runtime="ollama",
            binary="ollama",
            default_port=11434,
            base_url_template="http://127.0.0.1:{port}/v1",
        )

    def launch_plan(self, model: str, *, port: Optional[int] = None) -> LaunchPlan:
        return LaunchPlan(
            runtime=self.runtime,
            command=("ollama", "serve"),
            base_url=self.base_url(port),
            pull_command=("ollama", "pull", model),
            notes="Ollama serves an OpenAI-compatible endpoint at /v1; `ollama pull` downloads weights.",
        )


class LlamaCppAdapter(ServerAdapter):
    def __init__(self) -> None:
        super().__init__(runtime="llama.cpp", binary="llama-server", default_port=8080)

    def launch_plan(self, model: str, *, port: Optional[int] = None) -> LaunchPlan:
        return LaunchPlan(
            runtime=self.runtime,
            command=(
                "llama-server",
                "-m",
                model,
                "--port",
                str(port or self.default_port),
            ),
            base_url=self.base_url(port),
            notes="llama.cpp `llama-server` exposes an OpenAI-compatible API. `-m` is a local GGUF path.",
        )


class VllmAdapter(ServerAdapter):
    def __init__(self) -> None:
        super().__init__(runtime="vllm", binary="vllm", default_port=8000)

    def launch_plan(self, model: str, *, port: Optional[int] = None) -> LaunchPlan:
        return LaunchPlan(
            runtime=self.runtime,
            command=("vllm", "serve", model, "--port", str(port or self.default_port)),
            base_url=self.base_url(port),
            notes="vLLM downloads from HF on first serve; needs a CUDA/ROCm GPU for most models.",
        )


class SglangAdapter(ServerAdapter):
    def __init__(self) -> None:
        super().__init__(runtime="sglang", binary="python", default_port=30000)

    def launch_plan(self, model: str, *, port: Optional[int] = None) -> LaunchPlan:
        return LaunchPlan(
            runtime=self.runtime,
            command=(
                "python",
                "-m",
                "sglang.launch_server",
                "--model-path",
                model,
                "--port",
                str(port or self.default_port),
            ),
            base_url=self.base_url(port),
            notes="SGLang launch_server exposes an OpenAI-compatible API; GPU recommended.",
        )


class OpenAICompatibleAdapter(ServerAdapter):
    """A generic adapter for an already-running OpenAI-compatible endpoint."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000/v1") -> None:
        super().__init__(runtime="openai-compatible", binary="", default_port=8000)
        object.__setattr__(self, "_base_url", base_url)

    def is_installed(self) -> bool:
        # The endpoint is provided by the user; we can't detect a binary.
        return True

    def base_url(self, port: Optional[int] = None) -> str:
        return getattr(self, "_base_url")

    def launch_plan(self, model: str, *, port: Optional[int] = None) -> LaunchPlan:
        return LaunchPlan(
            runtime=self.runtime,
            command=(),
            base_url=self.base_url(port),
            notes="Bring-your-own endpoint; nothing to launch. Point HERMES at this base_url.",
        )


class DsparkAdapter(ServerAdapter):
    """DSpark speculative decoding on top of llama.cpp or vLLM.

    DSpark (DeepSeek + PKU, MIT) pairs the target model with a small draft
    module for 60-85% faster generation at identical output quality. The
    draft catalog and plan builder live in ``dspark.py`` (imported lazily —
    this dict is built at module import).
    """

    def __init__(self) -> None:
        super().__init__(runtime="dspark", binary="", default_port=8080)

    def is_installed(self) -> bool:
        return any(_ADAPTERS[r].is_installed() for r in ("llama.cpp", "vllm"))

    def launch_plan(self, model: str, *, port: Optional[int] = None) -> LaunchPlan:
        from hermes_cli.local_models.dspark import build_dspark_plan

        return build_dspark_plan(model, port=port)


_ADAPTERS: dict[str, ServerAdapter] = {
    "ollama": OllamaAdapter(),
    "llama.cpp": LlamaCppAdapter(),
    "vllm": VllmAdapter(),
    "sglang": SglangAdapter(),
    "dspark": DsparkAdapter(),
    "openai-compatible": OpenAICompatibleAdapter(),
}

SUPPORTED_RUNTIMES: tuple[str, ...] = tuple(_ADAPTERS.keys())


def get_adapter(runtime: str) -> ServerAdapter:
    key = runtime.strip().lower()
    if key not in _ADAPTERS:
        raise KeyError(
            f"unknown runtime {runtime!r}; supported: {', '.join(SUPPORTED_RUNTIMES)}"
        )
    return _ADAPTERS[key]


def installed_runtimes() -> list[str]:
    return [name for name, adapter in _ADAPTERS.items() if adapter.is_installed()]
