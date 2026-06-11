"""Phase 1 — kernel hardening: richer body ops, cycle guard,
deprecation, ledger compaction. Every test here defends an invariant;
none may be weakened to get green.
"""

from __future__ import annotations

import json

import pytest

from axiom.core.canonical import Unit
from axiom.core.ledger import Ledger
from axiom.core.registry import Registry
from axiom.core.verifier import Attestation, Rejection, Verifier


@pytest.fixture
def world():
    registry = Registry(":memory:")
    ledger = Ledger(":memory:")
    return registry, ledger, Verifier(registry, ledger)


# ------------------------------------------------------------- 1.1 new ops

def _attest_and_run(verifier, unit, args):
    outcome = verifier.verify(unit)
    assert isinstance(outcome, Attestation), getattr(outcome, "errors", None)
    return verifier.run(outcome.unit_hash, args)


def test_op_min_max(world):
    _, _, verifier = world
    smaller = Unit(
        name="smaller", doc="",
        params={"a": "float", "b": "float"},
        intent="THE unit SHALL return the smaller of a and b.",
        contracts=("(result == a or result == b) and result <= a and result <= b",),
        body=({"op": "min", "in": ["a", "b"], "into": "m"},
              {"op": "return", "in": ["m"]}),
    )
    assert _attest_and_run(verifier, smaller, {"a": 3.0, "b": 7.0}) == 3.0

    larger = Unit(
        name="larger", doc="",
        params={"a": "float", "b": "float"},
        intent="THE unit SHALL return the larger of a and b.",
        contracts=("(result == a or result == b) and result >= a and result >= b",),
        body=({"op": "max", "in": ["a", "b"], "into": "m"},
              {"op": "return", "in": ["m"]}),
    )
    assert _attest_and_run(verifier, larger, {"a": 3.0, "b": 7.0}) == 7.0


def test_op_abs(world):
    _, _, verifier = world
    magnitude = Unit(
        name="magnitude", doc="",
        params={"x": "float"},
        intent="THE unit SHALL return the magnitude of x.",
        contracts=("result >= 0.0 and (result == x or result == -x)",),
        body=({"op": "abs", "in": ["x"], "into": "m"},
              {"op": "return", "in": ["m"]}),
    )
    assert _attest_and_run(verifier, magnitude, {"x": -4.5}) == 4.5
    assert _attest_and_run(verifier, magnitude, {"x": 4.5}) == 4.5


def test_op_if_select_and_comparisons(world):
    _, _, verifier = world
    # clamp_low(x, lo): if x < lo then lo else x — built from lt + if.
    clamp = Unit(
        name="clamp_low", doc="",
        params={"lo": "float", "x": "float"},
        intent="THE unit SHALL return x clamped below by lo.",
        contracts=("result >= lo", "result == x or result == lo"),
        body=(
            {"op": "lt", "in": ["x", "lo"], "into": "below"},
            {"op": "if", "in": ["below", "lo", "x"], "into": "out"},
            {"op": "return", "in": ["out"]},
        ),
    )
    assert _attest_and_run(verifier, clamp, {"lo": 0.0, "x": -5.0}) == 0.0
    assert _attest_and_run(verifier, clamp, {"lo": 0.0, "x": 5.0}) == 5.0


def test_op_eq_produces_bool(world):
    registry, _, verifier = world
    # eq feeds if: same(x, y) returns 1.0 when equal else 0.0.
    same = Unit(
        name="same", doc="",
        params={"x": "float", "y": "float"},
        intent="THE unit SHALL return one when x equals y and zero otherwise.",
        contracts=("result == 0.0 or result == 1.0",),
        body=(
            {"op": "eq", "in": ["x", "y"], "into": "e"},
            {"op": "if", "in": ["e", 1.0, 0.0], "into": "out"},
            {"op": "return", "in": ["out"]},
        ),
    )
    assert _attest_and_run(verifier, same, {"x": 2.0, "y": 2.0}) == 1.0
    assert _attest_and_run(verifier, same, {"x": 2.0, "y": 3.0}) == 0.0


# --------------------------------------------------------- 1.2 cycle guard

