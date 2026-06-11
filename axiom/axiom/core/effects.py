"""Effect declaration, capability gating, and the op-language interpreter
(defends I1 and I2).

A unit declares every effect it may have. The executor refuses to run a
unit whose declared effects exceed the granted capability set — an
undeclared effect can never fire. The verifier separately checks the
callee effect closure: a unit's declared effects must cover the union
of its callees' effects.

The body language is a tiny op program: each op is a dict
  {"op": <name>, "in": [operands], "into": <var>}
where an operand is a variable name (str) or a numeric literal. Unit
calls use {"op": "call", "ref": <alias or "#"+hash>, "in": [...]}.
A "#"-prefixed ref is a direct content hash; anything else must be an
alias declared in the unit's refs map — resolve-or-fail, never a guess.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .canonical import Unit, effect_in_vocab
from .registry import Registry, UnresolvedReferenceError

if TYPE_CHECKING:  # pragma: no cover
    pass

HASH_REF_PREFIX = "#"

_BIN_OPS = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "div": lambda a, b: a / b,
}


class UndeclaredEffectError(PermissionError):
    """A unit declared effects outside the granted capability set."""


class EffectVocabularyError(ValueError):
    """A declared effect is outside the closed vocabulary."""


class EffectClosureError(ValueError):
    """A callee's effects are not covered by the caller's declaration."""


class BodyError(ValueError):
    """The body program is malformed."""


def check_effect_vocab(unit: Unit) -> None:
    """Every declared effect must be in the vocabulary (or regulated:)."""
    for eff in unit.effects:
        if not effect_in_vocab(eff):
            raise EffectVocabularyError(f"effect {eff!r} not in vocabulary")


def resolve_ref(ref: str, unit: Unit, registry: Registry) -> Unit:
    """Resolve a body ref (alias or #hash) to a Unit — or fail hard."""
    if ref.startswith(HASH_REF_PREFIX):
        return registry.resolve(ref[len(HASH_REF_PREFIX):])
    if ref not in unit.refs:
        raise UnresolvedReferenceError(ref)
    return registry.resolve(unit.refs[ref])


def callee_effect_closure(unit: Unit, registry: Registry) -> None:
    """The caller's declared effects must cover every callee's effects."""
    declared = set(unit.effects)
    for alias, h in unit.refs.items():
        callee = registry.resolve(h)
        missing = set(callee.effects) - declared
        if missing:
            raise EffectClosureError(
                f"callee {alias!r} has effects {sorted(missing)} "
                f"not declared by caller"
            )


def gate_capabilities(unit: Unit, granted: frozenset[str] | set[str]) -> None:
    """Refuse execution if declared effects exceed granted capabilities."""
    excess = set(unit.effects) - set(granted)
    if excess:
        raise UndeclaredEffectError(
            f"effects {sorted(excess)} not within granted capabilities"
        )


class Interpreter:
    """Executes a unit body. Pure ops + capability-gated calls only."""

    MAX_CALL_DEPTH = 32

    def __init__(self, registry: Registry):
        self.registry = registry

    def _operand(self, operand: Any, scope: dict) -> Any:
        if isinstance(operand, str):
            if operand not in scope:
                raise BodyError(f"unknown variable {operand!r}")
            return scope[operand]
        if isinstance(operand, (int, float, bool)):
            return operand
        raise BodyError(f"bad operand {operand!r}")

    def execute(
        self,
        unit: Unit,
        args: dict[str, Any],
        granted: frozenset[str] | set[str] = frozenset(),
        _depth: int = 0,
    ) -> Any:
        """Run *unit* with *args* under the granted capability set."""
        if _depth > self.MAX_CALL_DEPTH:
            raise BodyError("call depth exceeded")
        gate_capabilities(unit, granted)

        missing = set(unit.params) - set(args)
        if missing:
            raise BodyError(f"missing args: {sorted(missing)}")
        scope: dict[str, Any] = {k: args[k] for k in unit.params}

        for op in unit.body:
            kind = op.get("op")
            if kind == "lit":
                scope[op["into"]] = op["in"][0]
            elif kind in _BIN_OPS:
                a = self._operand(op["in"][0], scope)
                b = self._operand(op["in"][1], scope)
                scope[op["into"]] = _BIN_OPS[kind](a, b)
            elif kind == "neg":
                scope[op["into"]] = -self._operand(op["in"][0], scope)
            elif kind == "call":
                callee = resolve_ref(op["ref"], unit, self.registry)
                # Positional binding follows sorted param-name order: the
                # canonical (hashed) form sorts keys, so insertion order
                # must never carry meaning.
                call_args = {
                    p: self._operand(v, scope)
                    for p, v in zip(sorted(callee.params), op["in"])
                }
                scope[op["into"]] = self.execute(
                    callee, call_args, granted=granted, _depth=_depth + 1
                )
            elif kind == "return":
                return self._operand(op["in"][0], scope)
            else:
                raise BodyError(f"unknown op {kind!r}")
        raise BodyError("body has no return op")
