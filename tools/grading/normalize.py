#!/usr/bin/env python3
"""Parsing and canonicalization for the pre-grading output validator.


This module turns a raw answer string into one of four typed readings —
number, boolean, date, or plain text — **without deciding whether two answers
agree**.  The comparison and the three-way verdict live in
:mod:`tools.grading.validator`; keeping them apart is what makes it possible to
say "these two parsed fine and still cannot be compared" instead of silently
coercing one into the other.

Nothing here is lossy on purpose.  :class:`Numeric` keeps the declared scale
token, the declared percent marker, the declared currency and the declared
dimensional unit as separate fields, because "17 declared as thousands" and
"17000 written out" are the same value but *not* the same evidence.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Sequence, Tuple

from .units import (
    BOOL_FALSE,
    BOOL_TRUE,
    CURRENCY_SYMBOLS,
    MONTHS,
    PERCENT_TOKENS,
    WORD_SCALES,
    WORD_TENS,
    WORD_UNITS,
    lookup_currency,
    lookup_scale,
    lookup_unit,
)

__all__ = [
    "Numeric",
    "DateReading",
    "clean_text",
    "naive_normalize",
    "parse_numeric",
    "parse_boolean",
    "parse_date",
    "parse_number_words",
    "split_list",
]


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")

_ANSWER_PREFIX_RE = re.compile(
    r"^(?:the\s+)?(?:final\s+)?answer(?:\s+is)?\s*[:\-]?\s*",
    re.IGNORECASE,
)

#: A leading ':' or '=' is extraction residue — the recorded Level-1 failure's
#: ``model_answer`` is literally ``": 17000"``, because the final-answer marker
#: was split off and the separator was left behind.  It is never part of an
#: answer, so it is removed rather than compared.
_LEADING_RESIDUE_RE = re.compile(r"^[:=]+\s*")

_WRAPPERS = "\"'`* \t\r\n“”‘’«»"

#: Characters that mean "minus" but are not U+002D.
_DASH_MAP = str.maketrans(
    {
        "−": "-",  # minus sign
        "‒": "-",  # figure dash
        "–": "-",  # en dash
        "—": "-",  # em dash
        " ": " ",  # nbsp
        " ": " ",  # narrow nbsp
        " ": " ",  # thin space
        " ": " ",  # figure space
    }
)


def naive_normalize(value: object) -> str:
    """Reproduce the incumbent grader's normalization, byte for byte.

    Mirrors ``benchmarks/gaia_runner.py::_normalize_answer`` as it stands on
    disk: strip, collapse whitespace, lowercase.  It is kept here so a report
    can state what the *unfixed* grader would have decided, which is how a
    grading defect is surfaced rather than merely avoided.
    """
    if value is None:
        return ""
    text = str(value).strip()
    text = _WS_RE.sub(" ", text)
    return text.lower()


def clean_text(value: object, *, strip_answer_prefix: bool = True) -> str:
    """Normalize whitespace, case, wrappers and lookalike punctuation.

    This is the §12 "whitespace and case" layer, plus the markdown/quote
    wrappers and answer-prefix boilerplate that real model output carries.  It
    is *not* semantic: it never changes a number, a unit or a word.
    """
    if value is None:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_DASH_MAP)
    text = _WS_RE.sub(" ", text).strip()
    text = text.strip(_WRAPPERS)
    if strip_answer_prefix:
        stripped = _ANSWER_PREFIX_RE.sub("", text, count=1)
        # Never let the prefix stripper eat the whole answer.
        if stripped.strip():
            text = stripped
        residue = _LEADING_RESIDUE_RE.sub("", text, count=1)
        if residue.strip():
            text = residue
    text = text.strip(_WRAPPERS)
    # Trailing sentence punctuation, but never a trailing '%'.
    text = re.sub(r"[.!;,:]+$", "", text).strip()
    return _WS_RE.sub(" ", text).strip()


# ---------------------------------------------------------------------------
# Numeric reading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Numeric:
    """A number with everything that was *declared* about it kept separate."""

    magnitude: Decimal
    """The bare number as written, before any scale multiplier."""

    scale: Decimal = Decimal(1)
    """Multiplier contributed by a declared scale token (``k``, ``million``)."""

    scale_token: Optional[str] = None
    """The literal scale token, or ``None`` if none was declared."""

    percent: bool = False
    """True when the value carried an explicit ``%`` / ``percent`` marker."""

    currency: Optional[str] = None
    """ISO currency code, when one was declared."""

    unit_token: Optional[str] = None
    """The literal dimensional-unit token, when one was declared."""

    dimension: Optional[str] = None
    """``length`` / ``mass`` / ``time`` / ``data``, when a unit was declared."""

    unit_factor: Decimal = Decimal(1)
    """Conversion of ``unit_token`` to its dimension's base unit."""

    decimals: int = 0
    """Digits written after the decimal separator (precision as *stated*)."""

    raw: str = ""

    @property
    def reported(self) -> Decimal:
        """The number the answer reports, with declared scale and % applied.

        ``17k`` reports 17000.  ``17%`` reports 0.17.  ``17 km`` reports 17 —
        a dimensional unit names the quantity, it does not restate the number.
        """
        value = self.magnitude * self.scale
        if self.percent:
            value = value / Decimal(100)
        return value

    @property
    def base(self) -> Decimal:
        """``reported`` converted into the base unit of its dimension."""
        return self.reported * self.unit_factor

    @property
    def qualified(self) -> bool:
        """True when this side declares what unit it is in.

        An unqualified number is the whole reason :class:`Verdict` has a third
        value: ``17000`` and ``17`` can only be reconciled if *somebody* said
        what the unit was.
        """
        return bool(self.scale_token) or self.percent or self.dimension is not None


