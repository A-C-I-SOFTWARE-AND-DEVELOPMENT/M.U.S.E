"""Rust backend compiler (W3) for the MUSE NL compiler.

Compiles an :class:`IntentGraph` into a ``RustModule`` — a small, validatable
Rust *source scaffold* (one ``pub struct`` per ENTITY, one ``pub fn`` per
OPERATION, doc comments naming inputs and CONSTRAINT guards). This is the Rust
analog of ``AutomationFlow``: it *describes* and *validates* a module, it does
not execute, compile, or shell out to ``rustc``.

Validation is purely **structural** over the rendered source: balanced braces
and parentheses, at least one struct or function, well-formed doc comments.
There is deliberately **no rustc / toolchain dependency** — the same module
text always validates the same way, deterministically and offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from muse_cli.jarvis_prime.backend_selector import BackendContext, BackendTarget
from muse_cli.jarvis_prime.guardrail_evidence import canonical_json, sha256_hex
from muse_cli.jarvis_prime.intent_graph import (
    IntentGraph,
    IntentNodeKind,
)
from muse_cli.jarvis_prime.ir_compilers.base import CompileResult

# Slot type -> Rust type. Anything unknown collapses to the unit type "()".
_TYPE_MAP: dict[str, str] = {"string": "String", "number": "i64"}


# ---------------------------------------------------------------------------
# Validation result types (mirror the AutomationFlow pattern)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RustValidationFinding:
    field: str
    severity: str        # "error" | "warning"
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "severity": self.severity,
                "message": self.message}


@dataclass(frozen=True)
class RustValidationResult:
    ok: bool
    findings: tuple[RustValidationFinding, ...] = ()

    @property
    def errors(self) -> tuple[RustValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity == "error")

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "findings": [f.to_dict() for f in self.findings]}


# ---------------------------------------------------------------------------
# Source-element dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RustField:
    name: str
    ty: str = "()"

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ty": self.ty}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RustField":
        return cls(name=str(d.get("name", "")), ty=str(d.get("ty", "()")))


@dataclass(frozen=True)
class RustStruct:
    name: str
    fields: tuple[RustField, ...] = ()
    doc: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "doc": self.doc,
                "fields": [f.to_dict() for f in self.fields]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RustStruct":
        return cls(
            name=str(d.get("name", "")),
            fields=tuple(RustField.from_dict(f) for f in d.get("fields", ())),
            doc=str(d.get("doc", "")),
        )


@dataclass(frozen=True)
class RustFn:
    name: str
    params: tuple[RustField, ...] = ()
    doc: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "doc": self.doc,
                "params": [p.to_dict() for p in self.params]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RustFn":
        return cls(
            name=str(d.get("name", "")),
            params=tuple(RustField.from_dict(p) for p in d.get("params", ())),
            doc=str(d.get("doc", "")),
        )


# ---------------------------------------------------------------------------
# The module
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RustModule:
    module_doc: str = ""
    structs: tuple[RustStruct, ...] = ()
    functions: tuple[RustFn, ...] = ()
    provenance: dict = field(default_factory=dict)

    # -- identity ----------------------------------------------------------

    @property
    def module_id(self) -> str:
        stable = {
            "module_doc": self.module_doc,
            "structs": sorted(
                [s.name, [[f.name, f.ty] for f in s.fields]] for s in self.structs
            ),
            "functions": sorted(
                [fn.name, [[p.name, p.ty] for p in fn.params]]
                for fn in self.functions
            ),
        }
        return sha256_hex(canonical_json(stable))

    # -- rendering ---------------------------------------------------------

    def render_source(self) -> str:
        lines: list[str] = []
        for doc_line in self.module_doc.splitlines() or [""]:
            lines.append(f"//! {doc_line}".rstrip())
        lines.append("")

        for s in self.structs:
            for doc_line in _doc_lines(s.doc):
                lines.append(doc_line)
            lines.append(f"pub struct {s.name} {{")
            for f in s.fields:
                lines.append(f"    pub {f.name}: {f.ty},")
            lines.append("}")
            lines.append("")

        for fn in self.functions:
            for doc_line in _doc_lines(fn.doc):
                lines.append(doc_line)
            params = ", ".join(f"{p.name}: {p.ty}" for p in fn.params)
            lines.append(f"pub fn {fn.name}({params}) {{")
            lines.append("    todo!()")
            lines.append("}")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "module_doc": self.module_doc,
            "structs": [s.to_dict() for s in self.structs],
            "functions": [fn.to_dict() for fn in self.functions],
            "source": self.render_source(),
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RustModule":
        return cls(
            module_doc=str(d.get("module_doc", "")),
            structs=tuple(RustStruct.from_dict(s) for s in d.get("structs", ())),
            functions=tuple(RustFn.from_dict(fn) for fn in d.get("functions", ())),
            provenance=dict(d.get("provenance", {})),
        )

    # -- validation (structural only — no rustc) ---------------------------

    def validate(self) -> RustValidationResult:
        findings: list[RustValidationFinding] = []
        source = self.render_source()

        opens = source.count("{")
        closes = source.count("}")
        if opens != closes:
            findings.append(RustValidationFinding(
                "source", "error",
                f"unbalanced braces: {opens} '{{' vs {closes} '}}'"))

        popens = source.count("(")
        pcloses = source.count(")")
        if popens != pcloses:
            findings.append(RustValidationFinding(
                "source", "error",
                f"unbalanced parentheses: {popens} '(' vs {pcloses} ')'"))

        if not self.structs and not self.functions:
            findings.append(RustValidationFinding(
                "module", "error",
                "a rust module needs at least one struct or function"))

        # Doc comments must be well-formed: a line that begins (after
        # indentation) with a comment sigil must use a valid doc/comment form.
        for line in source.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("/") and not _is_well_formed_comment(stripped):
                findings.append(RustValidationFinding(
                    "source", "error", f"malformed doc comment: {line!r}"))

        ok = not any(f.severity == "error" for f in findings)
        return RustValidationResult(ok=ok, findings=tuple(findings))


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------


class RustModuleCompiler:
    target = BackendTarget.RUST

    def compile(
        self, graph: IntentGraph, context: Optional[BackendContext] = None
    ) -> CompileResult:
        structs: list[RustStruct] = []
        for ent in graph.nodes_of(IntentNodeKind.ENTITY):
            fields = tuple(
                RustField(name=_snake_case(s.name), ty=_rust_type(s.type))
                for s in ent.slots
            )
            structs.append(RustStruct(
                name=_pascal_case(ent.label),
                fields=fields,
                doc=f"{ent.label} entity.",
            ))

        constraints = [c.label for c in graph.nodes_of(IntentNodeKind.CONSTRAINT)]

        functions: list[RustFn] = []
        for op in graph.nodes_of(IntentNodeKind.OPERATION):
            verb_slot = op.slot("verb")
            verb = str(verb_slot.value) if verb_slot and verb_slot.value else op.label
            params = tuple(
                RustField(name=_snake_case(s.name), ty=_rust_type(s.type))
                for s in op.slots
                if s.name != "verb"
            )
            functions.append(RustFn(
                name=_snake_case(verb),
                params=params,
                doc=_fn_doc(verb, params, constraints),
            ))

        module = RustModule(
            module_doc=_module_doc(graph),
            structs=tuple(structs),
            functions=tuple(functions),
            provenance={"graph_id": graph.graph_id},
        )

        result = module.validate()
        notes = tuple(f"{f.severity}: {f.message}" for f in result.findings)
        return CompileResult(
            target=self.target,
            artifact=module,
            artifact_dict=module.to_dict(),
            gate_packet=None,
            notes=notes,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc_lines(doc: str) -> list[str]:
    if not doc:
        return []
    return [f"/// {line}".rstrip() for line in doc.splitlines()]


def _is_well_formed_comment(stripped: str) -> bool:
    # Accept module docs (//!), doc comments (///), line comments (//),
    # and block comments (/* ... */ or /** ... */).
    return bool(
        re.match(r"^//!", stripped)
        or re.match(r"^///", stripped)
        or re.match(r"^//", stripped)
        or re.match(r"^/\*", stripped)
    )


def _fn_doc(verb: str, params: tuple[RustField, ...], constraints: list[str]) -> str:
    parts = [f"{verb} operation."]
    if params:
        parts.append("Inputs: " + ", ".join(p.name for p in params) + ".")
    if constraints:
        parts.append("Constraints: " + ", ".join(constraints) + ".")
    return " ".join(parts)


def _module_doc(graph: IntentGraph) -> str:
    text = (graph.raw_text or "").strip()
    if text:
        return text.replace("\n", " ")[:200]
    return "MUSE generated module."


def _rust_type(slot_type: str) -> str:
    return _TYPE_MAP.get((slot_type or "").lower(), "()")


_NON_IDENT = re.compile(r"[^0-9a-zA-Z]+")


def _split_words(raw: str) -> list[str]:
    # Split on non-alphanumerics and camelCase boundaries.
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(raw))
    tokens = _NON_IDENT.sub(" ", spaced).split()
    return [t for t in tokens if t]


def _snake_case(raw: str) -> str:
    words = _split_words(raw)
    if not words:
        return "field"
    name = "_".join(w.lower() for w in words)
    if name[0].isdigit():
        name = f"_{name}"
    return name


def _pascal_case(raw: str) -> str:
    words = _split_words(raw)
    if not words:
        return "Item"
    name = "".join(w[:1].upper() + w[1:].lower() for w in words)
    if name[0].isdigit():
        name = f"_{name}"
    return name


__all__ = [
    "RustValidationFinding",
    "RustValidationResult",
    "RustField",
    "RustStruct",
    "RustFn",
    "RustModule",
    "RustModuleCompiler",
]
