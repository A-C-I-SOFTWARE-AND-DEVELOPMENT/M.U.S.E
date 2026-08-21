#!/usr/bin/env python3
"""Unit, scale, currency and boolean tables for the pre-grading normalizer.


These tables are deliberately conservative.  A token only appears here when its
meaning is unambiguous in the context "a benchmark answer field".  Tokens whose
meaning is genuinely contested are **left out**, because the whole point of the
validator is that an unresolvable reading must surface as
``Verdict.AMBIGUOUS_UNIT`` rather than be silently coerced into a match.

Deliberate omissions, each for a reason:

``ton`` / ``tons``
    US short ton (907.18474 kg) and metric tonne (1000 kg) are both in common
    use.  ``tonne`` is listed, ``ton`` is not.
``mm`` as a scale word
    Finance writes ``$5mm`` for five million; SI writes ``5 mm`` for five
    millimetres.  Only the SI reading is listed.
``b`` (lowercase)
    ``b`` is bit, byte and billion depending on who is writing.  Only the
    uppercase ``B`` billion reading is listed, and byte quantities are only
    recognised in their unambiguous multi-letter forms (``KB``, ``MB``, ...).
``pound`` / ``pounds``
    Mass and currency.  Listed as mass only; GBP is recognised from ``£``
    and the ISO code ``GBP``.
Temperature units
    Conversion is affine, not multiplicative, and the tables here are pure
    scale factors.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Optional, Tuple

__all__ = [
    "SCALE_LETTERS",
    "SCALE_WORDS",
    "PERCENT_TOKENS",
    "CURRENCY_SYMBOLS",
    "CURRENCY_CODES",
    "CURRENCY_WORDS",
    "UNIT_SYMBOLS",
    "UNIT_WORDS",
    "BOOL_TRUE",
    "BOOL_FALSE",
    "MONTHS",
    "WORD_UNITS",
    "WORD_TENS",
    "WORD_SCALES",
    "lookup_scale",
    "lookup_unit",
    "lookup_currency",
]

_D = Decimal


# ---------------------------------------------------------------------------
# Scale multipliers
# ---------------------------------------------------------------------------

#: Single-letter scale suffixes.  Matched **case-sensitively** so that ``1.5M``
#: reads as 1.5 million while ``1.5 m`` reads as 1.5 metres.
SCALE_LETTERS: Dict[str, Decimal] = {
    "k": _D(10) ** 3,
    "K": _D(10) ** 3,
    "M": _D(10) ** 6,
    "B": _D(10) ** 9,
    "T": _D(10) ** 12,
}

#: Multi-character scale tokens.  Matched case-insensitively.
SCALE_WORDS: Dict[str, Decimal] = {
    "hundred": _D(10) ** 2,
    "hundreds": _D(10) ** 2,
    "thousand": _D(10) ** 3,
    "thousands": _D(10) ** 3,
    "thsd": _D(10) ** 3,
    "million": _D(10) ** 6,
    "millions": _D(10) ** 6,
    "mn": _D(10) ** 6,
    "billion": _D(10) ** 9,
    "billions": _D(10) ** 9,
    "bn": _D(10) ** 9,
    "trillion": _D(10) ** 12,
    "trillions": _D(10) ** 12,
    "tn": _D(10) ** 12,
}

#: Tokens that mark a value as a percentage.
PERCENT_TOKENS = frozenset({"%", "percent", "percents", "percentage", "pct", "pc"})


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

CURRENCY_SYMBOLS: Tuple[Tuple[str, str], ...] = (
    ("US$", "USD"),
    ("C$", "CAD"),
    ("A$", "AUD"),
    ("NZ$", "NZD"),
    ("HK$", "HKD"),
    ("R$", "BRL"),
    ("$", "USD"),
    ("€", "EUR"),  # euro sign
    ("£", "GBP"),  # pound sign
    ("¥", "JPY"),  # yen sign
    ("₹", "INR"),  # indian rupee sign
    ("₩", "KRW"),  # won sign
)

CURRENCY_CODES = frozenset(
    {
        "USD",
        "EUR",
        "GBP",
        "JPY",
        "CNY",
        "INR",
        "CAD",
        "AUD",
        "NZD",
        "CHF",
        "SEK",
        "NOK",
        "BRL",
        "KRW",
        "HKD",
        "MXN",
        "ZAR",
    }
)

#: Spelled-out currency names whose ISO mapping is not contested.
CURRENCY_WORDS: Dict[str, str] = {
    "dollar": "USD",
    "dollars": "USD",
    "euro": "EUR",
    "euros": "EUR",
    "yen": "JPY",
    "rupee": "INR",
    "rupees": "INR",
    "yuan": "CNY",
    "won": "KRW",
}


# ---------------------------------------------------------------------------
# Dimensional units
# ---------------------------------------------------------------------------
# value: (dimension, factor to the dimension's base unit)

#: Case-sensitive symbol forms.
UNIT_SYMBOLS: Dict[str, Tuple[str, Decimal]] = {
    # length, base metre
    "m": ("length", _D(1)),
    "km": ("length", _D(1000)),
    "cm": ("length", _D("0.01")),
    "mm": ("length", _D("0.001")),
    "um": ("length", _D("0.000001")),
    "nm": ("length", _D("0.000000001")),
    "mi": ("length", _D("1609.344")),
    "ft": ("length", _D("0.3048")),
    "in": ("length", _D("0.0254")),
    "yd": ("length", _D("0.9144")),
    "nmi": ("length", _D(1852)),
    # mass, base kilogram
    "kg": ("mass", _D(1)),
    "g": ("mass", _D("0.001")),
    "mg": ("mass", _D("0.000001")),
    "lb": ("mass", _D("0.45359237")),
    "lbs": ("mass", _D("0.45359237")),
    "oz": ("mass", _D("0.028349523125")),
    # time, base second
    "s": ("time", _D(1)),
    "sec": ("time", _D(1)),
    "ms": ("time", _D("0.001")),
    "min": ("time", _D(60)),
    "h": ("time", _D(3600)),
    "hr": ("time", _D(3600)),
    "hrs": ("time", _D(3600)),
    # data, base byte.  Only multi-letter forms; bare "b"/"B" is left to the
    # billion reading in SCALE_LETTERS.
    "kB": ("data", _D(10) ** 3),
    "KB": ("data", _D(10) ** 3),
    "MB": ("data", _D(10) ** 6),
    "GB": ("data", _D(10) ** 9),
    "TB": ("data", _D(10) ** 12),
    "KiB": ("data", _D(1024)),
    "MiB": ("data", _D(1024) ** 2),
    "GiB": ("data", _D(1024) ** 3),
    "TiB": ("data", _D(1024) ** 4),
}

#: Case-insensitive spelled-out forms.
UNIT_WORDS: Dict[str, Tuple[str, Decimal]] = {
    "meter": ("length", _D(1)),
    "meters": ("length", _D(1)),
    "metre": ("length", _D(1)),
    "metres": ("length", _D(1)),
    "kilometer": ("length", _D(1000)),
    "kilometers": ("length", _D(1000)),
    "kilometre": ("length", _D(1000)),
    "kilometres": ("length", _D(1000)),
    "centimeter": ("length", _D("0.01")),
    "centimeters": ("length", _D("0.01")),
    "centimetre": ("length", _D("0.01")),
    "centimetres": ("length", _D("0.01")),
    "millimeter": ("length", _D("0.001")),
    "millimeters": ("length", _D("0.001")),
    "millimetre": ("length", _D("0.001")),
    "millimetres": ("length", _D("0.001")),
    "mile": ("length", _D("1609.344")),
    "miles": ("length", _D("1609.344")),
    "foot": ("length", _D("0.3048")),
    "feet": ("length", _D("0.3048")),
    "inch": ("length", _D("0.0254")),
    "inches": ("length", _D("0.0254")),
    "yard": ("length", _D("0.9144")),
    "yards": ("length", _D("0.9144")),
    "kilogram": ("mass", _D(1)),
    "kilograms": ("mass", _D(1)),
    "gram": ("mass", _D("0.001")),
    "grams": ("mass", _D("0.001")),
    "milligram": ("mass", _D("0.000001")),
    "milligrams": ("mass", _D("0.000001")),
    "tonne": ("mass", _D(1000)),
    "tonnes": ("mass", _D(1000)),
    "pound": ("mass", _D("0.45359237")),
    "pounds": ("mass", _D("0.45359237")),
    "ounce": ("mass", _D("0.028349523125")),
    "ounces": ("mass", _D("0.028349523125")),
    "second": ("time", _D(1)),
    "seconds": ("time", _D(1)),
    "millisecond": ("time", _D("0.001")),
    "milliseconds": ("time", _D("0.001")),
    "minute": ("time", _D(60)),
    "minutes": ("time", _D(60)),
    "hour": ("time", _D(3600)),
    "hours": ("time", _D(3600)),
    "day": ("time", _D(86400)),
    "days": ("time", _D(86400)),
    "week": ("time", _D(604800)),
    "weeks": ("time", _D(604800)),
    "byte": ("data", _D(1)),
    "bytes": ("data", _D(1)),
    "kilobyte": ("data", _D(10) ** 3),
    "kilobytes": ("data", _D(10) ** 3),
    "megabyte": ("data", _D(10) ** 6),
    "megabytes": ("data", _D(10) ** 6),
    "gigabyte": ("data", _D(10) ** 9),
    "gigabytes": ("data", _D(10) ** 9),
    "terabyte": ("data", _D(10) ** 12),
    "terabytes": ("data", _D(10) ** 12),
}


# ---------------------------------------------------------------------------
# Booleans
# ---------------------------------------------------------------------------

BOOL_TRUE = frozenset({"yes", "y", "true", "t", "on", "correct", "affirmative"})
BOOL_FALSE = frozenset({"no", "n", "false", "f", "off", "incorrect", "negative"})


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

MONTHS: Dict[str, int] = {}
_MONTH_NAMES = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
for _i, _name in enumerate(_MONTH_NAMES, start=1):
    MONTHS[_name] = _i
    MONTHS[_name[:3]] = _i
MONTHS["sept"] = 9


# ---------------------------------------------------------------------------
# English cardinal number words
# ---------------------------------------------------------------------------

WORD_UNITS: Dict[str, int] = {
    "zero": 0,
    "nil": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

WORD_TENS: Dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fourty": 40,  # common misspelling; harmless to accept
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

WORD_SCALES: Dict[str, Decimal] = {
    "thousand": _D(10) ** 3,
    "million": _D(10) ** 6,
    "billion": _D(10) ** 9,
    "trillion": _D(10) ** 12,
}


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def lookup_scale(token: str) -> Optional[Decimal]:
    """Return the multiplier for a scale token, or ``None``.

    Single-character tokens are matched case-sensitively (``M`` is million,
    ``m`` is not); everything else is case-insensitive.
    """
    if not token:
        return None
    if len(token) == 1:
        return SCALE_LETTERS.get(token)
    return SCALE_WORDS.get(token.lower())


def lookup_unit(token: str) -> Optional[Tuple[str, Decimal]]:
    """Return ``(dimension, factor_to_base)`` for a unit token, or ``None``."""
    if not token:
        return None
    hit = UNIT_SYMBOLS.get(token)
    if hit is not None:
        return hit
    return UNIT_WORDS.get(token.lower())


def lookup_currency(token: str) -> Optional[str]:
    """Return the ISO code for a currency token, or ``None``."""
    if not token:
        return None
    upper = token.upper()
    if upper in CURRENCY_CODES:
        return upper
    return CURRENCY_WORDS.get(token.lower())