#: Number bodies, most specific first.  Every alternative ends with ``(?!\d)``
#: so a group pattern cannot swallow a prefix of a longer plain number
#: (``3.14159`` must not read as the European thousands group ``3.141``).
#:
#: The dot-as-thousands-separator reading is deliberately restricted to the
#: spellings that cannot also be a decimal: two or more dot groups
#: (``1.234.567``), or a dot group followed by a decimal comma
#: (``1.234,56``).  A lone ``1.234`` stays a decimal, which is the English
#: reading benchmark gold fields are written in.  When the two conventions
#: really do collide the validator reports it — ``1,234`` against ``1.234``
#: comes out as ``ambiguous_unit``, not as a match and not as a failure.
_BODY_RE = re.compile(
    r"""
    (?P<comma_group>\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?!\d)         # 1,234,567.89
  | (?P<dot_group>
        \d{1,3}(?:\.\d{3}){2,}(?:,\d+)?
      | \d{1,3}(?:\.\d{3})+,\d+
    )(?!\d)                                                     # 1.234.567,89
  | (?P<space_group>\d{1,3}(?:[ ]\d{3})+(?:[.,]\d+)?)(?!\d)     # 1 234 567,89
  | (?P<plain>\d+(?:[.,]\d+)?)(?!\d)                            # 1234.56
    """,
    re.VERBOSE,
)

_EXP_RE = re.compile(
    r"""
    ^\s*
    (?:
        [eE](?P<e1>[+-]?\d+)
      | [x×*]\s*10\s*(?:\^|\*\*)?\s*(?P<e2>[+-]?\d+)
    )
    """,
    re.VERBOSE,
)


def _split_body(body: str, kind: str) -> Tuple[Decimal, int]:
    """Return ``(value, decimals_written)`` for a matched number body."""
    if kind == "comma_group":
        cleaned = body.replace(",", "")
    elif kind == "dot_group":
        cleaned = body.replace(".", "").replace(",", ".")
    elif kind == "space_group":
        cleaned = body.replace(" ", "")
        if cleaned.count(",") == 1 and "." not in cleaned:
            cleaned = cleaned.replace(",", ".")
    else:  # plain
        cleaned = body
        if "," in cleaned:
            # A three-digit group would have matched comma_group first, so a
            # comma surviving to here is a decimal comma.
            cleaned = cleaned.replace(",", ".")
    decimals = len(cleaned.split(".", 1)[1]) if "." in cleaned else 0
    return Decimal(cleaned), decimals


def _strip_leading_currency(text: str) -> Tuple[str, Optional[str]]:
    for symbol, code in CURRENCY_SYMBOLS:
        if text.startswith(symbol):
            return text[len(symbol) :].lstrip(), code
    match = re.match(r"^([A-Za-z]{3})\s*(?=[\d+\-.])", text)
    if match:
        code = lookup_currency(match.group(1))
        if code:
            return text[match.end() :].lstrip(), code
    return text, None


