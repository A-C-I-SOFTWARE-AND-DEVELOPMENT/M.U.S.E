"""The muse_TEMPLATES fast path — cluster-routed, grammar-forced, cache-primed.

Flag-guarded challenger lane for the Gemma runner (champion = flag-off free
generation). With ``muse_TEMPLATES`` truthy AND ``muse_TEMPLATES_SERVER``
pointing at a healthy llama-server, :func:`maybe_wrap_runner` wraps the base
``(prompt) -> completion`` runner:

1. ``clusters.assign(prompt)`` — below the τ gate (default 0.75,
   ``muse_TEMPLATES_TAU``) or no template for the cluster → base runner,
   fallback logged to flywheel.
2. ``hard`` template: single grammar-constrained completion, prefix-primed on
   the cluster's prompt-cache slot (stable ``cluster_id % n_slots`` mapping).
3. ``soft`` template: two-stage reason-then-format — stage 1 free reasoning,
   stage 2 grammar-constrained fill with stage-1 reasoning as context, same
   slot. Reasoning is never hard-forced.
4. ANY error → flywheel record + silent fallback to the base runner; repeated
   hard errors enqueue a flywheel improvement entry. The fast path can slow
   things down but never break the lane.

With the flag off (default) ``maybe_wrap_runner`` is never even imported by
``gemma_runner`` — behavior is byte-identical to the champion.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .clusters import ClusterModel, EmbeddingBackend, HashedFeatureBackend
from .llama_client import LlamaServerClient
from .template_mining import DEFAULT_TAU, TemplateFiles, load_template, templates_dir

ENV_TEMPLATES = "muse_TEMPLATES"
ENV_TEMPLATES_SERVER = "muse_TEMPLATES_SERVER"
ENV_TEMPLATES_TAU = "muse_TEMPLATES_TAU"

# After this many consecutive hard failures, queue a flywheel improvement
# entry (once) so the owner sees a structured signal, not just fallbacks.
_HARD_ERROR_QUEUE_THRESHOLD = 3


def templates_enabled() -> bool:
    """True when the owner opted into the template fast path (default off)."""

    return os.environ.get(ENV_TEMPLATES, "").strip().lower() in ("1", "true", "yes", "on")


def configured_server_url() -> str:
    return os.environ.get(ENV_TEMPLATES_SERVER, "").strip()


def configured_tau() -> float:
    raw = os.environ.get(ENV_TEMPLATES_TAU, "").strip()
    try:
        return float(raw) if raw else DEFAULT_TAU
    except ValueError:
        return DEFAULT_TAU


@dataclass(frozen=True)
class FastPathPlan:
    cluster_id: int
    confidence: float
    mode: str  # "hard" | "soft"
    template: TemplateFiles
    slot: int


@dataclass(frozen=True)
class FastPathResult:
    text: str
    used_fastpath: bool
    cluster_id: Optional[int]
    confidence: float
    mode: str
    tokens_cached: int
    latency_ms: float


def _default_recorder(kind: str, payload: dict, *, outcome: Optional[str] = None) -> None:
    from . import flywheel

    flywheel.record(kind, payload, outcome=outcome)


def _default_improvement_queue(summary: str, payload: dict) -> None:
    from . import flywheel

    flywheel.queue_improvement(
        summary, kind="templates.fastpath_error", payload=payload, source="template_fastpath"
    )


class TemplateFastPath:
    """Plans and runs template-accelerated completions for one llama-server."""

    def __init__(
        self,
        *,
        model: ClusterModel,
        backend: EmbeddingBackend,
        templates_root: Path,
        client: LlamaServerClient,
        tau: float = DEFAULT_TAU,
        n_slots: int = 4,
        recorder: Optional[Callable[..., Any]] = None,
        improvement_queue: Optional[Callable[[str, dict], Any]] = None,
    ) -> None:
        self.model = model
        self.backend = backend
        self.templates_root = templates_root
        self.client = client
        self.tau = tau
        self.n_slots = n_slots
        self._record = recorder or _default_recorder
        self._queue_improvement = improvement_queue or _default_improvement_queue
        self._consecutive_errors = 0
        self._error_queued = False

    def plan(self, prompt: str) -> Optional[FastPathPlan]:
        assignment = self.model.assign(prompt, backend=self.backend)
        if assignment.confidence < self.tau:
            self._record(
                "agent.action",
                {
                    "summary": "template fastpath fallback: below confidence gate",
                    "tool": "template_fastpath",
                    "cluster_id": assignment.cluster_id,
                    "confidence": round(assignment.confidence, 4),
                    "tau": self.tau,
                },
                outcome="success",
            )
            return None
        template = load_template(self.templates_root, assignment.cluster_id)
        if template is None:
            self._record(
                "agent.action",
                {
                    "summary": "template fastpath fallback: no template for cluster",
                    "tool": "template_fastpath",
                    "cluster_id": assignment.cluster_id,
                    "confidence": round(assignment.confidence, 4),
                },
                outcome="success",
            )
            return None
        return FastPathPlan(
            cluster_id=assignment.cluster_id,
            confidence=assignment.confidence,
            mode=template.mode,
            template=template,
            slot=assignment.cluster_id % self.n_slots,
        )

    def run(self, prompt: str) -> Optional[FastPathResult]:
        """Template-accelerated completion, or None to signal base fallback."""

        try:
            plan = self.plan(prompt)
            if plan is None:
                return None
            if plan.mode == "hard":
                result = self._run_hard(prompt, plan)
            else:
                result = self._run_soft(prompt, plan)
            self._consecutive_errors = 0
            return result
        except Exception as exc:
            self._consecutive_errors += 1
            self._record(
                "agent.action",
                {
                    "summary": "template fastpath fallback: error",
                    "tool": "template_fastpath",
                    "error": str(exc)[:300],
                },
                outcome="failure",
            )
            if self._consecutive_errors >= _HARD_ERROR_QUEUE_THRESHOLD and not self._error_queued:
                self._error_queued = True
                self._queue_improvement(
                    "template fastpath: repeated hard errors, falling back to base runner",
                    {"consecutive_errors": self._consecutive_errors, "last_error": str(exc)[:300]},
                )
            return None

    def _run_hard(self, prompt: str, plan: FastPathPlan) -> FastPathResult:
        result = self.client.completion(
            f"{plan.template.prefix}{prompt}\n",
            grammar=plan.template.scaffold_gbnf,
            id_slot=plan.slot,
            cache_prompt=True,
        )
        return self._result(result.text, plan, result)

    def _run_soft(self, prompt: str, plan: FastPathPlan) -> FastPathResult:
        # Stage 1 — free reasoning (never grammar-forced), same cached slot.
        reasoning = self.client.completion(
            f"{plan.template.prefix}{prompt}\nReason step by step before answering:\n",
            id_slot=plan.slot,
            cache_prompt=True,
            n_predict=256,
        )
        # Stage 2 — constrained fill, stage-1 reasoning as context.
        final = self.client.completion(
            (
                f"{plan.template.prefix}{prompt}\n"
                f"Draft reasoning:\n{reasoning.text}\n"
                "Now produce only the final answer in the required shape:\n"
            ),
            grammar=plan.template.scaffold_gbnf,
            id_slot=plan.slot,
            cache_prompt=True,
        )
        merged = CompletionPair(reasoning, final)
        return self._result(final.text, plan, merged)

    def _result(self, text: str, plan: FastPathPlan, timing: Any) -> FastPathResult:
        self._record(
            "agent.action",
            {
                "summary": "template fastpath used",
                "tool": "template_fastpath",
                "cluster_id": plan.cluster_id,
                "mode": plan.mode,
                "confidence": round(plan.confidence, 4),
                "tokens_cached": timing.tokens_cached,
            },
            outcome="success",
        )
        return FastPathResult(
            text=text,
            used_fastpath=True,
            cluster_id=plan.cluster_id,
            confidence=plan.confidence,
            mode=plan.mode,
            tokens_cached=timing.tokens_cached,
            latency_ms=timing.prompt_ms + timing.predict_ms,
        )


class CompletionPair:
    """Aggregated timings over the two soft-mode stages."""

    def __init__(self, first: Any, second: Any) -> None:
        self.tokens_cached = int(first.tokens_cached) + int(second.tokens_cached)
        self.prompt_ms = float(first.prompt_ms) + float(second.prompt_ms)
        self.predict_ms = float(first.predict_ms) + float(second.predict_ms)


def _backend_for(backend_name: str) -> Optional[EmbeddingBackend]:
    """Reconstruct the embedding backend a cluster model was fitted with."""

    import re as _re

    match = _re.fullmatch(r"hashed-ngram-d(\d+)-s(\d+)", backend_name)
    if match:
        return HashedFeatureBackend(dim=int(match.group(1)), seed=int(match.group(2)))
    if backend_name.startswith("minilm:"):
        try:
            from .clusters import MiniLMBackend

            return MiniLMBackend(backend_name.split(":", 1)[1])
        except Exception:
            return None
    return None


def build_fastpath(
    *,
    server_url: Optional[str] = None,
    templates_root: Optional[Path] = None,
    tau: Optional[float] = None,
) -> Optional[TemplateFastPath]:
    """Construct the fast path from env + committed artifacts, or None.

    Returns None (never raises) when the server is missing/unhealthy or the
    cluster-model/template artifacts are absent — callers degrade to the base
    runner silently.
    """

    url = server_url if server_url is not None else configured_server_url()
    if not url:
        return None
    root = templates_root if templates_root is not None else templates_dir()
    model_dir = root / "model"
    try:
        model = ClusterModel.load(model_dir)
    except Exception:
        return None
    backend = _backend_for(model.backend_name)
    if backend is None:
        return None
    client = LlamaServerClient(url)
    if not client.health():
        return None
    return TemplateFastPath(
        model=model,
        backend=backend,
        templates_root=root,
        client=client,
        tau=tau if tau is not None else configured_tau(),
    )


def maybe_wrap_runner(base_runner: Callable[[str], str]) -> Callable[[str], str]:
    """Wrap a base runner with the fast path; return it UNCHANGED on any gap.

    The identity guarantee (same object back) is what keeps flag-off — and
    flag-on-but-unconfigured — behavior byte-identical to the champion.
    """

    if not templates_enabled():
        return base_runner
    fastpath = build_fastpath()
    if fastpath is None:
        return base_runner

    def wrapped(prompt: str) -> str:
        result = fastpath.run(prompt)
        if result is not None:
            return result.text
        return base_runner(prompt)

    return wrapped


__all__ = [
    "ENV_TEMPLATES",
    "ENV_TEMPLATES_SERVER",
    "ENV_TEMPLATES_TAU",
    "templates_enabled",
    "FastPathPlan",
    "FastPathResult",
    "TemplateFastPath",
    "build_fastpath",
    "maybe_wrap_runner",
]
