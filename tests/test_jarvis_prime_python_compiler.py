"""Tests for the JARVIS Prime Python-module backend compiler.

Behavioral coverage: compiling a hand-built IntentGraph (one ENTITY with
slots, one OPERATION) yields a PythonModule whose rendered source parses and
validates, whose class/function names appear in the source; an invalid
function name makes validation fail with a source error; to_dict/from_dict
round-trips preserve module_id.
"""

from __future__ import annotations

import ast

from hermes_cli.jarvis_prime.backend_selector import BackendTarget
from hermes_cli.jarvis_prime.intent_graph import (
    IntentGraph,
    IntentNode,
    IntentNodeKind,
    Slot,
)
from hermes_cli.jarvis_prime.ir_compilers.python_module import (
    PyDataclass,
    PyField,
    PyFunction,
    PythonModule,
    PythonModuleCompiler,
)


def _invoice_graph() -> IntentGraph:
    entity = IntentNode.make(
        IntentNodeKind.ENTITY,
        "invoice",
        slots=(
            Slot(name="total", type="number"),
            Slot(name="vendor", type="string"),
        ),
    )
    operation = IntentNode.make(
        IntentNodeKind.OPERATION,
        "extract",
        slots=(Slot(name="verb", type="string", value="extract"),),
    )
    return IntentGraph(
        nodes=(entity, operation),
        raw_text="extract the total from each invoice\nand store it",
    )


def test_compile_produces_valid_parseable_module() -> None:
    graph = _invoice_graph()
    result = PythonModuleCompiler().compile(graph)

    assert result.target == BackendTarget.PYTHON
    module = result.artifact
    assert isinstance(module, PythonModule)

    validation = module.validate()
    assert validation.ok, validation.findings

    source = result.artifact_dict["source"]
    # The rendered source is real, parseable Python.
    ast.parse(source)


def test_entity_and_operation_names_appear_in_source() -> None:
    result = PythonModuleCompiler().compile(_invoice_graph())
    source = result.artifact_dict["source"]

    # ENTITY -> PascalCase dataclass, OPERATION -> snake_case function.
    assert "class Invoice:" in source
    assert "def extract(" in source
    # Slot-derived typed fields.
    assert "total: int" in source
    assert "vendor: str" in source
    # Module doc takes only the first line of raw_text.
    module = result.artifact
    assert isinstance(module, PythonModule)
    assert module.module_doc == "extract the total from each invoice"


def test_no_entity_operation_uses_generic_data_param() -> None:
    op = IntentNode.make(IntentNodeKind.OPERATION, "summarize")
    graph = IntentGraph(nodes=(op,), raw_text="summarize things")
    result = PythonModuleCompiler().compile(graph)
    source = result.artifact_dict["source"]
    assert "def summarize(data) -> Any:" in source


def test_constraint_label_named_in_docstring() -> None:
    op = IntentNode.make(IntentNodeKind.OPERATION, "alert")
    constraint = IntentNode.make(IntentNodeKind.CONSTRAINT, "vendor is new")
    graph = IntentGraph(nodes=(op, constraint), raw_text="alert if vendor is new")
    module = PythonModuleCompiler().compile(graph).artifact
    assert isinstance(module, PythonModule)
    assert "vendor is new" in module.functions[0].doc


def test_invalid_function_name_fails_validation() -> None:
    # A function name that is not a valid identifier renders un-parseable source.
    bad = PythonModule.from_dict(
        {
            "functions": [
                {"name": "1nvalid name", "params": ["data"], "doc": "bad"}
            ]
        }
    )
    result = bad.validate()
    assert result.ok is False
    assert any(
        f.field == "source" and f.severity == "error" for f in result.findings
    )


def test_empty_module_warns_but_stays_ok() -> None:
    empty = PythonModule()
    result = empty.validate()
    # No dataclasses/functions -> warning, but still ok (parseable).
    assert result.ok is True
    assert any(f.severity == "warning" for f in result.findings)


def test_to_dict_from_dict_preserves_module_id() -> None:
    module = PythonModule(
        module_doc="demo",
        dataclasses=(
            PyDataclass(
                name="Invoice",
                fields=(PyField("total", "int"), PyField("vendor", "str")),
                doc="Models the invoice entity.",
            ),
        ),
        functions=(
            PyFunction(name="extract", params=("invoice",), doc="extract op."),
        ),
        provenance={"graph_id": "abc"},
    )
    restored = PythonModule.from_dict(module.to_dict())
    assert restored.module_id == module.module_id
    assert restored.render_source() == module.render_source()
