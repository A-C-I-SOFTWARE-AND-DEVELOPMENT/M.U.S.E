"""Tests for the muse W3 Rust backend compiler.

Behavioral coverage: a graph with one ENTITY + one OPERATION compiles to a
RustModule whose rendered source validates and contains the expected scaffold;
a structurally broken module (unbalanced brace) fails validation; an empty
module fails validation; and to_dict/from_dict round-trips preserve module_id.

All checks are structural — no rustc / toolchain is invoked.
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.backend_selector import BackendTarget
from hermes_cli.jarvis_prime.intent_graph import (
    IntentGraph,
    IntentNode,
    IntentNodeKind,
    Slot,
)
from hermes_cli.jarvis_prime.ir_compilers.rust_module import (
    RustField,
    RustFn,
    RustModule,
    RustModuleCompiler,
    RustStruct,
)


def _entity_and_op_graph() -> IntentGraph:
    invoice = IntentNode.make(
        IntentNodeKind.ENTITY,
        "invoice",
        slots=(
            Slot(name="total", type="number"),
            Slot(name="vendor", type="string"),
        ),
    )
    extract = IntentNode.make(
        IntentNodeKind.OPERATION,
        "extract",
        slots=(
            Slot(name="verb", type="string", value="extract"),
            Slot(name="amount", type="number"),
        ),
    )
    new_vendor = IntentNode.make(
        IntentNodeKind.CONSTRAINT, "vendor is new"
    )
    return IntentGraph(
        nodes=(invoice, extract, new_vendor),
        raw_text="extract the total from each invoice",
    )


# --- compile path ----------------------------------------------------------


def test_compiler_target_is_rust() -> None:
    assert RustModuleCompiler.target == BackendTarget.RUST


def test_compile_entity_and_op_validates_and_renders() -> None:
    result = RustModuleCompiler().compile(_entity_and_op_graph())
    module = result.artifact
    assert isinstance(module, RustModule)

    validation = module.validate()
    assert validation.ok, validation.to_dict()

    src = module.render_source()
    assert "pub struct" in src
    assert "pub fn" in src
    assert "todo!()" in src
    # Module doc and entity/op naming made it into the source.
    assert "//!" in src
    assert "pub struct Invoice" in src
    # Slot types mapped: number -> i64, string -> String.
    assert "i64" in src
    assert "String" in src
    # Constraint label surfaced into the fn doc comment.
    assert "vendor is new" in src


def test_compile_result_dict_includes_source_and_id() -> None:
    result = RustModuleCompiler().compile(_entity_and_op_graph())
    d = result.artifact_dict
    module = result.artifact
    assert isinstance(module, RustModule)
    assert d["source"] == module.render_source()
    assert d["module_id"] == module.module_id
    assert result.target == BackendTarget.RUST


# --- structural validation -------------------------------------------------


def test_unbalanced_brace_fails_validation() -> None:
    # Injecting a '{' into a field name unbalances the rendered braces.
    broken = RustModule(
        module_doc="broken",
        structs=(
            RustStruct(
                name="Bad",
                fields=(RustField(name="oops{", ty="String"),),
            ),
        ),
    )
    src = broken.render_source()
    assert src.count("{") != src.count("}")

    result = broken.validate()
    assert result.ok is False
    assert any(f.field == "source" for f in result.errors)


def test_empty_module_fails_validation() -> None:
    empty = RustModule(module_doc="nothing here")
    result = empty.validate()
    assert result.ok is False
    assert any(f.field == "module" for f in result.errors)


def test_non_empty_module_with_only_fn_is_ok() -> None:
    mod = RustModule(
        module_doc="ok",
        functions=(RustFn(name="run", doc="run it."),),
    )
    assert mod.validate().ok


# --- round-trip ------------------------------------------------------------


def test_to_dict_from_dict_preserves_module_id() -> None:
    original = RustModuleCompiler().compile(_entity_and_op_graph()).artifact
    assert isinstance(original, RustModule)
    rebuilt = RustModule.from_dict(original.to_dict())
    assert rebuilt.module_id == original.module_id
    assert rebuilt.render_source() == original.render_source()
