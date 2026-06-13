"""Per-job cost / token aggregation (Sprint 10).

Accumulates the cost (USD) and token counts a job has spent across every
worker / model call recorded against it, and evaluates that running total
against a configured budget via :func:`hermes_cli.budget_policy.evaluate_budget`.

This is the missing per-job aggregate: ``main`` already ships the budget
*kernel* (``budget_policy.evaluate_budget``) and per-call usage / pricing
primitives (``agent.usage_pricing.CanonicalUsage`` /
``agent.usage_pricing.estimate_usage_cost``), but nothing summed usage per
job. :class:`JobCost` is that sum.

Design notes:

* **Stdlib only.** Token usage is consumed structurally — ``add_usage``
  accepts any object exposing the ``CanonicalUsage`` token attributes
  (``input_tokens`` / ``output_tokens`` / ``cache_read_tokens`` /
  ``cache_write_tokens`` / ``reasoning_tokens``) plus an optional explicit
  ``cost_usd``. This avoids importing the pricing module (and its ``httpx``
  dependency chain) into the orchestrator's hot path, while staying
  type-compatible with the real ``CanonicalUsage`` dataclass.
* **Additive & behavior-preserving.** A fresh accumulator has zero cost and
  zero tokens; ``budget_decision`` with no limits is always ``WITHIN`` (the
  ``auto`` tier), so wiring it onto a job changes no existing behavior.
* **Cost is float USD.** ``add_usage`` accepts ``Decimal`` (e.g. from
  ``CostResult.amount_usd``), ``int``, ``float``, or numeric ``str`` and
  normalizes to ``float`` so the aggregate is JSON-serializable.

Where this gets fed (the emit hook) is a **documented follow-up**: today the
orchestrator API (``hermes_cli.orchestrator_api``) records worker heartbeats
via ``JobStore.record_worker`` but workers do not yet report token usage in
that payload. When they do, the dispatcher should call
``JobStore.accumulate_cost(job_id, usage=..., cost_usd=...)`` (added here) per
recorded model call. The accumulator and its budget surfacing are real and
tested now; only the producer side is pending.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional, Protocol, Union

from hermes_cli.budget_policy import BudgetDecision, evaluate_budget

if TYPE_CHECKING:  # pragma: no cover - typing only
    from agent.usage_pricing import CanonicalUsage

__all__ = [
    "UsageLike",
    "JobCost",
]


class UsageLike(Protocol):
    """Structural type for the token buckets ``add_usage`` reads.

    ``agent.usage_pricing.CanonicalUsage`` satisfies this protocol, but so
    does any object exposing the same integer attributes — which keeps the
    accumulator free of a hard import on the pricing module.
    """

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int


def _coerce_cost(value: Any) -> float:
    """Normalize a cost value (``Decimal`` / ``int`` / ``float`` / str) to float.

    ``None`` becomes ``0.0`` so an unpriced / "included" call contributes
    tokens without moving the dollar meter. A negative cost is rejected — a
    job's spend only ever grows.
    """

    if value is None:
        return 0.0
    if isinstance(value, bool):  # guard: bool is an int subclass
        raise TypeError("cost_usd must be numeric, not bool")
    if isinstance(value, Decimal):
        amount = float(value)
    elif isinstance(value, (int, float)):
        amount = float(value)
    elif isinstance(value, str):
        try:
            amount = float(value)
        except ValueError as exc:
            raise ValueError(f"cost_usd is not a number: {value!r}") from exc
    else:
        raise TypeError(f"unsupported cost_usd type: {type(value).__name__}")
    if amount < 0:
        raise ValueError("cost_usd must be >= 0")
    return amount


def _coerce_tokens(value: Any) -> int:
    try:
        count = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, count)


#: The ``CanonicalUsage`` token attributes :meth:`JobCost.add_usage` reads off
#: a usage object. The single source of truth for serializing a usage delta
#: (``cost.accumulated`` events) and rebuilding it on restart-replay.
USAGE_TOKEN_FIELDS: tuple[str, ...] = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
)


@dataclass
class JobCost:
    """Running cost + token totals for a single job.

    All fields default to zero, so an attached-but-untouched accumulator is
    indistinguishable (cost-wise) from no accumulator at all. Call
    :meth:`add_usage` per recorded model call; read :meth:`totals` or
    :meth:`budget_decision` to surface the aggregate.
    """

    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    call_count: int = 0
    # Per-(provider, model) breakdown of cost so a status surface can show
    # which route dominated spend. Values are float USD.
    by_model: dict[str, float] = field(default_factory=dict)

    @property
    def prompt_tokens(self) -> int:
        """Tokens billed at input/cache rates (mirrors ``CanonicalUsage``)."""

        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    @property
    def total_tokens(self) -> int:
        """Every token billed across this job (mirrors ``CanonicalUsage``)."""

        return self.prompt_tokens + self.output_tokens

    def add_usage(
        self,
        usage: Optional[Union["UsageLike", "CanonicalUsage"]] = None,
        *,
        cost_usd: Any = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> "JobCost":
        """Fold one recorded model call into the running total.

        Args:
            usage: An object exposing the ``CanonicalUsage`` token attributes.
                ``None`` records a cost-only entry (e.g. a flat per-request
                charge) without touching token counters.
            cost_usd: The call's cost in USD. Accepts ``Decimal`` (e.g.
                ``CostResult.amount_usd``), ``int``, ``float``, numeric ``str``,
                or ``None`` (treated as ``0.0`` — an unpriced/included call).
            model: Optional model id, used to key the ``by_model`` breakdown.
            provider: Optional provider; combined with ``model`` as
                ``"provider/model"`` for the breakdown key.

        Returns:
            ``self``, so calls can be chained.
        """

        amount = _coerce_cost(cost_usd)
        self.cost_usd += amount
        if usage is not None:
            self.input_tokens += _coerce_tokens(getattr(usage, "input_tokens", 0))
            self.output_tokens += _coerce_tokens(getattr(usage, "output_tokens", 0))
            self.cache_read_tokens += _coerce_tokens(
                getattr(usage, "cache_read_tokens", 0)
            )
            self.cache_write_tokens += _coerce_tokens(
                getattr(usage, "cache_write_tokens", 0)
            )
            self.reasoning_tokens += _coerce_tokens(
                getattr(usage, "reasoning_tokens", 0)
            )
        self.call_count += 1
        key = self._model_key(provider, model)
        if key is not None:
            self.by_model[key] = self.by_model.get(key, 0.0) + amount
        return self

    @staticmethod
    def _model_key(provider: Optional[str], model: Optional[str]) -> Optional[str]:
        model_name = (model or "").strip()
        provider_name = (provider or "").strip()
        if not model_name and not provider_name:
            return None
        if provider_name and model_name:
            return f"{provider_name}/{model_name}"
        return model_name or provider_name

    def totals(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the aggregate."""

        return {
            "cost_usd": round(self.cost_usd, 6),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "prompt_tokens": self.prompt_tokens,
            "total_tokens": self.total_tokens,
            "call_count": self.call_count,
            "by_model": {k: round(v, 6) for k, v in self.by_model.items()},
        }

    def budget_decision(
        self,
        *,
        soft_limit: Optional[float] = None,
        hard_limit: Optional[float] = None,
        meter: str = "cost",
    ) -> BudgetDecision:
        """Evaluate the accumulated ``cost_usd`` against soft/hard limits.

        Thin wrapper over :func:`hermes_cli.budget_policy.evaluate_budget`.
        With both limits ``None`` (the default) the outcome is always
        ``WITHIN`` / ``auto`` — attaching budget evaluation to a job changes
        nothing until limits are configured.
        """

        return evaluate_budget(
            self.cost_usd,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
            meter=meter,
        )

    def to_dict(self) -> dict[str, Any]:
        """Alias of :meth:`totals` for symmetry with other Hermes dataclasses."""

        return self.totals()
