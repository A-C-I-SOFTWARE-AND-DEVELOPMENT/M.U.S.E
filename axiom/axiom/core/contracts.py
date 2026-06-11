"""EARS intent + Z3 contracts (defends I2).

"No spec, no parse": a unit without a well-formed EARS intent clause
is rejected before any other check runs. Contracts are restricted-AST
expressions compiled to Z3; the conjunction must be satisfiable
(consistent) and each clause must be non-vacuous (not a tautology).
At runtime the same clauses are evaluated again on concrete values —
a statically-clean unit that lies at runtime yields no result.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import z3  # ty: ignore[unresolved-import]

# ---------------------------------------------------------------------------
# EARS — Easy Approach to Requirements Syntax (4 patterns)
# ---------------------------------------------------------------------------

_EARS_PATTERNS: dict[str, re.Pattern] = {
    "ubiquitous": re.compile(r"^THE .+? SHALL .+\.$"),
    "event": re.compile(r"^WHEN .+?, THE .+? SHALL .+\.$"),
    "state": re.compile(r"^WHILE .+?, THE .+? SHALL .+\.$"),
    "optional": re.compile(r"^WHERE .+?, THE .+? SHALL .+\.$"),
}


class SpecError(ValueError):
    """Raised when an intent is not a well-formed EARS clause."""


@dataclass(frozen=True)
class EarsClause:
    pattern: str  # ubiquitous | event | state | optional
    text: str


def parse_ears(text: str) -> EarsClause:
    """Parse *text* as one EARS clause or raise SpecError (no spec, no parse)."""
    text = text.strip()
    for pattern, rx in _EARS_PATTERNS.items():
        if rx.match(text):
            return EarsClause(pattern=pattern, text=text)
    raise SpecError(f"intent is not a well-formed EARS clause: {text!r}")


# ---------------------------------------------------------------------------
# Restricted-AST contract expressions -> Z3
# ---------------------------------------------------------------------------

_ALLOWED_BINOPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}
_ALLOWED_CMPOPS: dict[type[ast.cmpop], Callable[[Any, Any], Any]] = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
}


class ContractError(ValueError):
    """Raised when a contract expression is outside the restricted language."""


def _z3_var(name: str, kind: str):
    if kind == "bool":
        return z3.Bool(name)
    if kind == "float":
        return z3.Real(name)
    raise ContractError(f"unknown param type {kind!r} for {name!r}")


def _compile(node: ast.AST, env: dict):
    """Recursively compile a restricted AST node against *env*."""
    if isinstance(node, ast.Expression):
        return _compile(node.body, env)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return z3.BoolVal(node.value)
        if isinstance(node.value, (int, float)):
            return z3.RealVal(node.value)
        raise ContractError(f"constant {node.value!r} not allowed")
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise ContractError(f"unknown name {node.id!r} in contract")
        return env[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](
            _compile(node.left, env), _compile(node.right, env)
        )
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return -_compile(node.operand, env)
        if isinstance(node.op, ast.Not):
            return z3.Not(_compile(node.operand, env))
        raise ContractError("unary op not allowed")
    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise ContractError("chained comparisons not allowed")
        op = node.ops[0]
        if type(op) not in _ALLOWED_CMPOPS:
            raise ContractError("comparison op not allowed")
        return _ALLOWED_CMPOPS[type(op)](
            _compile(node.left, env), _compile(node.comparators[0], env)
        )
    if isinstance(node, ast.BoolOp):
        parts = [_compile(v, env) for v in node.values]
        if isinstance(node.op, ast.And):
            return z3.And(*parts)
        if isinstance(node.op, ast.Or):
            return z3.Or(*parts)
        raise ContractError("bool op not allowed")
    raise ContractError(f"AST node {type(node).__name__} not allowed in contracts")


def compile_contract(expr: str, params: dict[str, str], result_type: str = "float"):
    """Compile a contract expression to a Z3 boolean over params + result."""
    env = {name: _z3_var(name, kind) for name, kind in params.items()}
    env["result"] = _z3_var("result", result_type)
    try:
        tree = ast.parse(expr, filename="<contract>", mode="eval")
    except SyntaxError as e:
        raise ContractError(f"contract does not parse: {expr!r}: {e}") from e
    return _compile(tree, env)


@dataclass(frozen=True)
class ContractReport:
    satisfiable: bool
    consistent: bool
    vacuous_clauses: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.satisfiable and self.consistent and not self.vacuous_clauses


def check_contracts(
    contracts: tuple[str, ...] | list[str],
    params: dict[str, str],
    result_type: str = "float",
) -> ContractReport:
    """Static contract check: SAT + consistency + per-clause vacuity."""
    compiled = [compile_contract(c, params, result_type) for c in contracts]

    # Satisfiability / consistency: the conjunction must be SAT.
    solver = z3.Solver()
    for c in compiled:
        solver.add(c)
    sat = solver.check() == z3.sat

    # Vacuity: a clause whose negation is UNSAT is a tautology — it
    # constrains nothing and is treated as a spec error.
    vacuous: list[str] = []
    for text, c in zip(contracts, compiled):
        s = z3.Solver()
        s.add(z3.Not(c))
        if s.check() == z3.unsat:
            vacuous.append(text)

    return ContractReport(
        satisfiable=sat, consistent=sat, vacuous_clauses=tuple(vacuous)
    )


# ---------------------------------------------------------------------------
# Concrete (runtime) evaluation of the same clauses
# ---------------------------------------------------------------------------


class PostconditionViolation(RuntimeError):
    """A unit's concrete result violated its own contract."""

    def __init__(self, clause: str, values: dict):
        super().__init__(f"postcondition violated: {clause!r} with {values!r}")
        self.clause = clause
        self.values = dict(values)


def eval_concrete(expr: str, values: dict) -> bool:
    """Evaluate a contract on concrete values, with no builtins in scope.

    The expression has already passed the restricted-AST compile at
    verify time, so eval here sees only the whitelisted grammar.
    """
    compile_contract(expr, {k: "bool" if isinstance(v, bool) else "float"
                            for k, v in values.items() if k != "result"},
                     "bool" if isinstance(values.get("result"), bool) else "float")
    return bool(eval(expr, {"__builtins__": {}}, dict(values)))  # noqa: S307


def enforce_postconditions(
    contracts: tuple[str, ...] | list[str], values: dict
) -> None:
    """Raise PostconditionViolation on the first failing clause."""
    for clause in contracts:
        if not eval_concrete(clause, values):
            raise PostconditionViolation(clause, values)
