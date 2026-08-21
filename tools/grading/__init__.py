#!/usr/bin/env python3
"""Pre-grading output normalization and unit interpretation.


Run this *before* a grader compares an answer to a gold field.  It answers one
question — "can these two strings be compared at all, and if so do they agree?"
— with a three-way verdict:

    >>> from tools.grading import validate_answer, Verdict
    >>> validate_answer("17000", "17").verdict          # no unit anywhere
    <Verdict.AMBIGUOUS_UNIT: 'ambiguous_unit'>
    >>> from tools.grading import GradingContext
    >>> ctx = GradingContext(question="Units sold, in thousands?")
    >>> validate_answer("17000", "17", ctx).verdict      # unit is inferable
    <Verdict.MATCH: 'match'>
    >>> validate_answer("17000", "18").verdict           # a real error
    <Verdict.MISMATCH: 'mismatch'>

``AMBIGUOUS_UNIT`` is a defect in the *benchmark row*, to be surfaced and
fixed at the task definition.  It is never a pass.
"""

from __future__ import annotations

from .normalize import (
    DateReading,
    Numeric,
    clean_text,
    naive_normalize,
    parse_boolean,
    parse_date,
    parse_number_words,
    parse_numeric,
    split_list,
)
from .validator import (
    GradingContext,
    NormalizationPolicy,
    OutputNormalizationValidator,
    Reason,
    ValidationReport,
    ValidationResult,
    Verdict,
    validate_answer,
)

__all__ = [
    "DateReading",
    "GradingContext",
    "NormalizationPolicy",
    "Numeric",
    "OutputNormalizationValidator",
    "Reason",
    "ValidationReport",
    "ValidationResult",
    "Verdict",
    "clean_text",
    "naive_normalize",
    "parse_boolean",
    "parse_date",
    "parse_number_words",
    "parse_numeric",
    "split_list",
    "validate_answer",
]
