"""FastMCP agent surface (the only door an agent gets into AXIOM).

Every tool returns machine-readable results; rejection errors are
structured so a retry loop can converge. The tools never bypass the
verifier — there is no "register unverified" door, no way to write
the ledger directly, and owner-gated conflicts come back as
owner_required errors instead of silent overwrites.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from ..core.canonical import Unit
from ..core.contracts import (
    ContractError,
    PostconditionViolation,
    SpecError,
    check_contracts,
    parse_ears,
)
from ..core.ledger import Ledger
from ..core.registry import Registry, UnresolvedReferenceError
from ..core.verifier import Attestation, Verifier
from ..forge.engine import ForgeEngine
from ..memory.beliefs import OwnerRequired
from ..memory.mind import Mind

mcp = FastMCP("axiom")

# Module-level stores; tests inject their own via configure().
_registry: Registry | None = None
_ledger: Ledger | None = None
_verifier: Verifier | None = None
_mind: Mind | None = None
_forge: ForgeEngine | None = None


def configure(
    registry: Registry, ledger: Ledger, data_dir: str = "data"
) -> None:
    """Wire the full organism behind the tool surface."""
    global _registry, _ledger, _verifier, _mind, _forge
    _registry = registry
    _ledger = ledger
    _verifier = Verifier(registry, ledger)
    _mind = Mind(data_dir, ledger)
    _forge = ForgeEngine(
        _verifier,
        ratings_path=str(Path(data_dir) / "ratings.db"),
        data_dir=data_dir,
    )


def _host() -> tuple[Registry, Ledger, Verifier, Mind, ForgeEngine]:
    if _verifier is None:
        configure(Registry("data/registry.db"), Ledger("data/ledger.db"))
    return _registry, _ledger, _verifier, _mind, _forge


# ------------------------------------------------------------------ registry

@mcp.tool
def registry_search(name: str) -> list[dict]:
    """Search registered units by name metadata. Hashes are identity;
    names are hints. Search before you invent."""
    registry, *_ = _host()
    return registry.search(name)


@mcp.tool
def verify_and_register(unit_form: dict) -> dict:
    """Verify a unit form; on success register + attest it.
    Returns {ok, unit_hash, checks} or {ok: false, errors: [...]}."""
    *_, verifier, _m, _f = _host()
    unit = Unit.from_form(unit_form)
    outcome = verifier.verify(unit)
    if isinstance(outcome, Attestation):
        return {
            "ok": True,
            "unit_hash": outcome.unit_hash,
            "checks": list(outcome.checks),
            "warnings": list(outcome.warnings),
        }
    return {"ok": False, "errors": [dict(e) for e in outcome.errors]}


@mcp.tool
def unit_compose(
    name: str,
    doc: str,
    params: dict,
    intent: str,
    contracts: list[str],
    body: list[dict],
    refs: dict | None = None,
    effects: list[str] | None = None,
) -> dict:
    """Build a unit form from parts, verifying as you go: every ref
    must resolve, the intent must parse as EARS, the contracts must
    compile and be consistent. Returns {ok, unit_form, unit_hash}
    (prospective hash; not yet registered) or {ok: false, errors}."""
    registry, *_ = _host()
    errors: list[dict] = []

    for alias, h in (refs or {}).items():
        if not registry.exists(h):
            errors.append({"check": "refs:resolve-or-fail",
                           "unresolved": h, "alias": alias})
    try:
        parse_ears(intent)
    except SpecError as e:
        errors.append({"check": "intent:EARS", "error": str(e)})
    try:
        report = check_contracts(tuple(contracts), dict(params))
        if not report.satisfiable:
            errors.append({"check": "contracts:z3",
                           "error": "contracts unsatisfiable"})
        for clause in report.vacuous_clauses:
            errors.append({"check": "contracts:z3",
                           "error": "vacuous clause", "clause": clause})
    except ContractError as e:
        errors.append({"check": "contracts:z3", "error": str(e)})

    if errors:
        return {"ok": False, "errors": errors}

    unit = Unit(
        name=name, doc=doc, params=dict(params), intent=intent,
        contracts=tuple(contracts), effects=tuple(effects or ()),
        refs=dict(refs or {}), body=tuple(dict(op) for op in body),
    )
    return {"ok": True, "unit_form": unit.full_form(),
            "unit_hash": unit.unit_hash()}


# ----------------------------------------------------------------- execution

@mcp.tool
def run(unit_hash: str, args: dict, capabilities: list[str] | None = None) -> dict:
    """Run an attested unit. Postconditions are enforced on the concrete
    result; a violating run returns an error, never a result."""
    *_, verifier, _m, _f = _host()
    try:
        result = verifier.run(unit_hash, args,
                              granted=frozenset(capabilities or ()))
        return {"ok": True, "result": result}
    except UnresolvedReferenceError as e:
        return {"ok": False, "error": "unresolved", "unit_hash": e.unit_hash}
    except PostconditionViolation as e:
        return {"ok": False, "error": "postcondition", "clause": e.clause}
    except PermissionError as e:
        return {"ok": False, "error": "capability", "detail": str(e)}


# -------------------------------------------------------------------- memory

@mcp.tool
def memory_observe(
    content: str,
    source_grade: str = "",
    contradicts: int | None = None,
) -> dict:
    """Record an observation. If it contradicts an entrenched belief,
    the conflict is ledgered and returned as owner_required — never
    silently resolved."""
    *_, mind, _f = _host()
    try:
        memory_id = mind.observe(content, source_grade, contradicts=contradicts)
        return {"ok": True, "memory_id": memory_id}
    except OwnerRequired as e:
        return {"ok": False, "error": "owner_required",
                "belief_id": e.belief_id, "belief": e.statement}


@mcp.tool
def memory_query(query: str, k: int = 5) -> list[dict]:
    """Routed recall over the memory plane (temporal / factual /
    conceptual / decision weighting is chosen from the query itself)."""
    *_, mind, _f = _host()
    return mind.recall(query, k=k)


# --------------------------------------------------------------------- forge

@mcp.tool
def forge_run(units: dict, probes: list[dict]) -> dict:
    """Run a hard-gated tournament over unit forms (cid -> unit_form).
    The verifier (static + runtime probes) is the gate; judges only
    rank what the theorem already admitted."""
    *_, forge = _host()
    parsed = {cid: Unit.from_form(form) for cid, form in units.items()}
    return forge.run_spec_tournament(parsed, probes=probes)


# -------------------------------------------------------------------- ledger

@mcp.tool
def ledger_history(unit_hash: str) -> list[dict]:
    """Every ledger event that touches *unit_hash* — the unit's full
    auditable history, from attestation through every run."""
    _r, ledger, *_ = _host()
    return [
        {"kind": ev["kind"], "payload": ev["payload"], "ts": ev["ts"],
         "hash": ev["hash"]}
        for ev in ledger.events()
        if ev["payload"].get("unit_hash") == unit_hash
    ]


@mcp.tool
def ledger_verify() -> dict:
    """Recompute the full hash chain and signatures."""
    _r, ledger, *_ = _host()
    return {"chain_valid": ledger.verify_chain(), "events": ledger.count()}


if __name__ == "__main__":
    mcp.run()
