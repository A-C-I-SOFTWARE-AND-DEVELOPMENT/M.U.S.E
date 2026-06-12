"""The verification pipeline — the gate (defends I1, I2, I3 together).

Nothing enters the registry or earns an attestation without passing
every check: EARS intent present, effects in vocabulary, references
resolved, Z3 contracts satisfiable + consistent + non-vacuous, callee
effect closure respected. At runtime, postconditions are enforced
again on concrete values — a unit that lies at runtime yields no
result and a violation event in the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .canonical import Unit
from .contracts import (
    Z3_AVAILABLE,
    ContractError,
    PostconditionViolation,
    SpecError,
    check_contracts,
    enforce_postconditions,
    parse_ears,
)
from .effects import (
    EffectClosureError,
    EffectVocabularyError,
    HASH_REF_PREFIX,
    Interpreter,
    callee_effect_closure,
    check_effect_vocab,
)
from .ledger import Ledger
from .registry import Registry, UnresolvedReferenceError

CHECKS = (
    "intent:EARS",
    "effects:vocab",
    "refs:resolve-or-fail",
    "contracts:z3",
)


@dataclass(frozen=True)
class Attestation:
    unit_hash: str
    checks: tuple[str, ...]
    event_hash: str
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return True


@dataclass(frozen=True)
class Rejection:
    errors: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return False


class Verifier:
    """Runs the full gate; on success registers + attests the unit."""

    def __init__(self, registry: Registry, ledger: Ledger):
        self.registry = registry
        self.ledger = ledger
        self.interpreter = Interpreter(registry)

    # ---------------------------------------------------------------- verify
    def verify(self, unit: Unit) -> Attestation | Rejection:
        errors: list[dict] = []
        warnings: list[str] = []

        # 1. intent:EARS — no spec, no parse.
        try:
            parse_ears(unit.intent)
        except SpecError as e:
            errors.append({"check": "intent:EARS", "error": str(e)})

        # 2. effects:vocab
        try:
            check_effect_vocab(unit)
        except EffectVocabularyError as e:
            errors.append({"check": "effects:vocab", "error": str(e)})

        # 3. refs:resolve-or-fail — every ref and every call target.
        for alias, h in unit.refs.items():
            if not self.registry.exists(h):
                errors.append(
                    {"check": "refs:resolve-or-fail", "unresolved": h, "alias": alias}
                )
            else:
                dep = self.registry.deprecated_by(h)
                if dep:
                    warnings.append(
                        f"ref {alias!r} -> {h} is deprecated; successor {dep}"
                    )
        for op in unit.body:
            if op.get("op") == "call":
                ref = op.get("ref", "")
                if ref.startswith(HASH_REF_PREFIX):
                    if not self.registry.exists(ref[len(HASH_REF_PREFIX):]):
                        errors.append(
                            {"check": "refs:resolve-or-fail", "unresolved": ref}
                        )
                elif ref not in unit.refs:
                    errors.append({"check": "refs:resolve-or-fail", "unresolved": ref})

        # 4. contracts:z3 — satisfiable + consistent + non-vacuous.
        # Without z3 the check degrades to grammar validation and says so.
        contracts_check = "contracts:z3" if Z3_AVAILABLE else "contracts:degraded"
        try:
            report = check_contracts(unit.contracts, unit.params)
            if report.degraded:
                warnings.append(
                    "z3 unavailable — contracts checked syntactically, not proven"
                )
            if not report.satisfiable:
                errors.append(
                    {"check": contracts_check, "error": "contracts unsatisfiable"}
                )
            for clause in report.vacuous_clauses:
                errors.append(
                    {"check": contracts_check, "error": "vacuous clause",
                     "clause": clause}
                )
        except ContractError as e:
            errors.append({"check": contracts_check, "error": str(e)})

        # 5. callee effect closure (only meaningful if refs resolved).
        if not any(e.get("check") == "refs:resolve-or-fail" for e in errors):
            try:
                callee_effect_closure(unit, self.registry)
            except EffectClosureError as e:
                errors.append({"check": "effects:vocab", "error": str(e)})

            # 6. Cycle guard. Content addressing makes honest cycles
            # unconstructible (a unit's hash depends on its refs), so a
            # cycle is proof of a corrupted registry — reject hard.
            cycle = self._find_cycle(unit)
            if cycle:
                errors.append(
                    {"check": "refs:resolve-or-fail", "error": "cycle",
                     "cycle": cycle}
                )

        if errors:
            return Rejection(errors=tuple(errors))

        # All checks green: register + attest (degraded label stays honest).
        checks = tuple(
            contracts_check if c == "contracts:z3" else c for c in CHECKS
        )
        unit_hash = self.registry.register(unit, self.ledger.signing_key)
        event_hash = self.ledger.append(
            "artifact_attestation",
            {"unit_hash": unit_hash, "name": unit.name, "checks": list(checks)},
        )
        return Attestation(
            unit_hash=unit_hash,
            checks=checks,
            event_hash=event_hash,
            warnings=tuple(warnings),
        )

    def _find_cycle(self, unit: Unit) -> list[str] | None:
        """DFS over the resolved ref graph; returns the cycle path if any."""
        visiting: list[str] = []
        done: set[str] = set()

        def visit(h: str) -> list[str] | None:
            if h in visiting:
                return visiting[visiting.index(h):] + [h]
            if h in done:
                return None
            visiting.append(h)
            try:
                callee = self.registry.resolve(h)
            except UnresolvedReferenceError:
                visiting.pop()
                done.add(h)
                return None
            for child in callee.refs.values():
                found = visit(child)
                if found:
                    return found
            visiting.pop()
            done.add(h)
            return None

        for h in unit.refs.values():
            found = visit(h)
            if found:
                return found
        return None

    # ------------------------------------------------------------------- run
    def run(
        self,
        unit_hash: str,
        args: dict[str, Any],
        granted: frozenset[str] | set[str] = frozenset(),
    ) -> Any:
        """Execute an attested unit; enforce postconditions on the
        concrete result. A violating run yields no result — only a
        violation event."""
        unit = self.registry.resolve(unit_hash)  # resolve-or-fail
        result = self.interpreter.execute(unit, args, granted=granted)
        values = dict(args)
        values["result"] = result
        try:
            enforce_postconditions(unit.contracts, values)
        except PostconditionViolation as e:
            self.ledger.append(
                "process_event",
                {"unit_hash": unit_hash, "op": "run", "violation": e.clause,
                 "args": {k: v for k, v in args.items()}},
            )
            raise
        self.ledger.append(
            "process_event",
            {"unit_hash": unit_hash, "op": "run", "result": result,
             "args": {k: v for k, v in args.items()}},
        )
        return result
