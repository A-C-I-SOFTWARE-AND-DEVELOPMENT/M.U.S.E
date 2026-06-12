"""SQL-query (W2) backend.

Compiles a *declarative-read* :class:`IntentGraph` into an ``SqlSelect`` — a
small, validatable, parameterized ``SELECT`` document (the "show me invoices
from vendors that are new" case).

SECURITY-CRITICAL
-----------------
This compiler **never** string-interpolates constraint values into the SQL
text. Every constraint becomes a *named placeholder* (``:p0``, ``:p1``, …);
the raw expression text is stashed in ``params`` as a provenance note, never
spliced into ``render_sql()``. The rendered SQL is therefore always a safe,
parameterized template — binding live values is the caller's job, done by the
DB driver, not by us.

Like the other IR backends this is describe/validate only — pure, IO-free, no
execution and no disk.
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

# Comparison operators we can recognize in a constraint expression. Order
# matters: longer/two-char operators are tried before their single-char
# prefixes so ``>=`` is not mis-parsed as ``>``.
_OP_TOKENS: tuple[tuple[str, str], ...] = (
    (">=", ">="),
    ("<=", "<="),
    ("!=", "!="),
    ("<>", "!="),
    ("=", "="),
    (">", ">"),
    ("<", "<"),
    (" is not ", "!="),
    (" is ", "="),
    (" equals ", "="),
    (" >= ", ">="),
    (" <= ", "<="),
)

# Operators that may legally appear in the rendered SQL.
_ALLOWED_SQL_OPS = frozenset({"=", "!=", "<", ">", "<=", ">="})

_IDENT_RE = re.compile(r"[^A-Za-z0-9_]+")


def _sanitize_identifier(raw: str) -> str:
    """Reduce an arbitrary label to a safe SQL identifier.

    Whitespace/punctuation collapse to underscores; anything not in
    ``[A-Za-z0-9_]`` is dropped. A leading digit gets an underscore prefix so
    the result is always a valid identifier (or empty).
    """

    cleaned = _IDENT_RE.sub("_", raw.strip()).strip("_")
    if cleaned and cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned


# ---------------------------------------------------------------------------
# Findings / validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SqlValidationFinding:
    field: str
    severity: str        # "error" | "warning"
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "severity": self.severity,
                "message": self.message}


@dataclass(frozen=True)
class SqlValidationResult:
    ok: bool
    findings: tuple[SqlValidationFinding, ...] = ()

    @property
    def errors(self) -> tuple[SqlValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity == "error")

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "findings": [f.to_dict() for f in self.findings]}


# ---------------------------------------------------------------------------
# Query parts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SqlColumn:
    name: str
    source_table: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "source_table": self.source_table}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SqlColumn":
        return cls(name=str(d.get("name", "")),
                   source_table=str(d.get("source_table", "")))


@dataclass(frozen=True)
class SqlPredicate:
    column: str
    op: str
    param: str           # a placeholder NAME like "p0" — never a literal value

    def to_dict(self) -> dict[str, Any]:
        return {"column": self.column, "op": self.op, "param": self.param}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SqlPredicate":
        return cls(column=str(d.get("column", "")), op=str(d.get("op", "=")),
                   param=str(d.get("param", "")))


@dataclass(frozen=True)
class SqlSelect:
    tables: tuple[str, ...] = ()
    columns: tuple[SqlColumn, ...] = ()
    predicates: tuple[SqlPredicate, ...] = ()
    # placeholder_name -> provenance note / raw expr. NEVER live values.
    params: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)

    @property
    def query_id(self) -> str:
        stable = {
            "tables": sorted(self.tables),
            "columns": sorted([c.name, c.source_table] for c in self.columns),
            "predicates": sorted(
                [p.column, p.op, p.param] for p in self.predicates
            ),
            "params": sorted(self.params.keys()),
        }
        return sha256_hex(canonical_json(stable))

    def render_sql(self) -> str:
        """Render a parameterized ``SELECT`` using only ``:pN`` placeholders.

        No constraint value is ever interpolated; the WHERE clause references
        placeholder names exclusively.
        """

        cols = ", ".join(c.name for c in self.columns) if self.columns else "*"
        tables = ", ".join(self.tables) if self.tables else ""
        sql = f"SELECT {cols} FROM {tables}".rstrip()
        if self.predicates:
            clauses = [
                f"{p.column} {p.op} :{p.param}" for p in self.predicates
            ]
            sql += " WHERE " + " AND ".join(clauses)
        return sql

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "tables": list(self.tables),
            "columns": [c.to_dict() for c in self.columns],
            "predicates": [p.to_dict() for p in self.predicates],
            "params": dict(self.params),
            "provenance": dict(self.provenance),
            "sql": self.render_sql(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SqlSelect":
        return cls(
            tables=tuple(d.get("tables", ())),
            columns=tuple(SqlColumn.from_dict(c) for c in d.get("columns", ())),
            predicates=tuple(
                SqlPredicate.from_dict(p) for p in d.get("predicates", ())
            ),
            params=dict(d.get("params", {})),
            provenance=dict(d.get("provenance", {})),
        )

    def validate(self) -> SqlValidationResult:
        findings: list[SqlValidationFinding] = []

        if len(self.tables) < 1:
            findings.append(SqlValidationFinding(
                "tables", "error", "a SELECT needs at least one table"))

        for c in self.columns:
            if not c.name.strip():
                findings.append(SqlValidationFinding(
                    "columns", "error", "a column name must not be empty"))

        if any(c.name.strip() == "*" for c in self.columns) or not self.columns:
            findings.append(SqlValidationFinding(
                "columns", "warning",
                "SELECT * is unbounded; prefer explicit columns"))

        for p in self.predicates:
            if p.param not in self.params:
                findings.append(SqlValidationFinding(
                    "predicates", "error",
                    f"predicate placeholder ':{p.param}' has no params entry"))
            if p.op not in _ALLOWED_SQL_OPS:
                findings.append(SqlValidationFinding(
                    "predicates", "warning",
                    f"unrecognized operator '{p.op}'"))

        ok = not any(f.severity == "error" for f in findings)
        return SqlValidationResult(ok=ok, findings=tuple(findings))


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------


def _constraint_expr(node) -> str:
    slot = node.slot("expr")
    if slot is not None and slot.value is not None:
        return str(slot.value)
    return node.label


def _parse_constraint(expr: str) -> Optional[tuple[str, str, str]]:
    """Best-effort parse of ``column op value`` from a constraint expression.

    Returns ``(column, op, value_text)`` or ``None`` if no operator token is
    found. The ``value_text`` is *not* used in SQL — only stashed as provenance.
    """

    lowered = expr.lower()
    for token, op in _OP_TOKENS:
        idx = lowered.find(token)
        if idx <= 0:
            continue
        left = expr[:idx].strip()
        right = expr[idx + len(token):].strip()
        column = _sanitize_identifier(left)
        if column:
            return column, op, right
    return None


class SqlQueryCompiler:
    target = BackendTarget.SQL

    def compile(
        self, graph: IntentGraph, context: Optional[BackendContext] = None
    ) -> CompileResult:
        notes: list[str] = []

        # -- tables: DATA_SOURCE + ENTITY labels (sanitized) ----------------
        tables: list[str] = []
        seen: set[str] = set()
        for n in graph.nodes_of(IntentNodeKind.DATA_SOURCE):
            ident = _sanitize_identifier(n.label)
            if ident and ident not in seen:
                seen.add(ident)
                tables.append(ident)
        entity_nodes = graph.nodes_of(IntentNodeKind.ENTITY)
        for n in entity_nodes:
            ident = _sanitize_identifier(n.label)
            if ident and ident not in seen:
                seen.add(ident)
                tables.append(ident)

        # -- columns: entity slot names -------------------------------------
        columns: list[SqlColumn] = []
        col_seen: set[tuple[str, str]] = set()
        for n in entity_nodes:
            table = _sanitize_identifier(n.label)
            for s in n.slots:
                col_name = _sanitize_identifier(s.name)
                key = (col_name, table)
                if col_name and key not in col_seen:
                    col_seen.add(key)
                    columns.append(SqlColumn(name=col_name, source_table=table))
        if not columns:
            columns.append(SqlColumn(name="*"))
            notes.append(
                "warning: no entity slot columns found; selecting all columns (*)")

        # -- predicates: CONSTRAINT nodes -> parameterized predicates -------
        predicates: list[SqlPredicate] = []
        params: dict[str, str] = {}
        for i, n in enumerate(graph.nodes_of(IntentNodeKind.CONSTRAINT)):
            pname = f"p{i}"
            expr = _constraint_expr(n)
            parsed = _parse_constraint(expr)
            if parsed is not None:
                column, op, value_text = parsed
                predicates.append(SqlPredicate(column=column, op=op, param=pname))
                params[pname] = f"constraint: {expr} (bound value: {value_text})"
            else:
                # Unparseable: still emit a placeholder, never a literal value.
                # Use a generic column so the raw phrase lives only in params
                # provenance, never leaking into the SQL text.
                predicates.append(
                    SqlPredicate(column="predicate", op="=", param=pname))
                params[pname] = f"constraint (raw, unparsed): {expr}"
                notes.append(
                    f"warning: constraint '{expr}' not fully parsed; "
                    f"emitted placeholder :{pname}")

        select = SqlSelect(
            tables=tuple(tables),
            columns=tuple(columns),
            predicates=tuple(predicates),
            params=params,
            provenance={"graph_id": graph.graph_id},
        )

        result = select.validate()
        notes.extend(f"{f.severity}: {f.message}" for f in result.findings)
        return CompileResult(
            target=self.target,
            artifact=select,
            artifact_dict=select.to_dict(),
            gate_packet=None,
            notes=tuple(notes),
        )


__all__ = [
    "SqlValidationFinding",
    "SqlValidationResult",
    "SqlColumn",
    "SqlPredicate",
    "SqlSelect",
    "SqlQueryCompiler",
]