def parse_number_words(text: str) -> Optional[Tuple[Decimal, Optional[str]]]:
    """Parse an English cardinal such as ``seventeen thousand``.

    Returns ``(value, largest_scale_word_used)``.  The scale word is returned
    because ``seventeen thousand`` *declares* its unit while ``17000`` does
    not, and the validator needs to know the difference.
    """
    tokens = [t for t in re.split(r"[\s\-]+", text.strip().lower()) if t]
    if not tokens:
        return None
    sign = Decimal(1)
    if tokens[0] in {"minus", "negative"}:
        sign = Decimal(-1)
        tokens = tokens[1:]
    if not tokens:
        return None
    total = Decimal(0)
    current = Decimal(0)
    saw_any = False
    biggest: Optional[str] = None
    biggest_value = Decimal(0)
    for token in tokens:
        if token == "and":
            continue
        if token in WORD_UNITS:
            current += Decimal(WORD_UNITS[token])
            saw_any = True
        elif token in WORD_TENS:
            current += Decimal(WORD_TENS[token])
            saw_any = True
        elif token in ("hundred", "hundreds"):
            current = (current if current else Decimal(1)) * Decimal(100)
            saw_any = True
        elif token in WORD_SCALES:
            factor = WORD_SCALES[token]
            total += (current if current else Decimal(1)) * factor
            current = Decimal(0)
            saw_any = True
            if factor > biggest_value:
                biggest_value = factor
                biggest = token
        else:
            return None
    if not saw_any:
        return None
    return sign * (total + current), biggest


def parse_numeric(text: str) -> Optional[Numeric]:
    """Parse a numeric answer, or return ``None`` if it is not one.

    Handles thousands separators, currency symbols and codes, ``k``/``M``/
    ``bn``-style scale suffixes, spelled-out scale words, percentages,
    scientific notation in both ``1.7e4`` and ``1.7 x 10^4`` spellings,
    accounting parentheses for negatives, and English number words.

    Returns ``None`` — rather than guessing — when the string carries a
    trailing token that is not a recognised scale, unit or currency.  ``17
    apples`` is text, not a number with a decoration, and treating it as a
    number would let ``17 apples`` match ``17 oranges``.
    """
    source = clean_text(text)
    if not source:
        return None

    working = source
    negate = False

    # Accounting negatives: (1,234)
    if working.startswith("(") and working.endswith(")") and len(working) > 2:
        inner = working[1:-1].strip()
        if inner and (inner[0].isdigit() or inner[0] in "+-$"):
            working = inner
            negate = True

    working, currency = _strip_leading_currency(working)

    sign = Decimal(-1) if negate else Decimal(1)
    if working[:1] in ("+", "-"):
        if working[0] == "-":
            sign = -sign
        working = working[1:].lstrip()
        working, cur2 = _strip_leading_currency(working)
        currency = currency or cur2

    if not working:
        return None

    match = _BODY_RE.match(working)
    if match is None:
        words = parse_number_words(source)
        if words is None:
            return None
        value, scale_word = words
        scale = WORD_SCALES.get(scale_word or "", Decimal(1))
        return Numeric(
            magnitude=value / scale if scale != 1 else value,
            scale=scale,
            scale_token=scale_word,
            raw=source,
        )

    kind = match.lastgroup or "plain"
    try:
        magnitude, decimals = _split_body(match.group(kind), kind)
    except InvalidOperation:
        return None
    rest = working[match.end() :]

    exp_match = _EXP_RE.match(rest)
    if exp_match:
        exponent = int(exp_match.group("e1") or exp_match.group("e2"))
        magnitude = magnitude * (Decimal(10) ** exponent)
        rest = rest[exp_match.end() :]

    magnitude = sign * magnitude

    scale = Decimal(1)
    scale_token: Optional[str] = None
    percent = False
    unit_token: Optional[str] = None
    dimension: Optional[str] = None
    unit_factor = Decimal(1)

    rest = rest.strip()
    if rest.startswith("%"):
        percent = True
        rest = rest[1:].strip()

    for token in [t for t in rest.split() if t]:
        bare = token.strip(".,")
        if not bare:
            continue
        if bare in PERCENT_TOKENS or bare.lower() in PERCENT_TOKENS:
            if percent:
                return None
            percent = True
            continue
        found_scale = lookup_scale(bare)
        if found_scale is not None and scale_token is None:
            scale = found_scale
            scale_token = bare
            continue
        found_unit = lookup_unit(bare)
        if found_unit is not None and dimension is None:
            dimension, unit_factor = found_unit
            unit_token = bare
            continue
        found_currency = lookup_currency(bare)
        if found_currency is not None and currency is None:
            currency = found_currency
            continue
        # Unrecognised trailing token: this is not a bare number.
        return None

    return Numeric(
        magnitude=magnitude,
        scale=scale,
        scale_token=scale_token,
        percent=percent,
        currency=currency,
        unit_token=unit_token,
        dimension=dimension,
        unit_factor=unit_factor,
        decimals=decimals,
        raw=source,
    )


