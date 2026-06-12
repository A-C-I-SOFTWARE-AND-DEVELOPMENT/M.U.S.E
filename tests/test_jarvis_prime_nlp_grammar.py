"""Tests for the W7 constrained / grammar decoding harness.

Behavioral, with no live model: every model call is a deterministic stub
callable. Covers the three grammars (python / sql / json), the
generate -> validate -> repair loop, fallback handling, and determinism.
"""

from __future__ import annotations

from typing import Callable

from muse_cli.jarvis_prime.nlp_grammar import (
    GRAMMARS,
    JSON_GRAMMAR,
    PYTHON_GRAMMAR,
    SQL_GRAMMAR,
    ConstrainedResult,
    GrammarResult,
    constrain,
    get_grammar,
)


def _sequence_generator(outputs: list[str]) -> Callable[[str], str]:
    """A stub ``generate`` that yields ``outputs`` in order, repeating last."""

    calls = {"n": 0}

    def _gen(_prompt: str) -> str:
        idx = min(calls["n"], len(outputs) - 1)
        calls["n"] += 1
        return outputs[idx]

    return _gen


# --------------------------------------------------------------------------- #
# Grammar validators
# --------------------------------------------------------------------------- #


def test_python_grammar_accepts_valid_source() -> None:
    assert PYTHON_GRAMMAR.validate("def f():\n    return 1\n").ok is True


def test_python_grammar_rejects_syntax_error() -> None:
    result = PYTHON_GRAMMAR.validate("def (:")
    assert result.ok is False
    assert result.findings  # carries at least one finding


def test_sql_grammar_accepts_named_param() -> None:
    assert SQL_GRAMMAR.validate("SELECT a FROM t WHERE x = :p0").ok is True


def test_sql_grammar_rejects_inline_string_literal() -> None:
    result = SQL_GRAMMAR.validate("SELECT a FROM t WHERE x = 'secret'")
    assert result.ok is False
    assert any("literal" in m for m in result.messages())


def test_sql_grammar_rejects_inline_number_literal() -> None:
    assert SQL_GRAMMAR.validate("SELECT a FROM t WHERE x = 42").ok is False


def test_sql_grammar_requires_select_and_from() -> None:
    assert SQL_GRAMMAR.validate("UPDATE t SET a = :p0").ok is False
    assert SQL_GRAMMAR.validate("SELECT a WHERE x = :p0").ok is False


def test_json_grammar_accepts_and_rejects() -> None:
    assert JSON_GRAMMAR.validate('{"a":1}').ok is True
    assert JSON_GRAMMAR.validate("{not json}").ok is False


def test_registry_and_lookup() -> None:
    assert get_grammar("python") is PYTHON_GRAMMAR
    assert get_grammar("sql") is SQL_GRAMMAR
    assert get_grammar("json") is JSON_GRAMMAR
    assert set(GRAMMARS) == {"python", "sql", "json"}


def test_unknown_grammar_raises() -> None:
    try:
        get_grammar("ruby")
    except KeyError:
        pass
    else:  # pragma: no cover - failure path
        raise AssertionError("expected KeyError for unknown grammar")


def test_result_to_dict_roundtrip() -> None:
    result: GrammarResult = SQL_GRAMMAR.validate("SELECT a FROM t WHERE x = 'q'")
    payload = result.to_dict()
    assert payload["ok"] is False
    assert payload["findings"][0]["severity"] == "error"
    assert "message" in payload["findings"][0]


# --------------------------------------------------------------------------- #
# constrain() harness
# --------------------------------------------------------------------------- #


def test_constrain_returns_first_valid_without_repair() -> None:
    gen = _sequence_generator(["x = 1\n"])
    out = constrain(gen, PYTHON_GRAMMAR, "write a python statement")
    assert out.ok is True
    assert out.repaired is False
    assert out.attempts == 1


def test_constrain_repairs_invalid_then_valid() -> None:
    gen = _sequence_generator(["def (:", "x = 1\n"])
    out = constrain(gen, PYTHON_GRAMMAR, "write a python statement")
    assert out.ok is True
    assert out.repaired is True
    assert out.attempts == 2


def test_constrain_uses_fallback_when_always_invalid() -> None:
    gen = _sequence_generator(["def (:"])  # always invalid
    out = constrain(
        gen,
        PYTHON_GRAMMAR,
        "write a python statement",
        max_repairs=2,
        fallback="x = 0\n",
    )
    assert out.ok is True
    assert out.repaired is True
    assert out.text == "x = 0\n"
    assert "used fallback" in out.trace


def test_constrain_fails_without_fallback() -> None:
    gen = _sequence_generator(["def (:"])  # always invalid
    out = constrain(
        gen,
        PYTHON_GRAMMAR,
        "write a python statement",
        max_repairs=2,
    )
    assert out.ok is False
    assert out.repaired is False
    # one initial attempt + max_repairs retries
    assert out.attempts == 3


def test_constrain_ignores_invalid_fallback() -> None:
    gen = _sequence_generator(["def (:"])
    out = constrain(
        gen,
        PYTHON_GRAMMAR,
        "write a python statement",
        max_repairs=1,
        fallback="also invalid (:",
    )
    assert out.ok is False
    assert out.text == "def (:"


def test_constrain_passes_findings_into_repair_prompt() -> None:
    seen_prompts: list[str] = []

    def gen(prompt: str) -> str:
        seen_prompts.append(prompt)
        return "def (:" if len(seen_prompts) == 1 else "x = 1\n"

    out = constrain(gen, PYTHON_GRAMMAR, "base prompt")
    assert out.ok is True
    # second prompt is the repair prompt carrying the grammar name + findings
    assert "Your previous output was invalid" in seen_prompts[1]
    assert "Return only valid python" in seen_prompts[1]


def test_constrain_is_deterministic() -> None:
    out1: ConstrainedResult = constrain(
        _sequence_generator(["def (:", "x = 1\n"]),
        PYTHON_GRAMMAR,
        "write a python statement",
    )
    out2: ConstrainedResult = constrain(
        _sequence_generator(["def (:", "x = 1\n"]),
        PYTHON_GRAMMAR,
        "write a python statement",
    )
    assert out1.to_dict() == out2.to_dict()
