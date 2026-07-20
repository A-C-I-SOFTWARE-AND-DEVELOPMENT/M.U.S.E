"""Static inventory + thresholds for the research fabric.

This module is **data only** (stdlib, frozen dataclasses, no I/O). It is the
single source of truth for:

* ``REQUIRED_DOMAINS`` — the evaluation domains a challenger must cover.
* The promotion thresholds (``ABSOLUTE_FLOOR``, ``COMPOSITE_MARGIN``,
  ``EVAL_WIN_MARGIN``) used by the strict non-regression ratchet.
* ``SAFETY_DOMAINS`` — domains whose floor may only rise, never fall.
* ``WORKER_POLICY`` — the sandbox limits for any self-modification run.
* The candidate inventory (models / benchmarks / datasets) surfaced from the
  verified research. Candidates are *registered*, never auto-promoted — license
  and capability are re-checked locally before anything is used.

The threshold constants encode two precedents from the research:

* ``EVAL_WIN_MARGIN = 0.55`` is the **AlphaGo Zero evaluator gate** — a
  challenger replaced the champion only if it won >55% of head-to-head games
  (AlphaZero paper, arXiv:1712.01815). A statistical margin, not a coin flip.
* ``ABSOLUTE_FLOOR = 0.80`` is the hard per-domain floor the owner specified.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Domains + thresholds
# ---------------------------------------------------------------------------

# Software-development-first evaluation domains. Each domain must have a
# *cheap, hard-to-game verifier* before it can drive autonomous promotion —
# that is the whole lesson of the AlphaZero/AlphaFold research.
REQUIRED_DOMAINS: tuple[str, ...] = (
    "code_generation",
    "code_editing",
    "code_review",
    "software_development",  # repo-scale issue resolution (SWE-bench-style)
    "reasoning",
    "safety",  # behavioral / constitution compliance — a SAFETY domain
)

# Domain -> executable verifier. Each value is a ``"module:callable"`` string
# pointing at a function with the contract
# ``verify(run_dir: Path) -> verifier.DomainScore`` (the same shape as
# :class:`verifier.swe.SweScore`). The ratchet resolves these at runtime via
# ``verifier.get_verifier(domain)`` so this catalog stays data-only and
# stdlib-only (no I/O, no imports of the verifier package). Adding a new
# benchmark lane is therefore a one-line edit: drop the entry in here and
# the ratchet picks it up automatically.
DOMAIN_VERIFIERS: dict[str, str] = {
    # reasoning lane — multi-step general-agent tasks with tool-use
    "reasoning": "hermes_cli.jarvis_prime.research_fabric.verifier.gaia:verify",
    # software_development lane — repo- and shell-grounded execution tasks
    "software_development": (
        "hermes_cli.jarvis_prime.research_fabric.verifier.terminal_bench:verify"
    ),
    # code_editing lane — multi-language edit-loop signal (Aider Polyglot)
    "code_editing": (
        "hermes_cli.jarvis_prime.research_fabric.verifier.polyglot:verify"
    ),
}

# A challenger must clear this absolute score on EVERY required domain.
ABSOLUTE_FLOOR: float = 0.80

# A challenger's weighted composite must beat the champion's by at least this.
COMPOSITE_MARGIN: float = 0.05

# AlphaGo-Zero-style head-to-head evaluator gate: the challenger must win at
# least this fraction of paired eval tasks against the reigning champion.
EVAL_WIN_MARGIN: float = 0.55

# Domains whose floor can only rise — a regression here can never be traded
# away by a gain elsewhere, no matter how large.
SAFETY_DOMAINS: frozenset[str] = frozenset({"safety", "code_review"})

# Sandbox policy for any self-modification / self-play run. Network OFF and
# no secrets during self-mod is non-negotiable (Sycophancy-to-Subterfuge,
# arXiv:2406.10162; the DGM monitor-tampering episode, arXiv:2505.22954).
WORKER_POLICY: dict[str, Any] = {
    "network": "off",
    "secrets": "none",
    "cpu_limit_cores": 4,
    "memory_limit_mb": 8192,
    "wall_timeout_seconds": 1800,
    "primary_builder": "claude_code",
    "secondary_reviewer": "codex",
    "recursive_learning_rule": "auto_apply_only_inside_active_charter",
}


# ---------------------------------------------------------------------------
# Candidate inventory (registered, not auto-promoted)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelCandidate:
    key: str
    name: str
    license_name: str
    strict_open_source: bool
    roles: tuple[str, ...]
    homepage: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkCandidate:
    key: str
    name: str
    domain: str
    # "train_signal" | "held_out_wall" | "regression_only"
    lane: str
    verifier: str  # how a result is graded (execution-based, etc.)
    contamination_resistant: bool
    homepage: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DatasetCandidate:
    key: str
    name: str
    license_name: str
    roles: tuple[str, ...]
    homepage: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Worker / student backbones — both leading open families are truly permissive
# (Apache-2.0 / MIT), which is what lets us fine-tune + redistribute freely.
MODEL_CANDIDATES: tuple[ModelCandidate, ...] = (
    ModelCandidate(
        key="qwen3_coder",
        name="Qwen3-Coder-480B-A35B-Instruct",
        license_name="Apache-2.0",
        strict_open_source=True,
        roles=("worker", "code_generation", "code_editing", "agentic_repo"),
        homepage="https://github.com/QwenLM/Qwen3-Coder",
        summary="Strongest open agentic/long-context coder; primary worker backbone.",
    ),
    ModelCandidate(
        key="deepseek_v3",
        name="DeepSeek-V3.2",
        license_name="MIT",
        strict_open_source=True,
        roles=("student", "reasoning", "cheap_rollouts"),
        homepage="https://github.com/deepseek-ai/DeepSeek-V3",
        summary="Cheapest to serve; top open Aider-Polyglot; good distillation target.",
    ),
    ModelCandidate(
        key="deepseek_r1",
        name="DeepSeek-R1 (+distills)",
        license_name="MIT",
        strict_open_source=True,
        roles=("reasoning", "rl_student", "math"),
        homepage="https://github.com/deepseek-ai/DeepSeek-R1",
        summary="Reasoning-first; distilled dense variants are excellent cheap RL students.",
    ),
)

# Benchmark lanes. Train on the large refreshable execution-graded pools; gate
# promotion on the held-out / date-gated walls. Never let a wall touch training.
BENCHMARK_CANDIDATES: tuple[BenchmarkCandidate, ...] = (
    BenchmarkCandidate(
        key="swe_rebench",
        name="SWE-rebench",
        domain="software_development",
        lane="train_signal",
        verifier="execution: repo test suite (FAIL_TO_PASS/PASS_TO_PASS)",
        contamination_resistant=True,
        homepage="https://swe-rebench.com/leaderboard",
        summary="21k+ executable RL tasks, continuously refreshed; freshest window is held out.",
    ),
    BenchmarkCandidate(
        key="bigcodebench",
        name="BigCodeBench",
        domain="code_generation",
        lane="train_signal",
        verifier="execution: avg 5.6 tests/task at ~99% branch coverage",
        contamination_resistant=False,
        homepage="https://github.com/bigcode-project/bigcodebench",
        summary="Rich multi-library executable signal for function/tool-use realism.",
    ),
    BenchmarkCandidate(
        key="commit0",
        name="Commit0",
        domain="software_development",
        lane="train_signal",
        verifier="execution: unit tests + static analysis over whole library",
        contamination_resistant=False,
        homepage="https://arxiv.org/abs/2412.01769",
        summary="Generate entire libraries from scratch; long-horizon repo capability.",
    ),
    BenchmarkCandidate(
        key="swe_bench_pro_heldout",
        name="SWE-bench Pro (held-out)",
        domain="software_development",
        lane="held_out_wall",
        verifier="execution: repo test suite on GPL/proprietary repos",
        contamination_resistant=True,
        homepage="https://arxiv.org/pdf/2509.16941",
        summary="Copyleft/proprietary barriers make leakage improbable; the engineered wall.",
    ),
    BenchmarkCandidate(
        key="livecodebench",
        name="LiveCodeBench (post-cutoff)",
        domain="code_generation",
        lane="held_out_wall",
        verifier="execution: contest tests on post-training-cutoff problems",
        contamination_resistant=True,
        homepage="https://livecodebench.github.io/",
        summary="Date-gating structurally defeats memorization; contamination-proof wall.",
    ),
    BenchmarkCandidate(
        key="aider_polyglot",
        name="Aider Polyglot",
        domain="code_editing",
        lane="train_signal",
        verifier="execution: unit tests across 6 languages, 2 attempts",
        contamination_resistant=False,
        homepage="https://aider.chat/docs/leaderboards/",
        summary="Multi-language edit-loop signal; static, so hold-out value decays.",
    ),
    BenchmarkCandidate(
        key="swe_bench_verified",
        name="SWE-bench Verified",
        domain="software_development",
        lane="regression_only",
        verifier="execution: repo test suite (contamination-suspect)",
        contamination_resistant=False,
        homepage="https://www.swebench.com/",
        summary="Legacy regression check only — NOT a wall (contamination-suspect since 2025).",
    ),
)

DATASET_CANDIDATES: tuple[DatasetCandidate, ...] = (
    DatasetCandidate(
        key="the_stack_v2",
        name="The Stack v2",
        license_name="open_permissive_corpus",
        roles=("code_pretraining", "repo_mixture"),
        homepage="https://huggingface.co/datasets/bigcode/the-stack-v2",
        summary="Open code dataset + curation stack for coding-model research.",
    ),
)


def candidate_dicts() -> dict[str, list[dict[str, Any]]]:
    """Return the full inventory as plain dicts (for reports / snapshots)."""

    return {
        "models": [c.to_dict() for c in MODEL_CANDIDATES],
        "benchmarks": [b.to_dict() for b in BENCHMARK_CANDIDATES],
        "datasets": [d.to_dict() for d in DATASET_CANDIDATES],
    }


def held_out_benchmarks() -> tuple[BenchmarkCandidate, ...]:
    return tuple(b for b in BENCHMARK_CANDIDATES if b.lane == "held_out_wall")


def train_signal_benchmarks() -> tuple[BenchmarkCandidate, ...]:
    return tuple(b for b in BENCHMARK_CANDIDATES if b.lane == "train_signal")


__all__ = [
    "REQUIRED_DOMAINS",
    "DOMAIN_VERIFIERS",
    "ABSOLUTE_FLOOR",
    "COMPOSITE_MARGIN",
    "EVAL_WIN_MARGIN",
    "SAFETY_DOMAINS",
    "WORKER_POLICY",
    "ModelCandidate",
    "BenchmarkCandidate",
    "DatasetCandidate",
    "MODEL_CANDIDATES",
    "BENCHMARK_CANDIDATES",
    "DATASET_CANDIDATES",
    "candidate_dicts",
    "held_out_benchmarks",
    "train_signal_benchmarks",
]
