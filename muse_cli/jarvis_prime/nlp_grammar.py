"""W7 — constrained / grammar decoding for the MUSE NL compiler.

The model provider interface here is *completion-only*: we hand a prompt to a
callable and get back a string. There is no token-level masking, so
"constrained decoding" is implemented as a deterministic
**generate -> validate -> repair** harness:

1. Generate once.
2. Validate the emitted *source/text* against a :class:`GrammarSpec`.
3. If invalid, build a repair prompt that lists the findings and ask the model
   to try again, up to ``max_repairs`` times.
4. If still invalid, optionally fall back to a known-good string (validated
   before use), otherwise return the best/last text with ``ok=False``.

Everything is model-agnostic and string/grammar based so it does not
hard-depend on the other in-flight compiler modules. Pass any deterministic
``generate`` callable and the whole harness is deterministic and testable
without a live model.

Grammars validate emitted text only:

- ``python`` — parses via :func:`ast.parse`.
- ``sql`` — must start with ``SELECT`` (case-insensitive), contain ``FROM``,
  and carry **no** inline string/number literal in a ``WHERE`` comparison;
  only ``:pN`` named params may follow a comparison operator.
- ``json`` — parses via :func:`json.loads`.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# --------------------------------------------------------------------------- #
# Findings / results
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GrammarFinding:
    """A single validation problem with a stable severity + message."""

    severity: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"severity": self.severity, "message": self.message}


@dataclass(frozen=True)
class GrammarResult:
    """Outcome of validating one piece of text against a grammar."""

    ok: bool
    findings: tuple[GrammarFinding, ...] = ()

    def messages(self) -> tuple[str, ...]:
        return tuple(f.message for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "findings": [f.to_dict() for f in self.findings],
        }


# --------------------------------------------------------------------------- #
# Grammar specs
# --------------------------------------------------------------------------- #

# A comparison operator followed by an inline string literal: ``= 'secret'``.
_SQL_STRING_LITERAL = re.compile(r"(?:=|!=|<>|<|>|<=|>=)\s*'[^']*'")
# A comparison operator followed by an inline numeric literal: ``= 42``.
_SQL_NUMBER_LITERAL = re.compile(r"(?:=|!=|<>|<|>|<=|>=)\s*\d")


def _ok() -> GrammarResult:
    return GrammarResult(ok=True, findings=())


def _fail(severity: str, message: str) -> GrammarResult:
    return GrammarResult(ok=False, findings=(GrammarFinding(severity, message),))


def _validate_python(text: str) -> GrammarResult:
    try:
        ast.parse(text)
    except SyntaxError as exc:
        return _fail("error", f"invalid python: {exc.msg}")
    except (ValueError, MemoryError) as exc:  # pragma: no cover - defensive
        return _fail("error", f"invalid python: {exc}")
    return _ok()


def _validate_json(text: str) -> GrammarResult:
    try:
        json.loads(text)
    except (ValueError, TypeError) as exc:
        return _fail("error", f"invalid json: {exc}")
    return _ok()


def _validate_sql(text: str) -> GrammarResult:
    stripped = text.strip()
    if not stripped:
        return _fail("error", "empty sql statement")

    findings: list[GrammarFinding] = []

    upper = stripped.upper()
    if not upper.startswith("SELECT"):
        findings.append(
            GrammarFinding("error", "sql must start with SELECT")
        )
    if "FROM" not in upper:
        findings.append(GrammarFinding("error", "sql must contain a FROM clause"))

    # Only inspect the WHERE clause for inline literals; comparisons there must
    # use ``:pN`` named params, never raw strings/numbers.
    where_idx = upper.find("WHERE")
    if where_idx != -1:
        where_clause = stripped[where_idx:]
        if _SQL_STRING_LITERAL.search(where_clause):
            findings.append(
                GrammarFinding(
                    "error",
                    "inline string literal in WHERE comparison; use a :pN param",
                )
            )
        if _SQL_NUMBER_LITERAL.search(where_clause):
            findings.append(
                GrammarFinding(
                    "error",
                    "inline numeric literal in WHERE comparison; use a :pN param",
                )
            )

    if findings:
        return GrammarResult(ok=False, findings=tuple(findings))
    return _ok()


_VALIDATORS: dict[str, Callable[[str], GrammarResult]] = {
    "python": _validate_python,
    "sql": _validate_sql,
    "json": _validate_json,
}


@dataclass(frozen=True)
class GrammarSpec:
    """A named grammar that validates emitted source/text.

    The actual rules live in module-level validator functions keyed by
    :attr:`name`; the spec is a thin, frozen handle so instances can be shared
    and compared cheaply.
    """

    name: str

    def validate(self, text: str) -> GrammarResult:
        validator = _VALIDATORS.get(self.name)
        if validator is None:  # pragma: no cover - guarded by registry
            return _fail("error", f"no validator for grammar {self.name!r}")
        return validator(text)


PYTHON_GRAMMAR = GrammarSpec(name="python")
SQL_GRAMMAR = GrammarSpec(name="sql")
JSON_GRAMMAR = GrammarSpec(name="json")

GRAMMARS: dict[str, GrammarSpec] = {
    "python": PYTHON_GRAMMAR,
    "sql": SQL_GRAMMAR,
    "json": JSON_GRAMMAR,
}


def get_grammar(name: str) -> GrammarSpec:
    """Look up a grammar by name. Raises ``KeyError`` if unknown."""

    try:
        return GRAMMARS[name]
    except KeyError as exc:
        raise KeyError(
            f"unknown grammar {name!r}; known: {sorted(GRAMMARS)}"
        ) from exc


# --------------------------------------------------------------------------- #
# Constrained decoding harness
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ConstrainedResult:
    """Outcome of a constrained generate -> validate -> repair run."""

    text: str
    ok: bool
    attempts: int
    repaired: bool
    trace: tuple[str, ...] = field(default=())

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "ok": self.ok,
            "attempts": self.attempts,
            "repaired": self.repaired,
            "trace": list(self.trace),
        }


def _repair_prompt(prompt: str, grammar: GrammarSpec, result: GrammarResult) -> str:
    messages = "; ".join(result.messages()) or "output failed validation"
    return (
        f"{prompt}\n\n"
        f"Your previous output was invalid: {messages}. "
        f"Return only valid {grammar.name}."
    )


def constrain(
    generate: Callable[[str], str],
    grammar: GrammarSpec,
    prompt: str,
    *,
    max_repairs: int = 2,
    fallback: Optional[str] = None,
) -> ConstrainedResult:
    """Deterministically generate text that satisfies ``grammar``.

    Calls ``generate`` once, then up to ``max_repairs`` more times with a
    findings-laden repair prompt. Returns the first valid text; if none
    validates, uses ``fallback`` when it validates, otherwise returns the last
    text with ``ok=False``. Deterministic for a deterministic ``generate``.
    """

    trace: list[str] = []
    current_prompt = prompt
    text = generate(current_prompt)
    result = grammar.validate(text)
    attempts = 1

    if result.ok:
        trace.append("attempt 1: ok")
        return ConstrainedResult(
            text=text,
            ok=True,
            attempts=attempts,
            repaired=False,
            trace=tuple(trace),
        )

    trace.append(f"attempt 1: invalid ({'; '.join(result.messages())})")

    for _ in range(max_repairs):
        current_prompt = _repair_prompt(prompt, grammar, result)
        text = generate(current_prompt)
        result = grammar.validate(text)
        attempts += 1
        if result.ok:
            trace.append(f"attempt {attempts}: ok (repaired)")
            return ConstrainedResult(
                text=text,
                ok=True,
                attempts=attempts,
                repaired=True,
                trace=tuple(trace),
            )
        trace.append(
            f"attempt {attempts}: invalid ({'; '.join(result.messages())})"
        )

    if fallback is not None:
        fallback_result = grammar.validate(fallback)
        if fallback_result.ok:
            trace.append("used fallback")
            return ConstrainedResult(
                text=fallback,
                ok=True,
                attempts=attempts,
                repaired=True,
                trace=tuple(trace),
            )
        trace.append("fallback invalid; kept last output")

    return ConstrainedResult(
        text=text,
        ok=False,
        attempts=attempts,
        repaired=False,
        trace=tuple(trace),
    )
