"""JARVIS model router scorecards — evidence-backed model selection.

Routing decisions should be backed by measured outcomes, not vibes. This
module records per-job scorecards (tests passed/failed, reviewer findings,
owner corrections, accepted-diff rate, hallucination corrections, latency,
cost) and aggregates them into a per-(model, task, risk) recommendation.

Hard rule (see § F of the build spec): OSS/local models are "wired and
ready" only as config / local-endpoint packets unless a smoke request has
actually succeeded. :func:`local_endpoint_packet` emits such a packet and
makes no sign-in assumption and no network call.

Clean-room, stdlib-only, local JSONL persistence with atomic writes.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Normalization references for turning raw latency/cost/context into [0,1]
# signals. Tunable, but constant so ranking stays reproducible.
_LATENCY_REF_MS = 10_000.0  # ≥10s round-trip scores 0 on the latency axis
_COST_REF_USD = 0.10  # ≥$0.10/task scores 0 on the cost axis
_CONTEXT_REF_TOKENS = 200_000  # ≥200K context scores 1 on the context axis


# Per-task-class weighting of the eight scorecard dimensions. Keys index the
# normalized signals produced by ``ModelScorecard._signals``. These names match
# ``task_router.TaskClass`` values, so the router can rank evidence per class
# without importing it here (no circular dependency).
TASK_CLASS_WEIGHTS: dict[str, dict[str, float]] = {
    "mobile_chat": {"quality": 0.30, "latency": 0.35, "mobile_ux": 0.25, "cost": 0.10},
    "voice_reply": {"quality": 0.20, "latency": 0.45, "mobile_ux": 0.30, "cost": 0.05},
    "research": {"quality": 0.40, "citation": 0.25, "context": 0.25, "tool": 0.10},
    "citation_verification": {"citation": 0.55, "quality": 0.30, "tool": 0.15},
    "coding_plan": {"quality": 0.45, "context": 0.25, "tool": 0.20, "cost": 0.10},
    "coding_build": {"coding": 0.45, "tool": 0.30, "quality": 0.15, "cost": 0.10},
    "coding_review": {"coding": 0.35, "quality": 0.35, "tool": 0.20, "citation": 0.10},
    "test_debug": {"coding": 0.45, "tool": 0.35, "quality": 0.20},
    "summarization": {"quality": 0.40, "latency": 0.25, "context": 0.25, "cost": 0.10},
    "memory_curator": {"quality": 0.35, "memory": 0.35, "tool": 0.20, "cost": 0.10},
}


@dataclass
class ModelScorecard:
    model: str
    provider: str
    task_type: str
    risk_class: str = "RC1"
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: Optional[float] = None
    cost_usd: Optional[float] = None
    tests_passed: int = 0
    tests_failed: int = 0
    reviewer_findings: int = 0
    owner_corrections: int = 0
    hallucination_corrections: int = 0
    accepted_diff_rate: Optional[float] = None
    repeated_error_count: int = 0
    memory_usefulness: Optional[float] = None
    # -- additional scorecard dimensions (mobile-first task routing) --------
    # ``context_length`` is informational (max context the model offers, in
    # tokens); the other three are measured [0,1] outcomes (higher better).
    context_length: int = 0
    tool_reliability: Optional[float] = None
    citation_accuracy: Optional[float] = None
    mobile_ux_suitability: Optional[float] = None
    created_at: str = field(default_factory=_now_iso)

    @property
    def score(self) -> float:
        """A bounded [0,1] quality score derived from recorded outcomes.

        This is the task-agnostic composite kept for backward compatibility.
        For task-class-aware ranking use :meth:`score_for`.
        """

        total_tests = self.tests_passed + self.tests_failed
        pass_rate = (self.tests_passed / total_tests) if total_tests else 0.5
        diff = self.accepted_diff_rate if self.accepted_diff_rate is not None else 0.5
        penalties = (
            0.08 * self.reviewer_findings
            + 0.12 * self.owner_corrections
            + 0.15 * self.hallucination_corrections
            + 0.05 * self.repeated_error_count
        )
        raw = 0.5 * pass_rate + 0.4 * diff + 0.1 * (self.memory_usefulness or 0.5)
        return max(0.0, min(1.0, raw - penalties))

    # -- normalized per-dimension signals (each in [0,1], higher better) ----

    def _signals(self) -> dict[str, float]:
        total_tests = self.tests_passed + self.tests_failed
        pass_rate = (self.tests_passed / total_tests) if total_tests else 0.5
        diff = self.accepted_diff_rate if self.accepted_diff_rate is not None else 0.5
        # Quality blends measured pass-rate with accepted-diff rate.
        quality = 0.6 * pass_rate + 0.4 * diff
        latency = (
            max(0.0, 1.0 - min(1.0, self.latency_ms / _LATENCY_REF_MS))
            if self.latency_ms is not None
            else 0.5
        )
        cost = (
            max(0.0, 1.0 - min(1.0, self.cost_usd / _COST_REF_USD))
            if self.cost_usd is not None
            else 0.5
        )
        context = (
            min(1.0, self.context_length / _CONTEXT_REF_TOKENS)
            if self.context_length
            else 0.5
        )
        return {
            "quality": quality,
            "coding": pass_rate,
            "latency": latency,
            "cost": cost,
            "context": context,
            "tool": self.tool_reliability if self.tool_reliability is not None else 0.5,
            "citation": (
                self.citation_accuracy if self.citation_accuracy is not None else 0.5
            ),
            "mobile_ux": (
                self.mobile_ux_suitability
                if self.mobile_ux_suitability is not None
                else 0.5
            ),
            "memory": self.memory_usefulness if self.memory_usefulness is not None else 0.5,
        }

    def score_for(self, task_class: Optional[str]) -> float:
        """Task-class-aware [0,1] score.

        Re-weights the eight scorecard dimensions per the profile for
        ``task_class`` (see :data:`TASK_CLASS_WEIGHTS`). Unknown/None task
        classes fall back to the task-agnostic :attr:`score`. Owner
        corrections, hallucination corrections and repeated errors always
        penalize, regardless of task class.
        """

        weights = TASK_CLASS_WEIGHTS.get(task_class or "")
        if not weights:
            return self.score
        signals = self._signals()
        total_w = sum(weights.values()) or 1.0
        raw = sum(weights[k] * signals[k] for k in weights) / total_w
        penalties = (
            0.06 * self.reviewer_findings
            + 0.12 * self.owner_corrections
            + 0.15 * self.hallucination_corrections
            + 0.05 * self.repeated_error_count
        )
        return max(0.0, min(1.0, raw - penalties))

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {
            "model": self.model,
            "provider": self.provider,
            "task_type": self.task_type,
            "risk_class": self.risk_class,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "reviewer_findings": self.reviewer_findings,
            "owner_corrections": self.owner_corrections,
            "hallucination_corrections": self.hallucination_corrections,
            "accepted_diff_rate": self.accepted_diff_rate,
            "repeated_error_count": self.repeated_error_count,
            "memory_usefulness": self.memory_usefulness,
            "context_length": self.context_length,
            "tool_reliability": self.tool_reliability,
            "citation_accuracy": self.citation_accuracy,
            "mobile_ux_suitability": self.mobile_ux_suitability,
            "created_at": self.created_at,
        }
        d["score"] = round(self.score, 4)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ModelScorecard":
        return cls(
            model=d["model"],
            provider=d.get("provider", "unknown"),
            task_type=d.get("task_type", "general"),
            risk_class=d.get("risk_class", "RC1"),
            tokens_in=int(d.get("tokens_in", 0)),
            tokens_out=int(d.get("tokens_out", 0)),
            latency_ms=d.get("latency_ms"),
            cost_usd=d.get("cost_usd"),
            tests_passed=int(d.get("tests_passed", 0)),
            tests_failed=int(d.get("tests_failed", 0)),
            reviewer_findings=int(d.get("reviewer_findings", 0)),
            owner_corrections=int(d.get("owner_corrections", 0)),
            hallucination_corrections=int(d.get("hallucination_corrections", 0)),
            accepted_diff_rate=d.get("accepted_diff_rate"),
            repeated_error_count=int(d.get("repeated_error_count", 0)),
            memory_usefulness=d.get("memory_usefulness"),
            context_length=int(d.get("context_length", 0) or 0),
            tool_reliability=d.get("tool_reliability"),
            citation_accuracy=d.get("citation_accuracy"),
            mobile_ux_suitability=d.get("mobile_ux_suitability"),
            created_at=d.get("created_at", _now_iso()),
        )


DEFAULT_SCORECARD_PATH = (
    Path.home() / ".hermes" / "jarvis_prime" / "model_scorecards.jsonl"
)


@dataclass
class ScorecardBook:
    path: Optional[Path] = None
    scorecards: list[ModelScorecard] = field(default_factory=list)
    load_diagnostics: list[str] = field(default_factory=list)

    def record(self, card: ModelScorecard, *, persist: bool = True) -> ModelScorecard:
        self.scorecards.append(card)
        if persist:
            self.save()
        return card

    def recommend(
        self,
        task_type: str,
        *,
        risk_class: Optional[str] = None,
        min_samples: int = 1,
        task_class: Optional[str] = None,
    ) -> list[tuple[str, float, int]]:
        """Return ``(model, mean_score, samples)`` best first for a task.

        When ``task_class`` is given, cards are scored with
        :meth:`ModelScorecard.score_for` so the ranking reflects the
        dimensions that matter for that mobile-first task class; otherwise the
        task-agnostic :attr:`ModelScorecard.score` is used.
        """

        buckets: dict[str, list[float]] = {}
        for card in self.scorecards:
            if card.task_type != task_type:
                continue
            if risk_class and card.risk_class != risk_class:
                continue
            value = card.score_for(task_class) if task_class else card.score
            buckets.setdefault(card.model, []).append(value)
        ranked = [
            (model, sum(scores) / len(scores), len(scores))
            for model, scores in buckets.items()
            if len(scores) >= min_samples
        ]
        ranked.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return ranked

    def render(self, task_type: Optional[str] = None) -> str:
        cards = [
            c for c in self.scorecards if not task_type or c.task_type == task_type
        ]
        if not cards:
            return "No scorecards recorded yet."
        lines = ["MODEL SCORECARDS"]
        for c in sorted(cards, key=lambda c: c.score, reverse=True):
            lines.append(
                f"  {c.model} [{c.provider}] {c.task_type}/{c.risk_class} "
                f"score={c.score:.2f} tests={c.tests_passed}/{c.tests_passed + c.tests_failed} "
                f"owner_corr={c.owner_corrections} halluc={c.hallucination_corrections}"
            )
        return "\n".join(lines)

    # -- persistence --------------------------------------------------------

    def _resolve_path(self) -> Path:
        return Path(self.path) if self.path else DEFAULT_SCORECARD_PATH

    def save(self) -> Path:
        target = self._resolve_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(
            json.dumps(c.to_dict(), sort_keys=True) + "\n" for c in self.scorecards
        )
        fd, tmp = tempfile.mkstemp(
            dir=str(target.parent), prefix=".scorecard-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        return target

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "ScorecardBook":
        book = cls(path=path)
        target = book._resolve_path()
        if not target.exists():
            return book
        with open(target, "r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, 1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    book.scorecards.append(ModelScorecard.from_dict(json.loads(raw)))
                except (json.JSONDecodeError, KeyError, ValueError) as exc:
                    book.load_diagnostics.append(f"line {lineno}: {exc}")
        return book


def local_endpoint_packet(
    model: str,
    *,
    endpoint: str = "http://localhost:8000/v1",
    server: str = "vllm",
) -> dict[str, object]:
    """Emit an OpenAI-compatible local-endpoint config packet.

    Makes no network call and assumes no sign-in. The model is "wired and
    ready" — NOT confirmed running. A smoke request must succeed before any
    code claims the model is live.
    """

    return {
        "status": "wired_not_confirmed",
        "model": model,
        "server": server,
        "endpoint": endpoint,
        "openai_compatible": True,
        "api_key_env": "LOCAL_OPENAI_API_KEY",  # often "EMPTY" for local servers
        "note": (
            "Local model is configured but not verified running. Run a smoke "
            "completion against the endpoint before treating it as available."
        ),
        "smoke_check": (
            f"curl -s {endpoint}/models  # then a 1-token completion against {model}"
        ),
    }
