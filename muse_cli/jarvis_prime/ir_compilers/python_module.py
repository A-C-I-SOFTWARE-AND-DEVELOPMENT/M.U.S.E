"""Python-module backend.

Compiles an :class:`IntentGraph` into a ``PythonModule`` — a small, valid,
parseable Python source scaffold (the "model the invoice entity and stub an
``extract`` function" case). It is the W1 sibling of the ``AutomationFlow``
backend: describe/validate only, no execution.

Each ENTITY node becomes an ``@dataclass`` with one typed field per slot; each
OPERATION node becomes a function stub that raises ``NotImplementedError`` and
documents its inputs and any CONSTRAINT guards. The emitted source is run
through :func:`ast.parse` during ``validate()`` so a malformed scaffold is
caught structurally rather than at import time.
"""

from __future__ import annotations

import ast
import keyword
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

# Slot type -> Python annotation.
_SLOT_TYPE_TO_PY: dict[str, str] = {
    "string": "str",
    "number": "int",
}


# ---------------------------------------------------------------------------
# Identifier safety
# ---------------------------------------------------------------------------


def _safe_ident(raw: str, *, fallback: str) -> str:
    """Sanitize ``raw`` into a snake_case Python identifier."""

    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", str(raw)).strip("_").lower()
    if not cleaned or not (cleaned[0].isalpha() or cleaned[0] == "_"):
        cleaned = f"{fallback}_{cleaned}".strip("_") if cleaned else fallback
    if not cleaned:
        cleaned = fallback
    if keyword.iskeyword(cleaned) or keyword.issoftkeyword(cleaned):
        cleaned = f"{cleaned}_"
    return cleaned


def _safe_class_name(raw: str, *, fallback: str) -> str:
    """Sanitize ``raw`` into a PascalCase Python class identifier."""

    parts = [p for p in re.split(r"[^0-9a-zA-Z]+", str(raw)) if p]
    name = "".join(p[:1].upper() + p[1:] for p in parts)
    if not name or not (name[0].isalpha() or name[0] == "_"):
        name = fallback if not name else f"{fallback}{name}"
    if not name:
        name = fallback
    if keyword.iskeyword(name) or keyword.issoftkeyword(name):
        name = f"{name}_"
    return name


# ---------------------------------------------------------------------------
# Module element dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PyValidationFinding:
    field: str
    severity: str        # "error" | "warning"
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "severity": self.severity,
                "message": self.message}


@dataclass(frozen=True)
class PyValidationResult:
    ok: bool
    findings: tuple[PyValidationFinding, ...] = ()

    @property
    def errors(self) -> tuple[PyValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity == "error")

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "findings": [f.to_dict() for f in self.findings]}


@dataclass(frozen=True)
class PyField:
    name: str
    type: str = "Any"

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "type": self.type}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PyField":
        return cls(name=str(d.get("name", "")), type=str(d.get("type", "Any")))


@dataclass(frozen=True)
class PyDataclass:
    name: str
    fields: tuple[PyField, ...] = ()
    doc: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "fields": [f.to_dict() for f in self.fields],
                "doc": self.doc}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PyDataclass":
        return cls(
            name=str(d.get("name", "")),
            fields=tuple(PyField.from_dict(f) for f in d.get("fields", ())),
            doc=str(d.get("doc", "")),
        )


@dataclass(frozen=True)
class PyFunction:
    name: str
    params: tuple[str, ...] = ()
    doc: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "params": list(self.params), "doc": self.doc}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PyFunction":
        return cls(
            name=str(d.get("name", "")),
            params=tuple(str(p) for p in d.get("params", ())),
            doc=str(d.get("doc", "")),
        )


# ---------------------------------------------------------------------------
# The module
# ---------------------------------------------------------------------------


def _docstring_literal(text: str, indent: str) -> str:
    """Emit a safe triple-quoted docstring for ``text`` at ``indent``."""

    safe = str(text).replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return f'{indent}"""{safe}"""'


