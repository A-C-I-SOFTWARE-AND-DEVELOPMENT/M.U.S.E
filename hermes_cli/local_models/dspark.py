"""DSpark speculative-decoding launch plans (DeepSeek + PKU, MIT).

DSpark (arXiv:2606.19348, open-sourced 2026-06-27 in
https://github.com/deepseek-ai/DeepSpec) attaches a small block-drafting
module to a target model so the target verifies several drafted tokens per
forward pass — 60-85% faster generation with *identical* output quality.
This module turns that into launch plans for the runtimes Muse already
knows, following the ``server_adapters`` contract: **plans only, nothing is
executed or downloaded here**.

Three serving paths, fastest-to-adopt first:

1. **DeepSeek API** — nothing to install. ``api.deepseek.com`` has served
   V4-Flash/V4-Pro with DSpark server-side since 2026-06-27; routing to the
   ``deepseek`` provider already gets the speedup.
2. **llama.cpp** — community GGUF conversions of the official draft models
   ride the existing ``--spec-draft-*`` flags (same flag family
   ``jarvis_prime.llama_client.SpecDecodeConfig`` verified).
3. **vLLM** — speculators-format conversions ride ``--speculative-config``;
   the self-contained ``DeepSeek-V4-*-DSpark`` checkpoints serve directly.

The draft catalog below mirrors DeepSpec's released checkpoints (Qwen3
4B/8B/14B, Gemma4-12B) plus the vLLM-ready conversions published alongside.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from hermes_cli.jarvis_prime.llama_client import SpecDecodeConfig
from hermes_cli.local_models.server_adapters import LaunchPlan, get_adapter


# DSpark's deployed configuration drafts 5 tokens per verify step
# ("DSpark-5" in the paper); llama.cpp draft windows are tuned separately
# via SpecDecodeConfig defaults.
DEFAULT_NUM_SPECULATIVE_TOKENS = 5


@dataclass(frozen=True)
class DsparkDraft:
    """One official DSpark draft model and its runtime-ready conversions."""

    family: str  # normalized target family key, e.g. "qwen3-8b"
    target_hf: str  # verified target checkpoint on Hugging Face
    draft_hf: str  # official DeepSpec draft (safetensors)
    draft_gguf: str = ""  # community GGUF conversion — llama.cpp path
    draft_speculators: str = ""  # speculators-format conversion — vLLM path

    @property
    def tokens(self) -> frozenset[str]:
        return frozenset(self.family.split("-"))


# Official DeepSpec draft checkpoints (deepseek-ai, MIT) and the
# runtime-ready conversions verified on Hugging Face as of 2026-07-02.
OFFICIAL_DRAFTS: tuple[DsparkDraft, ...] = (
    DsparkDraft(
        family="qwen3-4b",
        target_hf="Qwen/Qwen3-4B",
        draft_hf="deepseek-ai/dspark_qwen3_4b_block7",
    ),
    DsparkDraft(
        family="qwen3-8b",
        target_hf="Qwen/Qwen3-8B",
        draft_hf="deepseek-ai/dspark_qwen3_8b_block7",
        draft_gguf="ankk98/dspark-qwen3-8b-block7-Q4_K_M-GGUF",
        draft_speculators="mgoin/Qwen3-8B-speculator.dspark",
    ),
    DsparkDraft(
        family="qwen3-14b",
        target_hf="Qwen/Qwen3-14B",
        draft_hf="deepseek-ai/dspark_qwen3_14b_block7",
    ),
    DsparkDraft(
        family="gemma4-12b",
        target_hf="google/gemma-4-12B-it",
        draft_hf="deepseek-ai/dspark_gemma4_12b_block7",
        draft_gguf="ankk98/dspark-gemma4-12b-block7-Q4_0-GGUF",
    ),
)

# Self-contained DSpark checkpoints — target weights with the draft module
# already attached. vLLM serves these directly, no --speculative-config.
# Server-class hardware (V4 is a ~671B/889B-param MoE family).
DSPARK_CHECKPOINTS: dict[str, str] = {
    "deepseek-v4-flash": "deepseek-ai/DeepSeek-V4-Flash-DSpark",
    "deepseek-v4-pro": "deepseek-ai/DeepSeek-V4-Pro-DSpark",
}


_SPLIT = re.compile(r"[^a-z0-9.]+")


def _norm_tokens(model: str) -> set[str]:
    """Tokenize a model ref for family matching.

    Handles HF ids ("Qwen/Qwen3-8B"), Ollama refs ("qwen3:8b"), and GGUF
    paths ("~/models/qwen3-8b-instruct-Q4_K_M.gguf") alike. Size tokens keep
    their ``b`` suffix so "8b" can't match "80b". Adjacent tokens are also
    merged so spelled-out generations match the family keys ("gemma-4" and
    "gemma4" both yield "gemma4", "qwen-3" yields "qwen3").
    """
    name = model.rsplit("/", 1)[-1].lower()
    name = name.removesuffix(".gguf")
    parts = [t for t in _SPLIT.split(name) if t]
    tokens = set(parts)
    tokens.update(a + b for a, b in zip(parts, parts[1:]))
    return tokens


def resolve_draft(model: str) -> Optional[DsparkDraft]:
    """The official DSpark draft for ``model``, or ``None`` if not covered."""
    tokens = _norm_tokens(model)
    for draft in OFFICIAL_DRAFTS:
        if draft.tokens <= tokens:
            return draft
    return None


def resolve_checkpoint(model: str) -> Optional[str]:
    """The self-contained DSpark checkpoint for a DeepSeek-V4 ref, if any."""
    if "deepseek" not in model.lower():
        return None
    tokens = _norm_tokens(model)
    for family, checkpoint in DSPARK_CHECKPOINTS.items():
        # "v4" and the variant ("flash"/"pro") must both appear.
        if set(family.split("-")) - {"deepseek"} <= tokens:
            return checkpoint
    return None


def build_dspark_plan(
    model: str,
    *,
    runtime: Optional[str] = None,
    port: Optional[int] = None,
    draft: Optional[str] = None,
    num_speculative_tokens: int = DEFAULT_NUM_SPECULATIVE_TOKENS,
) -> LaunchPlan:
    """A DSpark-accelerated launch plan for ``model``.

    ``runtime`` may be ``"llama.cpp"`` or ``"vllm"``; when omitted it is
    inferred (GGUF path → llama.cpp, else first installed of vllm/llama.cpp,
    else vllm). ``draft`` overrides the draft-model ref — for llama.cpp it
    should be a local GGUF path once downloaded.
    """
    checkpoint = resolve_checkpoint(model)
    resolved = resolve_draft(model)

    if runtime is None:
        if model.lower().endswith(".gguf"):
            runtime = "llama.cpp"
        elif checkpoint is not None:
            runtime = "vllm"
        else:
            installed = [r for r in ("vllm", "llama.cpp") if get_adapter(r).is_installed()]
            runtime = installed[0] if installed else "vllm"

    key = runtime.strip().lower()
    if key == "llama.cpp":
        return _llamacpp_plan(model, resolved, draft=draft, port=port)
    if key == "vllm":
        return _vllm_plan(
            model,
            resolved,
            checkpoint=checkpoint,
            draft=draft,
            port=port,
            num_speculative_tokens=num_speculative_tokens,
        )
    raise KeyError(f"dspark runtime must be 'llama.cpp' or 'vllm', got {runtime!r}")


def _llamacpp_plan(
    model: str,
    resolved: Optional[DsparkDraft],
    *,
    draft: Optional[str],
    port: Optional[int],
) -> LaunchPlan:
    adapter = get_adapter("llama.cpp")
    draft_ref = draft or (resolved.draft_gguf if resolved else "")
    if not draft_ref:
        known = ", ".join(d.family for d in OFFICIAL_DRAFTS if d.draft_gguf)
        return LaunchPlan(
            runtime="dspark",
            command=(),
            base_url=adapter.base_url(port),
            notes=(
                f"No GGUF DSpark draft known for {model!r} (GGUF drafts exist for: "
                f"{known}). Pass draft= with a local draft GGUF, or use the vllm "
                "runtime with the safetensors draft."
            ),
        )
    spec = SpecDecodeConfig(draft_model_path=draft_ref)
    base = adapter.launch_plan(model, port=port)
    pull: tuple[str, ...] = ()
    if "/" in draft_ref and not draft_ref.lower().endswith(".gguf"):
        pull = ("huggingface-cli", "download", draft_ref)
    return LaunchPlan(
        runtime="dspark",
        command=base.command + spec.to_server_args(),
        base_url=base.base_url,
        pull_command=pull,
        notes=(
            "llama.cpp speculative decoding with the DSpark draft; flag family "
            "verified in jarvis_prime.llama_client. Draft must be a local GGUF "
            "path at launch — the pull_command downloads it (consent-gated)."
        ),
    )


def _vllm_plan(
    model: str,
    resolved: Optional[DsparkDraft],
    *,
    checkpoint: Optional[str],
    draft: Optional[str],
    port: Optional[int],
    num_speculative_tokens: int,
) -> LaunchPlan:
    adapter = get_adapter("vllm")
    if checkpoint is not None:
        base = adapter.launch_plan(checkpoint, port=port)
        return LaunchPlan(
            runtime="dspark",
            command=base.command,
            base_url=base.base_url,
            notes=(
                f"{checkpoint} ships with the DSpark draft module attached — vLLM "
                "serves it directly (no --speculative-config). Server-class GPUs "
                "required; V4 is a large MoE family."
            ),
        )
    draft_ref = draft or (
        (resolved.draft_speculators or resolved.draft_hf) if resolved else ""
    )
    if not draft_ref:
        known = ", ".join(d.family for d in OFFICIAL_DRAFTS)
        return LaunchPlan(
            runtime="dspark",
            command=(),
            base_url=adapter.base_url(port),
            notes=(
                f"No DSpark draft known for {model!r} (official drafts cover: "
                f"{known}). Pass draft= with a draft-model ref, or train one with "
                "DeepSpec (github.com/deepseek-ai/DeepSpec)."
            ),
        )
    spec_config = json.dumps(
        {"model": draft_ref, "num_speculative_tokens": num_speculative_tokens}
    )
    base = adapter.launch_plan(model, port=port)
    return LaunchPlan(
        runtime="dspark",
        command=base.command + ("--speculative-config", spec_config),
        base_url=base.base_url,
        notes=(
            "vLLM speculative decoding with the DSpark draft. speculators-format "
            "drafts (…-speculator.dspark) auto-detect the method; for raw DeepSpec "
            "drafts check your vLLM version's DSpark support."
        ),
    )
