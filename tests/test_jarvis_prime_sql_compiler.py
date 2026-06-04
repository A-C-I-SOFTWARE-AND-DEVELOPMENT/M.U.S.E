"""Tests for the JARVIS Prime W2 SQL backend compiler.

Covers: a declarative-read graph compiles into a parameterized ``SqlSelect``
with >=1 table and explicit columns; the rendered SQL uses ``:pN`` placeholders
and never interpolates a constraint's literal value; validation flags a missing
table and an empty column name; to_dict/from_dict preserves ``query_id``.
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.backend_selector import BackendTarget
from hermes_cli.jarvis_prime.intent_graph import (
    IntentGraph,
    IntentNode,
    IntentNodeKind,
    Slot,
)
from hermes_cli.jarvis_prime.ir_compilers.sql_query import (
    SqlColumn,
    SqlPredicate,
    SqlQueryCompiler,
    SqlSelect,
)


def _read_graph() -> IntentGraph:
    """DATA_SOURCE invoices, ENTITY invoice(vendor,total), CONSTRAINT vendor is new."""
    source = IntentNode.make(IntentNodeKind.DATA_SOURCE, "invoices")
    entity = IntentNode.make(
        IntentNodeKind.ENTITY,
        "invoice",
        slots=(Slot(name="vendor"), Slot(name="total")),
    )
    constraint = IntentNode.make(
        IntentNodeKind.CONSTRAINT,
        "vendor is new",
        slots=(Slot(name="expr", value="vendor is new"),),
    )
    return IntentGraph(
        nodes=(source, entity, constraint),
        raw_text="show me invoices where the vendor is new",
    )


def test_compile_produces_parameterized_select() -> None:
    result = SqlQueryCompiler().compile(_read_graph())
    select = result.artifact
    assert isinstance(select, SqlSelect)
    assert isinstance(select, SqlSelect)
    assert len(select.tables) >= 1
    assert select.columns
    sql = select.render_sql()
    # Parameterized: a :pN placeholder is present.
    assert ":p" in sql
    # SECURITY: the literal constraint value ("new") is NOT in the SQL text.
    assert "new" not in sql
    assert select.validate().ok is True


def test_render_sql_never_interpolates_predicate_values() -> None:
    result = SqlQueryCompiler().compile(_read_graph())
    select = result.artifact
    assert isinstance(select, SqlSelect)
    sql = select.render_sql()
    # Every predicate references its placeholder name, never a bound value.
    for pred in select.predicates:
        assert f":{pred.param}" in sql
        # The provenance note (which carries the raw value) is not in the SQL.
        assert select.params[pred.param] not in sql
    # No raw constraint expression leaked into the SQL.
    assert "vendor is new" not in sql


def test_compile_columns_from_entity_slots() -> None:
    select = SqlQueryCompiler().compile(_read_graph()).artifact
    assert isinstance(select, SqlSelect)
    names = {c.name for c in select.columns}
    assert "vendor" in names
    assert "total" in names
    assert "invoices" in select.tables


def test_validate_flags_missing_table() -> None:
    select = SqlSelect(tables=(), columns=(SqlColumn(name="vendor"),))
    result = select.validate()
    assert result.ok is False
    assert any(f.field == "tables" for f in result.errors)


def test_validate_flags_empty_column_name() -> None:
    select = SqlSelect(tables=("invoices",), columns=(SqlColumn(name=""),))
    result = select.validate()
    assert result.ok is False
    assert any(f.field == "columns" for f in result.errors)


def test_validate_warns_on_select_star() -> None:
    select = SqlSelect(tables=("invoices",), columns=(SqlColumn(name="*"),))
    result = select.validate()
    assert result.ok is True
    assert any(
        f.severity == "warning" and f.field == "columns"
        for f in result.findings
    )


def test_validate_errors_on_predicate_without_param_entry() -> None:
    select = SqlSelect(
        tables=("invoices",),
        columns=(SqlColumn(name="vendor"),),
        predicates=(SqlPredicate(column="vendor", op="=", param="p0"),),
        params={},  # placeholder p0 has no entry
    )
    result = select.validate()
    assert result.ok is False
    assert any(f.field == "predicates" for f in result.errors)


def test_unparseable_constraint_still_parameterized() -> None:
    source = IntentNode.make(IntentNodeKind.DATA_SOURCE, "invoices")
    entity = IntentNode.make(
        IntentNodeKind.ENTITY, "invoice", slots=(Slot(name="vendor"),))
    constraint = IntentNode.make(
        IntentNodeKind.CONSTRAINT,
        "something weird",
        slots=(Slot(name="expr", value="totally opaque phrase"),),
    )
    graph = IntentGraph(nodes=(source, entity, constraint), raw_text="x")
    select = SqlQueryCompiler().compile(graph).artifact
    assert isinstance(select, SqlSelect)
    assert select.predicates
    pred = select.predicates[0]
    assert pred.param in select.params
    sql = select.render_sql()
    assert f":{pred.param}" in sql
    assert "opaque" not in sql


def test_to_dict_includes_rendered_sql_and_params() -> None:
    select = SqlQueryCompiler().compile(_read_graph()).artifact
    assert isinstance(select, SqlSelect)
    d = select.to_dict()
    assert d["sql"] == select.render_sql()
    assert "params" in d
    assert ":p" in d["sql"]


def test_round_trip_preserves_query_id() -> None:
    select = SqlQueryCompiler().compile(_read_graph()).artifact
    assert isinstance(select, SqlSelect)
    restored = SqlSelect.from_dict(select.to_dict())
    assert restored.query_id == select.query_id


def test_compiler_target_is_sql() -> None:
    assert SqlQueryCompiler().target == BackendTarget.SQL
