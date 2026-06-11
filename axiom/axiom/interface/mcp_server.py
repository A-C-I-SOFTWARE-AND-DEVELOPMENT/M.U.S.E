"""FastMCP agent surface (the only door an agent gets into AXIOM).

Every tool returns machine-readable results; rejection errors are
structured so a retry loop can converge. The tools never bypass the
verifier — there is no "register unverified" door.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP

from ..core.canonical import Unit
from ..core.ledger import Ledger
from ..core.registry import Registry, UnresolvedReferenceError
from ..core.verifier import Attestation, Verifier
from ..core.contracts import PostconditionViolation

mcp = FastMCP("axiom")

# Default on-disk stores; tests construct their own.
_registry: Registry | None = None
_ledger: Ledger | None = None
_verifier: Verifier | None = None


def _stores() -> tuple[Registry, Ledger, Verifier]:
    global _registry, _ledger, _verifier
    if _verifier is None:
        _registry = Registry("data/registry.db")
        _ledger = Ledger("data/ledger.db")
        _verifier = Verifier(_registry, _ledger)
    return _registry, _ledger, _verifier


def configure(registry: Registry, ledger: Ledger) -> None:
    """Inject stores (used by tests and embedding hosts)."""
    global _registry, _ledger, _verifier
    _registry = registry
    _ledger = ledger
    _verifier = Verifier(registry, ledger)


@mcp.tool
def registry_search(name: str) -> list[dict]:
    """Search registered units by name metadata. Hashes are identity;
    names are hints. Search before you invent."""
    registry, _, _ = _stores()
    return registry.search(name)


@mcp.tool
def verify_and_register(unit_form: dict) -> dict:
    """Verify a unit form; on success register + attest it.
    Returns {ok, unit_hash, checks} or {ok: false, errors: [...]}."""
    _, _, verifier = _stores()
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
def run(unit_hash: str, args: dict, capabilities: list[str] | None = None) -> dict:
    """Run an attested unit. Postconditions are enforced on the concrete
    result; a violating run returns an error, never a result."""
    _, _, verifier = _stores()
    try:
        result = verifier.run(unit_hash, args, granted=frozenset(capabilities or ()))
        return {"ok": True, "result": result}
    except UnresolvedReferenceError as e:
        return {"ok": False, "error": "unresolved", "unit_hash": e.unit_hash}
    except PostconditionViolation as e:
        return {"ok": False, "error": "postcondition", "clause": e.clause}
    except PermissionError as e:
        return {"ok": False, "error": "capability", "detail": str(e)}


@mcp.tool
def ledger_verify() -> dict:
    """Recompute the full hash chain and signatures."""
    _, ledger, _ = _stores()
    return {"chain_valid": ledger.verify_chain(), "events": ledger.count()}


if __name__ == "__main__":
    mcp.run()