def test_cycle_rejected_at_verify(world):
    registry, ledger, verifier = world
    # Content addressing makes honest cycles unconstructible (a unit's
    # hash depends on its refs), so we simulate a corrupted registry:
    # register A and B, then tamper A's stored form to ref B.
    a = Unit(name="a", doc="", params={"x": "float"},
             intent="THE unit SHALL return x.",
             contracts=("result == x",),
             body=({"op": "return", "in": ["x"]},))
    ha = registry.register(a, ledger.signing_key)
    b = Unit(name="b", doc="", params={"x": "float"},
             intent="THE unit SHALL return x via a.",
             contracts=("result == x",),
             refs={"a": ha},
             body=({"op": "call", "ref": "a", "in": ["x"], "into": "y"},
                   {"op": "return", "in": ["y"]}))
    hb = registry.register(b, ledger.signing_key)

    form_a = a.full_form()
    form_a["refs"] = {"b": hb}  # forge the cycle a -> b -> a
    registry._db.execute(
        "UPDATE units SET form = ? WHERE unit_hash = ?",
        (json.dumps(form_a), ha),
    )
    registry._db.commit()

    caller = Unit(name="caller", doc="", params={"x": "float"},
                  intent="THE unit SHALL call b.",
                  contracts=("result == x",),
                  refs={"b": hb},
                  body=({"op": "call", "ref": "b", "in": ["x"], "into": "y"},
                        {"op": "return", "in": ["y"]}))
    outcome = verifier.verify(caller)
    assert isinstance(outcome, Rejection)
    assert any("cycle" in str(e).lower() for e in outcome.errors)


# --------------------------------------------------------- 1.3 deprecation

def test_deprecation_old_hash_resolves_and_verifier_warns(world):
    registry, ledger, verifier = world
    v1 = Unit(name="conv_v1", doc="", params={"c": "float"},
              intent="THE converter SHALL return c plus 273.15.",
              contracts=("result == c + 273.15",),
              body=({"op": "add", "in": ["c", 273.15], "into": "k"},
                    {"op": "return", "in": ["k"]}))
    v2 = Unit(name="conv_v2", doc="better docs same math",
              params={"c": "float"},
              intent="THE converter SHALL return c plus 273.15 exactly.",
              contracts=("result == c + 273.15",),
              body=({"op": "add", "in": ["c", 273.15], "into": "k"},
                    {"op": "return", "in": ["k"]}))
    h1 = registry.register(v1, ledger.signing_key)
    h2 = registry.register(v2, ledger.signing_key)
    registry.deprecate(h1, h2)

    # History immutable: the old hash still resolves.
    assert registry.resolve(h1).unit_hash() == h1
    assert registry.deprecated_by(h1) == h2

    # A unit referencing the deprecated hash attests WITH a warning.
    caller = Unit(name="caller", doc="", params={"c": "float"},
                  intent="THE caller SHALL convert via v1.",
                  contracts=("result == c + 273.15",),
                  refs={"conv": h1},
                  body=({"op": "call", "ref": "conv", "in": ["c"], "into": "k"},
                        {"op": "return", "in": ["k"]}))
    outcome = verifier.verify(caller)
    assert isinstance(outcome, Attestation)
    assert any("deprecated" in w for w in outcome.warnings)


# ----------------------------------------------------- 1.4 ledger compaction

def test_ledger_compaction_preserves_root_and_chain():
    ledger = Ledger(":memory:")
    hashes = [ledger.append("process_event", {"i": i}) for i in range(6)]
    cp = ledger.checkpoint()

    ledger.compact(cp)

    # Chain still verifies: links + signatures hold even though
    # compacted payloads are summarized.
    assert ledger.verify_chain() is True
    # Inclusion proofs against the stored root still verify.
    for h in hashes:
        proof = ledger.inclusion_proof(h, cp)
        assert Ledger.verify_inclusion(h, proof, cp["root"]) is True
    # Tampering with a compacted event's stored hash is still detected.
    ledger._db.execute(
        "UPDATE events SET hash = ? WHERE seq = 1", ("00" * 32,)
    )
    ledger._db.commit()
    assert ledger.verify_chain() is False


def test_compaction_never_touches_post_checkpoint_events():
    ledger = Ledger(":memory:")
    for i in range(3):
        ledger.append("process_event", {"i": i})
    cp = ledger.checkpoint()
    after = ledger.append("process_event", {"i": 99})
    ledger.compact(cp)
    events = {e["hash"]: e for e in ledger.events()}
    assert events[after]["payload"] == {"i": 99}  # untouched
    assert ledger.verify_chain() is True
