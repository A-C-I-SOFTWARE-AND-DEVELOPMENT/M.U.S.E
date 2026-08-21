#!/usr/bin/env python3
"""Output-normalization and unit-interpretation validator, run *before* grading.


**The failure this exists for.** A Level-1 QA answer was graded WRONG because
the model produced ``17000`` against a gold field of ``17``, after completing 6
turns and 6 API calls in 72.57 s.  The work was right; the grader was
unit-blind.  A grader that only lowercases and collapses whitespace
(``benchmarks/gaia_runner.py::_normalize_answer``) cannot tell a unit
convention apart from a wrong answer.

**The rule this obeys.** Fixing that by making ``17000 == 17`` would be worse
than the bug, because it would also erase every genuinely wrong answer that
happens to be a thousand times too large.  So the verdict is three-way:

``MATCH``
    The two answers denote the same value under a reading that somebody
    actually declared, or that the question makes inferable.
``MISMATCH``
    They denote different values and no unit convention reconciles them.
``AMBIGUOUS_UNIT``
    They *would* agree under a plausible unit convention, but nothing in the
    answer, the gold field or the question declares which convention applies.

``AMBIGUOUS_UNIT`` is not a soft match.  It is a grading defect to surface: the
benchmark row is under-specified, and the fix belongs in the task definition,
not in the comparison.  :meth:`ValidationResult.is_grading_defect` is what a
harness should route to a human.

Nothing in this module edits or replaces an existing grader.  It runs ahead of
one and reports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from enum import Enum
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .normalize import (
    DateReading,
    Numeric,
    clean_text,
    naive_normalize,
    parse_boolean,
    parse_date,
    parse_numeric,
    split_list,
)
from .units import lookup_scale, lookup_unit

__all__ = [
    "Verdict",
    "Reason",
    "NormalizationPolicy",
    "GradingContext",
    "ValidationResult",
    "ValidationReport",
    "OutputNormalizationValidator",
    "validate_answer",
]


class Verdict(str, Enum):
    """The three-way verdict.  There is no fourth value and no soft match."""

    MATCH = "match"
    MISMATCH = "mismatch"
    AMBIGUOUS_UNIT = "ambiguous_unit"


class Reason:
    """Machine-readable reason codes, so a report can be triaged by class."""

    IDENTICAL = "identical"
    TEXT_NORMALIZED = "text_normalized"
    NUMERIC_EQUAL = "numeric_equal"
    UNIT_CONVERSION = "unit_conversion"
    UNIT_ANNOTATION_ONLY = "unit_annotation_only"
    CONTEXT_UNIT_INFERRED = "context_unit_inferred"
    BOOLEAN_EQUAL = "boolean_equal"
    DATE_EQUAL = "date_equal"
    LIST_EQUAL = "list_equal"

    NUMERIC_DIFFERENT = "numeric_different"
    DIMENSION_MISMATCH = "dimension_mismatch"
    CURRENCY_MISMATCH = "currency_mismatch"
    BOOLEAN_DIFFERENT = "boolean_different"
    DATE_DIFFERENT = "date_different"
    LIST_DIFFERENT = "list_different"
    LIST_LENGTH_DIFFERENT = "list_length_different"
    TYPE_MISMATCH = "type_mismatch"
    TEXT_DIFFERENT = "text_different"

    UNIT_SCALE_UNDECLARED = "unit_scale_undeclared"
    PERCENT_CONVENTION_UNDECLARED = "percent_convention_undeclared"
    DATE_ORDER_UNDECLARED = "date_order_undeclared"
    PRECISION_UNDECLARED = "precision_undeclared"
    LIST_AMBIGUOUS = "list_ambiguous"


_DEFAULT_AMBIGUITY_FACTORS: Tuple[Decimal, ...] = (
    Decimal(10) ** 2,  # percent <-> fraction, and "hundreds"
    Decimal(10) ** 3,  # thousands / k
    Decimal(10) ** 6,  # millions / M
    Decimal(10) ** 9,  # billions / bn
    Decimal(10) ** 12,  # trillions
)


@dataclass(frozen=True)
class NormalizationPolicy:
    """Knobs, all of which default to the conservative reading."""

    rel_tol: Decimal = Decimal("1e-9")
    """Relative tolerance, wide enough for float printing noise and no wider."""

    abs_tol: Decimal = Decimal(0)

    ambiguity_factors: Tuple[Decimal, ...] = _DEFAULT_AMBIGUITY_FACTORS
    """Ratios that a unit convention could explain.

    Note what is *absent*: 10.  No unit word means ten, so ``1.7e4`` against
    ``1.7e5`` is a plain wrong answer, not an ambiguity.
    """

    ratio_tol: Decimal = Decimal("1e-9")

    precision_ambiguity: bool = True
    """Flag "gold may be the rounded form of the answer" instead of failing it."""

    allow_list_reordering: bool = True

    allow_boolean_numeric: bool = True
    """Let ``1``/``0`` read as a boolean, but only opposite a boolean word."""


# Singular and plural both count: the recorded Level-1 failure's question asks
# "how many thousand hours would it take", not "how many thousands".
_SCALE_ALT = r"(hundreds?|thousands?|millions?|billions?|trillions?)"

_SCALE_PHRASE_RE = re.compile(
    r"\b(?:in|expressed\s+in|reported\s+in|measured\s+in|stated\s+in)\s+"
    r"(?:[a-z]+\s+)?" + _SCALE_ALT + r"\b",
    re.IGNORECASE,
)
_SCALE_PAREN_RE = re.compile(
    r"\((?:\s*in\s+)?(?:[^)]{0,12}?\s)?" + _SCALE_ALT + r"\s*\)",
    re.IGNORECASE,
)
_SCALE_HOWMANY_RE = re.compile(
    r"\bhow\s+many\s+" + _SCALE_ALT + r"\b",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(
    r"\b(?:what\s+)?percent(?:age)?\b|\bin\s+percent\b|\bas\s+a\s+percentage\b",
    re.IGNORECASE,
)

_SCALE_WORD_TO_FACTOR = {
    "hundred": Decimal(10) ** 2,
    "hundreds": Decimal(10) ** 2,
    "thousand": Decimal(10) ** 3,
    "thousands": Decimal(10) ** 3,
    "million": Decimal(10) ** 6,
    "millions": Decimal(10) ** 6,
    "billion": Decimal(10) ** 9,
    "billions": Decimal(10) ** 9,
    "trillion": Decimal(10) ** 12,
    "trillions": Decimal(10) ** 12,
}


@dataclass(frozen=True)
class GradingContext:
    """Everything outside the two answer strings that can license a reading.

    A unit is "inferable" only from something recorded here — the question
    text, an explicit ``unit_hint`` on the task, or an explicit ``date_order``.
    Nothing is inferred from the answers themselves, because that is circular.
    """

    question: str = ""
    unit_hint: Optional[str] = None
    """e.g. ``"thousands"``, ``"percent"``, ``"km"``, ``"USD"``."""

    date_order: Optional[str] = None
    """``"MDY"`` or ``"DMY"``, when the task declares one."""

    task_id: Optional[str] = None

    def scale_hint(self) -> Optional[Tuple[Decimal, str]]:
        """Return ``(factor, source)`` for a declared/inferable scale."""
        if self.unit_hint:
            hint = self.unit_hint.strip()
            direct = _SCALE_WORD_TO_FACTOR.get(hint.lower())
            if direct is not None:
                return direct, f"unit_hint={hint!r}"
            found = lookup_scale(hint)
            if found is not None:
                return found, f"unit_hint={hint!r}"
        text = self.question or ""
        for pattern in (_SCALE_PHRASE_RE, _SCALE_PAREN_RE, _SCALE_HOWMANY_RE):
            match = pattern.search(text)
            if match:
                word = match.group(1).lower()
                return _SCALE_WORD_TO_FACTOR[word], f"question:{match.group(0).strip()!r}"
        return None

    def percent_hint(self) -> Optional[str]:
        """Return the source string when the answer is declared a percentage."""
        if self.unit_hint and self.unit_hint.strip().lower() in {
            "percent",
            "percentage",
            "%",
            "pct",
        }:
            return f"unit_hint={self.unit_hint!r}"
        match = _PERCENT_RE.search(self.question or "")
        if match:
            return f"question:{match.group(0).strip()!r}"
        return None

    def unit_hint_dimension(self) -> Optional[Tuple[str, Decimal, str]]:
        """Return ``(dimension, factor, source)`` when the hint names a unit."""
        if not self.unit_hint:
            return None
        found = lookup_unit(self.unit_hint.strip())
        if found is None:
            return None
        dimension, factor = found
        return dimension, factor, f"unit_hint={self.unit_hint!r}"


@dataclass(frozen=True)
class ValidationResult:
    """One comparison, with the evidence that produced it."""

    verdict: Verdict
    reason: str
    detail: str
    model_raw: str
    gold_raw: str
    model_normalized: str
    gold_normalized: str
    model_canonical: Optional[str] = None
    gold_canonical: Optional[str] = None
    naive_match: bool = False
    """What the incumbent lowercase/whitespace grader would have decided."""

    task_id: Optional[str] = None

    @property
    def is_match(self) -> bool:
        return self.verdict is Verdict.MATCH

    @property
    def is_ambiguous(self) -> bool:
        return self.verdict is Verdict.AMBIGUOUS_UNIT

    @property
    def is_grading_defect(self) -> bool:
        """True when this row should be surfaced rather than scored.

        Two ways to qualify: the comparison is ambiguous, or the validator and
        the incumbent grader disagree — which means the recorded score for this
        row is wrong in one direction or the other.
        """
        if self.verdict is Verdict.AMBIGUOUS_UNIT:
            return True
        return self.is_match != self.naive_match

    def as_dict(self) -> Dict[str, object]:
        return {
            "task_id": self.task_id,
            "verdict": self.verdict.value,
            "reason": self.reason,
            "detail": self.detail,
            "model_raw": self.model_raw,
            "gold_raw": self.gold_raw,
            "model_normalized": self.model_normalized,
            "gold_normalized": self.gold_normalized,
            "model_canonical": self.model_canonical,
            "gold_canonical": self.gold_canonical,
            "naive_match": self.naive_match,
            "is_grading_defect": self.is_grading_defect,
        }


@dataclass
class ValidationReport:
    """Aggregate over a result set, kept honest about the ambiguous bucket."""

    results: List[ValidationResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def matched(self) -> int:
        return sum(1 for r in self.results if r.verdict is Verdict.MATCH)

    @property
    def mismatched(self) -> int:
        return sum(1 for r in self.results if r.verdict is Verdict.MISMATCH)

    @property
    def ambiguous(self) -> int:
        return sum(1 for r in self.results if r.verdict is Verdict.AMBIGUOUS_UNIT)

    @property
    def defects(self) -> List[ValidationResult]:
        return [r for r in self.results if r.is_grading_defect]

    @property
    def naive_matched(self) -> int:
        return sum(1 for r in self.results if r.naive_match)

    def summary(self) -> Dict[str, object]:
        return {
            "total": self.total,
            "match": self.matched,
            "mismatch": self.mismatched,
            "ambiguous_unit": self.ambiguous,
            "naive_grader_match": self.naive_matched,
            "grading_defects": len(self.defects),
        }

    def render(self) -> str:
        lines = [
            # ASCII only: this is printed to consoles whose codepage is not
            # UTF-8, and a section sign turns into mojibake there.
            "output-normalization precheck",
            f"  rows                 : {self.total}",
            f"  match                : {self.matched}",
            f"  mismatch             : {self.mismatched}",
            f"  ambiguous_unit       : {self.ambiguous}",
            f"  incumbent grader ok  : {self.naive_matched}",
            f"  grading defects      : {len(self.defects)}",
        ]
        if self.defects:
            lines.append("")
            lines.append("  defects to surface (not resolved here):")
            for result in self.defects:
                lines.append(
                    f"    [{result.verdict.value:<14}] {result.reason:<30} "
                    f"model={result.model_raw!r} gold={result.gold_raw!r} "
                    f"(incumbent said {'correct' if result.naive_match else 'wrong'})"
                )
                if result.detail:
                    lines.append(f"        {result.detail}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Numeric comparison helpers
# ---------------------------------------------------------------------------


def _close(a: Decimal, b: Decimal, policy: NormalizationPolicy) -> bool:
    with localcontext() as ctx:
        ctx.prec = 50
        if a == b:
            return True
        diff = abs(a - b)
        if diff <= policy.abs_tol:
            return True
        scale = max(abs(a), abs(b))
        if scale == 0:
            return False
        return diff <= policy.rel_tol * scale


def _fmt(value: Decimal) -> str:
    with localcontext() as ctx:
        ctx.prec = 40
        normalized = value.normalize()
        text = format(normalized, "f")
    return text


def _candidates(
    number: Numeric, context: GradingContext
) -> List[Tuple[str, Decimal]]:
    """Plausible canonical values for one side, each tagged with its licence."""
    out: List[Tuple[str, Decimal]] = []
    if number.dimension is not None:
        out.append(("declared", number.base))
        # A dimensional unit names the quantity; the bare number is still a
        # legitimate reading against an un-united counterpart ("17 km" vs "17").
        if number.base != number.reported:
            out.append(("bare", number.reported))
        return out

    out.append(("declared", number.reported))
    if number.qualified:
        return out

    scale = context.scale_hint()
    if scale is not None:
        out.append((f"context_scale({scale[1]})", number.reported * scale[0]))
    percent_source = context.percent_hint()
    if percent_source is not None:
        out.append(
            (f"context_percent({percent_source})", number.reported / Decimal(100))
        )
    unit = context.unit_hint_dimension()
    if unit is not None:
        out.append((f"context_unit({unit[2]})", number.reported * unit[1]))
    return out


def _ratio_ambiguity(
    model: Numeric, gold: Numeric, policy: NormalizationPolicy
) -> Optional[Tuple[Decimal, Decimal]]:
    """Return ``(ratio, factor)`` if a unit convention could explain the gap."""
    a = model.base if model.dimension else model.reported
    b = gold.base if gold.dimension else gold.reported
    if a == 0 or b == 0:
        return None
    with localcontext() as ctx:
        ctx.prec = 50
        high, low = (abs(a), abs(b)) if abs(a) > abs(b) else (abs(b), abs(a))
        ratio = high / low
        for factor in policy.ambiguity_factors:
            if abs(ratio - factor) <= policy.ratio_tol * factor:
                return ratio, factor
    return None


def _precision_ambiguity(
    model: Numeric, gold: Numeric, policy: NormalizationPolicy
) -> Optional[str]:
    """Detect "one side is the other rounded to its own stated precision"."""
    if not policy.precision_ambiguity:
        return None
    answer_value = model.base if model.dimension else model.reported
    gold_value = gold.base if gold.dimension else gold.reported
    orderings = (
        (gold, gold_value, "gold", model, answer_value, "answer"),
        (model, answer_value, "answer", gold, gold_value, "gold"),
    )
    for coarse, coarse_value, coarse_name, fine, fine_value, fine_name in orderings:
        if coarse.decimals < 1 or fine.decimals <= coarse.decimals:
            continue
        quant = Decimal(1).scaleb(-coarse.decimals)
        if fine_value.quantize(quant) == coarse_value.quantize(quant):
            return (
                f"{fine_name} {_fmt(fine_value)} rounds to {coarse_name} "
                f"{_fmt(coarse_value)} at {coarse.decimals} dp, but neither side "
                "declares the reporting precision"
            )
    return None


def _describe(number: Numeric) -> str:
    bits = [f"value={_fmt(number.reported)}"]
    if number.scale_token:
        bits.append(f"scale={number.scale_token!r}")
    if number.percent:
        bits.append("percent=declared")
    if number.unit_token:
        bits.append(f"unit={number.unit_token!r}({number.dimension})")
    if number.currency:
        bits.append(f"currency={number.currency}")
    return " ".join(bits)


def _compare_numeric(
    model: Numeric,
    gold: Numeric,
    context: GradingContext,
    policy: NormalizationPolicy,
) -> Tuple[Verdict, str, str]:
    if model.currency and gold.currency and model.currency != gold.currency:
        return (
            Verdict.MISMATCH,
            Reason.CURRENCY_MISMATCH,
            f"answer is {model.currency}, gold is {gold.currency}; "
            "these are different quantities, not different spellings",
        )
    if (
        model.dimension
        and gold.dimension
        and model.dimension != gold.dimension
    ):
        return (
            Verdict.MISMATCH,
            Reason.DIMENSION_MISMATCH,
            f"answer is a {model.dimension} ({model.unit_token}), "
            f"gold is a {gold.dimension} ({gold.unit_token})",
        )

    if model.dimension and gold.dimension:
        pairs = [(("declared", model.base), ("declared", gold.base))]
    else:
        pairs = [
            (ma, ga)
            for ma in _candidates(model, context)
            for ga in _candidates(gold, context)
        ]

    for (mtag, mval), (gtag, gval) in pairs:
        if not _close(mval, gval, policy):
            continue
        if mtag.startswith("context") or gtag.startswith("context"):
            source = mtag if mtag.startswith("context") else gtag
            return (
                Verdict.MATCH,
                Reason.CONTEXT_UNIT_INFERRED,
                f"equal at {_fmt(mval)} once the declared unit is applied "
                f"[{source}]; {_describe(model)} vs {_describe(gold)}",
            )
        if model.dimension or gold.dimension:
            if model.dimension and gold.dimension:
                reason = Reason.UNIT_CONVERSION
            elif "bare" in (mtag, gtag):
                reason = Reason.UNIT_ANNOTATION_ONLY
            else:
                declaring = model if model.dimension else gold
                reason = (
                    Reason.UNIT_CONVERSION
                    if declaring.unit_factor != 1
                    else Reason.UNIT_ANNOTATION_ONLY
                )
            return (
                Verdict.MATCH,
                reason,
                f"equal at {_fmt(mval)}; {_describe(model)} vs {_describe(gold)}",
            )
        return (
            Verdict.MATCH,
            Reason.NUMERIC_EQUAL,
            f"equal at {_fmt(mval)}; {_describe(model)} vs {_describe(gold)}",
        )

    # Not equal under any licensed reading.  Is the gap explainable by a unit
    # convention that nobody declared?  Two ways for the answer to be "no":
    #
    #   * both sides state their own units, so a gap is a wrong answer; or
    #   * the task states the unit, so there is nothing undeclared left.  A
    #     declared unit cuts both ways — the same context that turns 17000 vs
    #     17 into a match under "in thousands" turns it into a plain mismatch
    #     under "in millions".
    context_declares_unit = bool(
        context.scale_hint()
        or context.percent_hint()
        or context.unit_hint_dimension()
    )
    if not (model.qualified and gold.qualified) and not context_declares_unit:
        ratio = _ratio_ambiguity(model, gold, policy)
        if ratio is not None:
            _, factor = ratio
            one_percent = model.percent != gold.percent
            if factor == Decimal(100) and one_percent:
                reason = Reason.PERCENT_CONVENTION_UNDECLARED
                explain = (
                    "one side is a declared percentage and the other is a bare "
                    "number; whether the bare side is a fraction or a percentage "
                    "is not stated anywhere"
                )
            else:
                reason = Reason.UNIT_SCALE_UNDECLARED
                explain = (
                    f"the two differ by exactly {_fmt(factor)}x, which a unit "
                    "convention would explain, but no unit is declared on the "
                    "unqualified side and the question does not state one"
                )
            return (
                Verdict.AMBIGUOUS_UNIT,
                reason,
                f"{explain}; {_describe(model)} vs {_describe(gold)}",
            )

    precision = _precision_ambiguity(model, gold, policy)
    if precision is not None:
        return Verdict.AMBIGUOUS_UNIT, Reason.PRECISION_UNDECLARED, precision

    return (
        Verdict.MISMATCH,
        Reason.NUMERIC_DIFFERENT,
        f"{_describe(model)} vs {_describe(gold)}; no unit convention "
        "reconciles them",
    )


def _compare_dates(
    model: DateReading,
    gold: DateReading,
    context: GradingContext,
) -> Tuple[Verdict, str, str]:
    order = (context.date_order or "").upper() or None
    if order in {"MDY", "DMY"}:
        resolved = []
        for reading in (model, gold):
            picked = dict(reading.by_order).get(order)
            resolved.append(picked if picked is not None else reading.candidates[0])
        if resolved[0] == resolved[1]:
            return (
                Verdict.MATCH,
                Reason.DATE_EQUAL,
                f"both resolve to {resolved[0].isoformat()} under declared "
                f"date order {order}",
            )
        return (
            Verdict.MISMATCH,
            Reason.DATE_DIFFERENT,
            f"{resolved[0].isoformat()} vs {resolved[1].isoformat()} under "
            f"declared date order {order}",
        )

    model_set = set(model.candidates)
    gold_set = set(gold.candidates)
    if model_set == gold_set:
        return (
            Verdict.MATCH,
            Reason.DATE_EQUAL,
            f"same date(s): {', '.join(d.isoformat() for d in sorted(model_set))}",
        )
    overlap = model_set & gold_set
    if overlap:
        return (
            Verdict.AMBIGUOUS_UNIT,
            Reason.DATE_ORDER_UNDECLARED,
            "the two agree only under one day/month reading "
            f"({', '.join(d.isoformat() for d in sorted(overlap))}); no date "
            "order is declared on the task",
        )
    return (
        Verdict.MISMATCH,
        Reason.DATE_DIFFERENT,
        f"{sorted(d.isoformat() for d in model_set)} vs "
        f"{sorted(d.isoformat() for d in gold_set)}",
    )


# ---------------------------------------------------------------------------
# The validator
# ---------------------------------------------------------------------------


class OutputNormalizationValidator:
    """Runs ahead of grading and reports what the grader is about to get wrong."""

    def __init__(self, policy: Optional[NormalizationPolicy] = None) -> None:
        self.policy = policy or NormalizationPolicy()

    # -- public API --------------------------------------------------------

    def validate(
        self,
        model_answer: object,
        gold_answer: object,
        context: Optional[GradingContext] = None,
    ) -> ValidationResult:
        ctx = context or GradingContext()
        model_raw = "" if model_answer is None else str(model_answer)
        gold_raw = "" if gold_answer is None else str(gold_answer)
        model_norm = clean_text(model_raw)
        gold_norm = clean_text(gold_raw)
        naive = naive_normalize(model_raw) == naive_normalize(gold_raw)

        verdict, reason, detail, mcanon, gcanon = self._decide(
            model_norm, gold_norm, ctx, allow_list=True
        )
        return ValidationResult(
            verdict=verdict,
            reason=reason,
            detail=detail,
            model_raw=model_raw,
            gold_raw=gold_raw,
            model_normalized=model_norm,
            gold_normalized=gold_norm,
            model_canonical=mcanon,
            gold_canonical=gcanon,
            naive_match=naive,
            task_id=ctx.task_id,
        )

    def validate_records(
        self,
        records: Iterable[Mapping[str, object]],
        *,
        model_key: str = "model_answer",
        gold_key: str = "gold_answer",
        question_key: str = "question",
        unit_hint_key: str = "unit_hint",
        date_order_key: str = "date_order",
        task_id_key: str = "task_id",
    ) -> ValidationReport:
        """Precheck a whole results file (GAIA's ``results.jsonl`` shape)."""
        report = ValidationReport()
        for record in records:
            ctx = GradingContext(
                question=str(record.get(question_key) or ""),
                unit_hint=(
                    str(record[unit_hint_key])
                    if record.get(unit_hint_key) not in (None, "")
                    else None
                ),
                date_order=(
                    str(record[date_order_key])
                    if record.get(date_order_key) not in (None, "")
                    else None
                ),
                task_id=(
                    str(record[task_id_key])
                    if record.get(task_id_key) not in (None, "")
                    else None
                ),
            )
            report.results.append(
                self.validate(record.get(model_key), record.get(gold_key), ctx)
            )
        return report

    # -- internals ---------------------------------------------------------

    def _decide(
        self,
        model_norm: str,
        gold_norm: str,
        ctx: GradingContext,
        *,
        allow_list: bool,
    ) -> Tuple[Verdict, str, str, Optional[str], Optional[str]]:
        if model_norm == gold_norm:
            return (
                Verdict.MATCH,
                Reason.IDENTICAL,
                "identical after whitespace/case/wrapper normalization",
                model_norm,
                gold_norm,
            )

        model_num = parse_numeric(model_norm)
        gold_num = parse_numeric(gold_norm)
        if model_num is not None and gold_num is not None:
            verdict, reason, detail = _compare_numeric(
                model_num, gold_num, ctx, self.policy
            )
            return (
                verdict,
                reason,
                detail,
                _fmt(model_num.base),
                _fmt(gold_num.base),
            )

        model_bool = parse_boolean(model_norm)
        gold_bool = parse_boolean(gold_norm)
        if self.policy.allow_boolean_numeric:
            if model_bool is None and gold_bool is not None:
                model_bool = self._numeric_boolean(model_num)
            elif gold_bool is None and model_bool is not None:
                gold_bool = self._numeric_boolean(gold_num)
        if model_bool is not None and gold_bool is not None:
            if model_bool == gold_bool:
                return (
                    Verdict.MATCH,
                    Reason.BOOLEAN_EQUAL,
                    f"both denote {model_bool}",
                    str(model_bool),
                    str(gold_bool),
                )
            return (
                Verdict.MISMATCH,
                Reason.BOOLEAN_DIFFERENT,
                f"{model_bool} vs {gold_bool}",
                str(model_bool),
                str(gold_bool),
            )

        model_date = parse_date(model_norm)
        gold_date = parse_date(gold_norm)
        if model_date is not None and gold_date is not None:
            verdict, reason, detail = _compare_dates(model_date, gold_date, ctx)
            return (
                verdict,
                reason,
                detail,
                ",".join(d.isoformat() for d in model_date.candidates),
                ",".join(d.isoformat() for d in gold_date.candidates),
            )

        # Case folding is applied only after every typed reading has been
        # tried, because case is load-bearing while a value is still a number:
        # "17 M" is seventeen million and "17 m" is seventeen metres, and those
        # must reach _compare_numeric as different values rather than collapse
        # into one string here.
        if model_norm.casefold() == gold_norm.casefold():
            return (
                Verdict.MATCH,
                Reason.TEXT_NORMALIZED,
                "equal after whitespace/case/wrapper normalization",
                model_norm.casefold(),
                gold_norm.casefold(),
            )

        if allow_list:
            model_list = split_list(model_norm)
            gold_list = split_list(gold_norm)
            if model_list is not None and gold_list is not None:
                return self._compare_lists(model_list, gold_list, ctx)

        if (model_num is None) != (gold_num is None):
            return (
                Verdict.MISMATCH,
                Reason.TYPE_MISMATCH,
                "one side is a number and the other is not; the validator does "
                "not strip qualifiers off an answer to make it numeric",
                model_norm,
                gold_norm,
            )

        return (
            Verdict.MISMATCH,
            Reason.TEXT_DIFFERENT,
            "different text after normalization",
            model_norm.lower(),
            gold_norm.lower(),
        )

    @staticmethod
    def _numeric_boolean(number: Optional[Numeric]) -> Optional[bool]:
        if number is None or number.qualified:
            return None
        value = number.reported
        if value == 1:
            return True
        if value == 0:
            return False
        return None

    def _compare_lists(
        self,
        model_items: Sequence[str],
        gold_items: Sequence[str],
        ctx: GradingContext,
    ) -> Tuple[Verdict, str, str, Optional[str], Optional[str]]:
        model_canon = " | ".join(model_items)
        gold_canon = " | ".join(gold_items)
        if len(model_items) != len(gold_items):
            return (
                Verdict.MISMATCH,
                Reason.LIST_LENGTH_DIFFERENT,
                f"{len(model_items)} items vs {len(gold_items)}",
                model_canon,
                gold_canon,
            )

        remaining = list(model_items)
        ambiguous_detail: Optional[str] = None
        for gold_item in gold_items:
            picked: Optional[int] = None
            fallback: Optional[Tuple[int, str]] = None
            search = remaining if self.policy.allow_list_reordering else remaining[:1]
            for index, model_item in enumerate(search):
                verdict, reason, detail, _, _ = self._decide(
                    model_item, gold_item, ctx, allow_list=False
                )
                if verdict is Verdict.MATCH:
                    picked = index
                    break
                if verdict is Verdict.AMBIGUOUS_UNIT and fallback is None:
                    fallback = (index, f"{reason}: {detail}")
            if picked is not None:
                remaining.pop(picked)
                continue
            if fallback is not None:
                remaining.pop(fallback[0])
                ambiguous_detail = ambiguous_detail or fallback[1]
                continue
            return (
                Verdict.MISMATCH,
                Reason.LIST_DIFFERENT,
                f"no counterpart for gold item {gold_item!r}",
                model_canon,
                gold_canon,
            )

        if ambiguous_detail is not None:
            return (
                Verdict.AMBIGUOUS_UNIT,
                Reason.LIST_AMBIGUOUS,
                f"at least one element is unit-ambiguous - {ambiguous_detail}",
                model_canon,
                gold_canon,
            )
        return (
            Verdict.MATCH,
            Reason.LIST_EQUAL,
            "every gold element has an equivalent answer element",
            model_canon,
            gold_canon,
        )


def validate_answer(
    model_answer: object,
    gold_answer: object,
    context: Optional[GradingContext] = None,
    policy: Optional[NormalizationPolicy] = None,
) -> ValidationResult:
    """Module-level convenience wrapper around :class:`OutputNormalizationValidator`."""
    return OutputNormalizationValidator(policy).validate(
        model_answer, gold_answer, context
    )