@dataclass(frozen=True)
class PythonModule:
    module_doc: str = ""
    dataclasses: tuple[PyDataclass, ...] = ()
    functions: tuple[PyFunction, ...] = ()
    provenance: dict = field(default_factory=dict)

    @property
    def module_id(self) -> str:
        stable = {
            "dataclasses": sorted(
                [dc.name, sorted([f.name, f.type] for f in dc.fields)]
                for dc in self.dataclasses
            ),
            "functions": sorted(
                [fn.name, list(fn.params)] for fn in self.functions
            ),
        }
        return sha256_hex(canonical_json(stable))

    def render_source(self) -> str:
        lines: list[str] = []
        lines.append("from __future__ import annotations")
        lines.append("")
        lines.append("from dataclasses import dataclass")
        lines.append("from typing import Any")
        lines.append("")

        for dc in self.dataclasses:
            lines.append("")
            lines.append("@dataclass")
            lines.append(f"class {dc.name}:")
            body_started = False
            if dc.doc:
                lines.append(_docstring_literal(dc.doc, "    "))
                body_started = True
            if dc.fields:
                for f in dc.fields:
                    lines.append(f"    {f.name}: {f.type}")
                body_started = True
            if not body_started:
                lines.append("    pass")

        for fn in self.functions:
            lines.append("")
            params = ", ".join(p for p in fn.params)
            lines.append(f"def {fn.name}({params}) -> Any:")
            doc = fn.doc or f"Stub for {fn.name}."
            lines.append(_docstring_literal(doc, "    "))
            lines.append("    raise NotImplementedError")

        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "module_doc": self.module_doc,
            "dataclasses": [dc.to_dict() for dc in self.dataclasses],
            "functions": [fn.to_dict() for fn in self.functions],
            "provenance": dict(self.provenance),
            "source": self.render_source(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PythonModule":
        return cls(
            module_doc=str(d.get("module_doc", "")),
            dataclasses=tuple(
                PyDataclass.from_dict(dc) for dc in d.get("dataclasses", ())
            ),
            functions=tuple(
                PyFunction.from_dict(fn) for fn in d.get("functions", ())
            ),
            provenance=dict(d.get("provenance", {})),
        )

    def validate(self) -> PyValidationResult:
        findings: list[PyValidationFinding] = []

        source = self.render_source()
        try:
            ast.parse(source)
        except SyntaxError as exc:
            findings.append(PyValidationFinding("source", "error", str(exc)))

        if not self.dataclasses and not self.functions:
            findings.append(PyValidationFinding(
                "module", "warning",
                "module has no dataclasses and no functions"))

        ok = not any(f.severity == "error" for f in findings)
        return PyValidationResult(ok=ok, findings=tuple(findings))


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------


class PythonModuleCompiler:
    target = BackendTarget.PYTHON

    def compile(
        self, graph: IntentGraph, context: Optional[BackendContext] = None
    ) -> CompileResult:
        dataclasses_out: list[PyDataclass] = []
        for i, ent in enumerate(graph.nodes_of(IntentNodeKind.ENTITY)):
            class_name = _safe_class_name(ent.label, fallback=f"Entity{i + 1}")
            fields: list[PyField] = []
            seen: set[str] = set()
            for j, slot in enumerate(ent.slots):
                fname = _safe_ident(slot.name, fallback=f"field{j + 1}")
                while fname in seen:
                    fname = f"{fname}_"
                seen.add(fname)
                fields.append(PyField(name=fname, type=_py_type(slot.type)))
            dataclasses_out.append(PyDataclass(
                name=class_name,
                fields=tuple(fields),
                doc=f"Models the {ent.label} entity.",
            ))

        entity_labels = [
            e.label for e in graph.nodes_of(IntentNodeKind.ENTITY)
        ]
        constraint_labels = [
            c.label for c in graph.nodes_of(IntentNodeKind.CONSTRAINT)
        ]

        functions_out: list[PyFunction] = []
        seen_fns: set[str] = set()
        for i, op in enumerate(graph.nodes_of(IntentNodeKind.OPERATION)):
            verb_slot = op.slot("verb")
            raw_name = (
                str(verb_slot.value)
                if verb_slot and verb_slot.value
                else op.label
            )
            fname = _safe_ident(raw_name, fallback=f"operation{i + 1}")
            while fname in seen_fns:
                fname = f"{fname}_"
            seen_fns.add(fname)

            if entity_labels:
                params = tuple(
                    _safe_ident(lbl, fallback=f"arg{k + 1}")
                    for k, lbl in enumerate(entity_labels)
                )
                # Dedupe params while preserving order.
                deduped: list[str] = []
                pseen: set[str] = set()
                for p in params:
                    while p in pseen:
                        p = f"{p}_"
                    pseen.add(p)
                    deduped.append(p)
                params = tuple(deduped)
            else:
                params = ("data",)

            doc_parts = [f"{raw_name} operation."]
            doc_parts.append("Inputs: " + ", ".join(params) + ".")
            if constraint_labels:
                doc_parts.append(
                    "Constraints: " + ", ".join(constraint_labels) + "."
                )
            functions_out.append(PyFunction(
                name=fname,
                params=params,
                doc=" ".join(doc_parts),
            ))

        module = PythonModule(
            module_doc=_module_doc(graph),
            dataclasses=tuple(dataclasses_out),
            functions=tuple(functions_out),
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


def _py_type(slot_type: str) -> str:
    if slot_type in ("predicate",):
        return "Any"
    return _SLOT_TYPE_TO_PY.get(str(slot_type), "Any")


def _module_doc(graph: IntentGraph) -> str:
    first_line = (graph.raw_text or "").splitlines()[0:1]
    return first_line[0].strip() if first_line else ""


__all__ = [
    "PyValidationFinding",
    "PyValidationResult",
    "PyField",
    "PyDataclass",
    "PyFunction",
    "PythonModule",
    "PythonModuleCompiler",
]
