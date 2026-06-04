"""Tests for the JARVIS Constitution rubric module (constitution.py).

Behavior-focused: clause integrity, dimension/severity validity, the
single-source-of-truth owner-gate reference, and sync with the spec doc.
"""

from pathlib import Path

from hermes_cli.jarvis_prime import constitution
from hermes_cli.jarvis_prime.constitution import Dimension, Severity
from hermes_cli.jarvis_prime.owner_auth import OWNER_GATED_ACTIONS

_DOC = Path(__file__).resolve().parents[1] / "docs" / "jarvis-constitution.md"


def test_clause_ids_are_sequential_and_unique():
    ids = [c.id for c in constitution.clauses()]
    assert ids == [f"C{i}" for i in range(1, len(ids) + 1)]
    assert len(set(ids)) == len(ids)


def test_every_clause_has_valid_dimension_severity_and_text():
    for c in constitution.clauses():
        assert isinstance(c.dimension, Dimension)
        assert isinstance(c.severity, Severity)
        assert c.text.strip()
        assert c.article.strip()
        assert c.title.strip()


def test_owner_gated_actions_references_source_of_truth():
    # Article III (C9) must reference owner_auth's frozenset, not copy it.
    assert constitution.owner_gated_actions() is OWNER_GATED_ACTIONS


def test_dimensions_cover_every_axis():
    present = {d.value for d in constitution.dimensions()}
    assert present == {d.value for d in Dimension}


def test_clause_lookup_and_get():
    c9 = constitution.clause("C9")
    assert c9.dimension == Dimension.OWNER_GATE_RESPECT
    assert c9.severity == Severity.FATAL
    assert constitution.get("C27").severity == Severity.FATAL
    assert constitution.get("does-not-exist") is None


def test_severity_rank_orders_fatal_highest():
    assert Severity.FATAL.rank > Severity.MAJOR.rank > Severity.MINOR.rank


def test_module_matches_spec_doc():
    text = _DOC.read_text(encoding="utf-8")
    assert f"Constitution **v{constitution.version()}**" in text
    for c in constitution.clauses():
        assert f"**{c.id}**" in text, f"{c.id} missing from {_DOC.name}"
