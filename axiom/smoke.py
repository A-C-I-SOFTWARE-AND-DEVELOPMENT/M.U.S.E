"""AXIOM smoke test: the canonical first-artifact transcript.

Exercises the full organism end to end: attest, run, forge, memory,
ledger. Exits non-zero if any stage misbehaves.
"""

from __future__ import annotations

from axiom.core.canonical import Unit
from axiom.core.ledger import Ledger
from axiom.core.registry import Registry
from axiom.core.verifier import Attestation, Verifier
from axiom.forge.ratings import Rating
from axiom.forge.tournament import Candidate, Tournament
from axiom.memory.fsrs_memory import MemoryStore


def main() -> None:
    registry = Registry(":memory:")
    ledger = Ledger(":memory:")
    verifier = Verifier(registry, ledger)

    # [1] Attest the canonical first artifact.
    c2f = Unit(
        name="c_to_f",
        doc="Convert Celsius to Fahrenheit.",
        params={"c": "float"},
        intent="THE converter SHALL return c times 9 over 5 plus 32.",
        contracts=("result == c * 9.0 / 5.0 + 32.0",),
        body=(
            {"op": "mul", "in": ["c", 9.0], "into": "t1"},
            {"op": "div", "in": ["t1", 5.0], "into": "t2"},
            {"op": "add", "in": ["t2", 32.0], "into": "t3"},
            {"op": "return", "in": ["t3"]},
        ),
    )
    att = verifier.verify(c2f)
    assert isinstance(att, Attestation), att
    print(f"[1] attested  unit={att.unit_hash[:12]}…  checks={list(att.checks)}")

    # [2] Run it with postconditions enforced on the concrete value.
    result = verifier.run(att.unit_hash, {"c": 100.0})
    print(f"[2] run(100C) = {result}F")
    assert result == 212.0

    # [3] A small forge round: hard gate + duels.
    t = Tournament(ledger)
    for cid in ("v1", "v2", "cheat"):
        t.add(Candidate(cid=cid))
    gate_failed = t.gate(lambda c: c.cid != "cheat")
    t.duel("v1", "v2", winner="v2")
    t.duel("v1", "v2", winner="v2")
    champ = t.champion()
    print(f"[3] forge: champion={champ.cid} ({champ.rating.rating:.0f}), "
          f"gate-failed={gate_failed} (rating 0)")
    assert champ.cid == "v2"
    assert t.candidates["cheat"].rating.rating == 0.0

    # [4] Memory: observe one fact; fresh memories are fully retrievable.
    mem = MemoryStore(":memory:")
    mid = mem.observe("water boils at 100C at sea level", source_grade="verified")
    m = mem.get(mid)
    print(f"[4] memory {mid} tier={m['tier']}  R={m['retrievability']:.2f}")

    # [5] The court of record.
    print(f"[5] ledger: {ledger.count()} events, chain_valid={ledger.verify_chain()}")
    assert ledger.verify_chain() is True


if __name__ == "__main__":
    main()
