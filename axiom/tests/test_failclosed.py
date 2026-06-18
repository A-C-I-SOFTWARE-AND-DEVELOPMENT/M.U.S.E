"""Fail-closed contract policy: no z3, no attestation of contracts.

AXIOM never trusts what it cannot verify (invariant I2 — "verify before
attest"). When z3 is unavailable the verifier cannot prove a contract
satisfiable/consistent/non-vacuous, so a unit that DECLARES contracts is
rejected — never attested-with-a-warning. The legacy degraded path
(attest unproven contracts) survives only as an explicit, owner-gated
opt-in via ``AXIOM_ALLOW_UNVERIFIED_CONTRACTS=1``.

These tests force the degraded path by monkeypatching the optional z3
import to ``None`` (the same state a Termux/aarch64 device is in), so they
prove the policy regardless of whether z3 is installed on this machine.
"""

from __future__ import annotations

import pytest

from axiom.core import contracts as contracts_mod
from axiom.core.canonical import Unit
from axiom.core.ledger import Ledger
from axiom.core.registry import Registry
from axiom.core.verifier import Attestation, Rejection, Verifier


@pytest.fixture
def world():
    registry = Registry(":memory:")
    ledger = Ledger(":memory:")
    return registry, ledger, Verifier(registry, ledger)


@pytest.fixture
def no_z3(monkeypatch):
    """Simulate a platform with no z3 wheel (check_contracts goes degraded)."""
    monkeypatch.setattr(contracts_mod, "z3", None)
    # Ensure no stray opt-in leaks in from the ambient environment.
    monkeypatch.delenv("AXIOM_ALLOW_UNVERIFIED_CONTRACTS", raising=False)


_DOUBLE_BODY: tuple[dict, ...] = (
    {"op": "mul", "in": ["x", 2.0], "into": "y"},
    {"op": "return", "in": ["y"]},
)


def _unit_with_contracts(
    *,
    name: str = "double",
    contracts: tuple[str, ...] = ("result == x * 2.0",),
    body: tuple[dict, ...] = _DOUBLE_BODY,
) -> Unit:
    return Unit(
        name=name,
        doc="",
        params={"x": "float"},
        intent="THE unit SHALL return two times x.",
        contracts=contracts,
        body=body,
    )


def test_no_z3_rejects_unit_with_contracts(world, no_z3):
    """Default policy: unprovable contracts are refused, not waved through."""
    _, _, verifier = world
    outcome = verifier.verify(_unit_with_contracts())
    assert isinstance(outcome, Rejection)
    assert any(e.get("check") == "contracts:unverified" for e in outcome.errors)
    # The unsafe legacy behaviour (attest-with-warning) must NOT happen.
    assert not isinstance(outcome, Attestation)


def test_no_z3_unit_without_contracts_still_attests(world, no_z3):
    """Nothing to prove ⇒ nothing to fail closed on; the unit attests."""
    _, _, verifier = world
    unit = _unit_with_contracts(name="identity", contracts=())
    outcome = verifier.verify(unit)
    assert isinstance(outcome, Attestation)
    assert "contracts:degraded" in outcome.checks


def test_no_z3_opt_in_re_opens_degraded_path(world, no_z3, monkeypatch):
    """The owner-gated opt-in restores attest-with-warning, honestly labelled."""
    _, _, verifier = world
    monkeypatch.setenv("AXIOM_ALLOW_UNVERIFIED_CONTRACTS", "1")
    outcome = verifier.verify(_unit_with_contracts())
    assert isinstance(outcome, Attestation)
    assert "contracts:degraded" in outcome.checks
    assert any("not proven" in w for w in outcome.warnings)


def test_opt_in_cannot_launder_a_contradiction_at_runtime(world, no_z3, monkeypatch):
    """Even opted-in, the runtime postcondition still bites: a unit that
    lies about its result yields no result, only a violation event."""
    _, _, verifier = world
    monkeypatch.setenv("AXIOM_ALLOW_UNVERIFIED_CONTRACTS", "1")
    # Statically un-provable here (no z3), but the body returns x, not 2x.
    liar = _unit_with_contracts(
        name="liar",
        body=({"op": "return", "in": ["x"]},),
    )
    outcome = verifier.verify(liar)
    assert isinstance(outcome, Attestation)
    with pytest.raises(contracts_mod.PostconditionViolation):
        verifier.run(outcome.unit_hash, {"x": 21.0})


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " On "])
def test_opt_in_truthy_values(value):
    import os

    os.environ["AXIOM_ALLOW_UNVERIFIED_CONTRACTS"] = value
    try:
        assert contracts_mod.degraded_contracts_allowed() is True
    finally:
        del os.environ["AXIOM_ALLOW_UNVERIFIED_CONTRACTS"]


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "maybe"])
def test_opt_in_falsy_values(value):
    import os

    os.environ["AXIOM_ALLOW_UNVERIFIED_CONTRACTS"] = value
    try:
        assert contracts_mod.degraded_contracts_allowed() is False
    finally:
        del os.environ["AXIOM_ALLOW_UNVERIFIED_CONTRACTS"]