# ---------------------------------------------------------------------------
# Boolean reading
# ---------------------------------------------------------------------------


def parse_boolean(text: str) -> Optional[bool]:
    """Parse a boolean word.  Numerals are deliberately *not* accepted here.

    ``1`` only becomes ``True`` when the value it is being compared against is
    a boolean word; that decision belongs to the validator, which can see both
    sides, not to a single-sided parser.
    """
    token = clean_text(text).lower()
    if token in BOOL_TRUE:
        return True
    if token in BOOL_FALSE:
        return False
    return None


# ---------------------------------------------------------------------------
# Date reading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DateReading:
    """One or more calendar dates a string could denote."""

    candidates: Tuple[date, ...]
    ambiguous: bool
    by_order: Tuple[Tuple[str, date], ...] = ()
    """``(("MDY", d1), ("DMY", d2))`` for a numeric ``a/b/c`` spelling."""

    raw: str = ""


_ISO_RE = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$")
_NUM_DATE_RE = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$")
_MONTH_FIRST_RE = re.compile(r"^([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})$")
_DAY_FIRST_RE = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([A-Za-z]+)\.?,?\s+(\d{4})$")


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date(text: str) -> Optional[DateReading]:
    """Parse a date, keeping day/month ambiguity as ambiguity.

    ``01/02/2026`` yields **two** candidates.  The validator turns that into
    ``AMBIGUOUS_UNIT`` rather than picking a locale, because picking one is
    exactly the silent coercion this validator exists to prevent.
    """
    source = clean_text(text)
    if not source:
        return None

    iso = _ISO_RE.match(source)
    if iso:
        found = _safe_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        return DateReading((found,), False, (), source) if found else None

    num = _NUM_DATE_RE.match(source)
    if num:
        first, second, year = int(num.group(1)), int(num.group(2)), int(num.group(3))
        mdy = _safe_date(year, first, second)
        dmy = _safe_date(year, second, first)
        by_order: List[Tuple[str, date]] = []
        if mdy:
            by_order.append(("MDY", mdy))
        if dmy:
            by_order.append(("DMY", dmy))
        if not by_order:
            return None
        unique = tuple(dict.fromkeys(d for _, d in by_order))
        return DateReading(unique, len(unique) > 1, tuple(by_order), source)

    month_first = _MONTH_FIRST_RE.match(source)
    if month_first:
        month = MONTHS.get(month_first.group(1).lower())
        if month:
            found = _safe_date(int(month_first.group(3)), month, int(month_first.group(2)))
            if found:
                return DateReading((found,), False, (), source)

    day_first = _DAY_FIRST_RE.match(source)
    if day_first:
        month = MONTHS.get(day_first.group(2).lower())
        if month:
            found = _safe_date(int(day_first.group(3)), month, int(day_first.group(1)))
            if found:
                return DateReading((found,), False, (), source)

    return None


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


def split_list(text: str) -> Optional[Sequence[str]]:
    """Split a delimited answer, or return ``None`` if it is not a list.

    A string that parses as a single number is never a list, so ``1,234`` stays
    one value.
    """
    source = clean_text(text)
    if not source:
        return None
    if parse_numeric(source) is not None:
        return None
    if ";" in source:
        parts = [p.strip() for p in source.split(";")]
    elif "," in source:
        parts = [p.strip() for p in source.split(",")]
    else:
        return None
    parts = [p for p in parts if p]
    return parts if len(parts) > 1 else None
