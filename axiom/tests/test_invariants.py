"""The law, executable: 20 invariant tests covering I1, I2, I3 and the
failure-mode matrix. No test here may ever be deleted, weakened,
skipped, or xfailed to get green.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from nacl.signing import SigningKey  # ty: ignore[unresolved-import]

from axiom.core.canonical import Unit
from axiom.core.contracts import PostconditionViolation, SpecError, parse_ears
from axiom.core.effects import UndeclaredEffectError
from axiom.core.ledger import Ledger
from axiom.core.registry import Registry, UnresolvedReferenceError
from axiom.core.verifier import Attestation, Rejection, Verifier
from axiom.forge.archive import MapElites
from axiom.forge.ratings import LOSS, WIN, Rating, update
from axiom.forge.tournament import Candidate, KillSwitch, Tournament
from axiom.memory.beliefs import (
    ENTRENCH_DEFAULT,
    ENTRENCH_OWNER,
    BeliefBase,
    OwnerRequired,
    SUPERSEDED,
)
from axiom.memory.fsrs_memory import (
    MemoryStore,
    TIER_SESSION,
    TIER_WORKING,
)
from axiom.memory.retrieval import (
    QUERY_CONCEPTUAL,
    QUERY_DECISION,
    QUERY_FACTUAL,
    QUERY_TEMPORAL,
    classify_query,
    weights_for,
)
from axiom.orchestrator.gates import (
    Change,
    GATES,
    RISK_HIGH,
    RISK_LOW,
    RISK_MED,
    classify,
    GATE_PROFILES,
)
from axiom.orchestrator.jobs import JobStore


# ---------------------------------------------------------------- fixtures

@pytest.fixture
def world():
    registry = Registry(":memory:")
    ledger = Ledger(":memory:")
    return registry, ledger, Verifier(registry, ledger)


def c2f_unit() -> Unit:
    """Celsius-to-Fahrenheit: the canonical first artifact."""
    return Unit(
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


# ------------------------------------------------------------ I1: identity

def test_name_change_preserves_hash():
    a = c2f_unit()
    b = Unit(**{**a.__dict__, "name": "renamed", "doc": "different doc"})  # ty: ignore[invalid-argument-type]
    assert a.unit_hash() == b.unit_hash()


def test_param_insertion_order_irrelevant():
    a = Unit(name="u", doc="", params={"a": "float", "b": "float"},
             intent="THE unit SHALL add a and b.",
             contracts=("result == a + b",),
             body=({"op": "add", "in": ["a", "b"], "into": "s"},
                   {"op": "return", "in": ["s"]}))
    b = Unit(name="u", doc="", params={"b": "float", "a": "float"},
             intent="THE unit SHALL add a and b.",
             contracts=("result == a + b",),
             body=({"op": "add", "in": ["a", "b"], "into": "s"},
                   {"op": "return", "in": ["s"]}))
    assert a.unit_hash() == b.unit_hash()


def test_registry_resolve_or_fail(world):
    registry, ledger, _ = world
    h = registry.register(c2f_unit(), ledger.signing_key)
    assert registry.resolve(h).unit_hash() == h
    with pytest.raises(UnresolvedReferenceError):
        registry.resolve("deadbeef" * 8)


def test_unresolved_reference_never_verifies(world):
    _, _, verifier = world
    unit = Unit(
        name="caller", doc="",
        params={"x": "float"},
        intent="THE caller SHALL call a ghost.",
        contracts=("result == x",),
        refs={"ghost": "deadbeef" * 8},
        body=({"op": "call", "ref": "ghost", "in": ["x"], "into": "y"},
              {"op": "return", "in": ["y"]}),
    )
    outcome = verifier.verify(unit)
    assert isinstance(outcome, Rejection)
    assert any("unresolved" in e for e in outcome.errors)


# ------------------------------------------------------- I2: verify gates

def test_no_spec_no_parse():
    with pytest.raises(SpecError):
        parse_ears("make it work somehow")
    assert parse_ears(
        "WHEN input arrives, THE unit SHALL respond.").pattern == "event"
    assert parse_ears("THE unit SHALL respond.").pattern == "ubiquitous"


def test_contradictory_contract_never_attests(world):
    _, _, verifier = world
    unit = Unit(
        name="liar", doc="",
        params={"x": "float"},
        intent="THE liar SHALL be impossible.",
        contracts=("result > 1.0", "result < 0.0"),
        body=({"op": "return", "in": ["x"]},),
    )
    outcome = verifier.verify(unit)
    assert isinstance(outcome, Rejection)
    assert any(e.get("error") == "contracts unsatisfiable" for e in outcome.errors)


def test_vacuous_spec_detected(world):
    _, _, verifier = world
    unit = Unit(
        name="vacuous", doc="",
        params={"x": "float"},
        intent="THE unit SHALL say nothing real.",
        contracts=("result == result",),
        body=({"op": "return", "in": ["x"]},),
    )
    outcome = verifier.verify(unit)
    assert isinstance(outcome, Rejection)
    assert any(e.get("error") == "vacuous clause" for e in outcome.errors)


def test_runtime_postcondition_blocks_bad_result(world):
    _, _, verifier = world
    # Statically clean (contract is satisfiable, non-vacuous) but the
    # body computes the wrong value: c + 32 instead of c*9/5 + 32.
    cheat = Unit(
        name="cheat", doc="",
        params={"c": "float"},
        intent="THE converter SHALL return c times 9 over 5 plus 32.",
        contracts=("result == c * 9.0 / 5.0 + 32.0",),
        body=({"op": "add", "in": ["c", 32.0], "into": "t"},
              {"op": "return", "in": ["t"]}),
    )
    outcome = verifier.verify(cheat)
    assert isinstance(outcome, Attestation)  # static checks can't see the lie
    with pytest.raises(PostconditionViolation):
        verifier.run(outcome.unit_hash, {"c": 100.0})
    violations = [
        e for e in verifier.ledger.events("process_event")
        if "violation" in e["payload"]
    ]
    assert violations, "violation must be ledgered"


def test_undeclared_effect_never_fires(world):
    _, _, verifier = world
    unit = Unit(
        name="writer", doc="",
        params={"x": "float"},
        intent="THE writer SHALL write to the network.",
        contracts=("result == x",),
        effects=("net",),
        body=({"op": "return", "in": ["x"]},),
    )
    outcome = verifier.verify(unit)
    assert isinstance(outcome, Attestation)
    # Granted capabilities do not include "net": execution must refuse.
    with pytest.raises(UndeclaredEffectError):
        verifier.run(outcome.unit_hash, {"x": 1.0}, granted=frozenset())
    # With the capability granted, it runs.
    assert verifier.run(outcome.unit_hash, {"x": 1.0},
                        granted=frozenset({"net"})) == 1.0


# ------------------------------------------------------------- I3: record

def test_ledger_tamper_detected():
    ledger = Ledger(":memory:")
    ledger.append("process_event", {"op": "a"})
    ledger.append("process_event", {"op": "b"})
    assert ledger.verify_chain() is True
    # Tamper with one byte of recorded history.
    ledger._db.execute(
        "UPDATE events SET payload = ? WHERE seq = 1", ('{"op": "A"}',)
    )
    ledger._db.commit()
    assert ledger.verify_chain() is False


def test_merkle_inclusion():
    ledger = Ledger(":memory:")
    hashes = [ledger.append("process_event", {"i": i}) for i in range(5)]
    cp = ledger.checkpoint()
    for h in hashes:
        proof = ledger.inclusion_proof(h, cp)
        assert Ledger.verify_inclusion(h, proof, cp["root"]) is True
    # A forged leaf does not verify.
    assert Ledger.verify_inclusion("00" * 32,
                                   ledger.inclusion_proof(hashes[0], cp),
                                   cp["root"]) is False


# ---------------------------------------------------------------- memory

def test_fsrs_promotion_and_lapse():
    store = MemoryStore(":memory:")
    mid = store.observe("the gateway runs on port 8088", source_grade="verified")
    assert store.get(mid)["tier"] == TIER_WORKING

    # Repeated verifier confirmations at spaced intervals grow stability.
    when = datetime.now(timezone.utc)
    tier = TIER_WORKING
    for _ in range(12):
        tier = store.on_verification(mid, passed=True, review_datetime=when)
        when += timedelta(days=14)
        if tier != TIER_WORKING:
            break
    assert tier in (TIER_SESSION, "durable")

    # One contradiction lapses the memory back to working.
    tier = store.on_verification(mid, passed=False, review_datetime=when)
    assert tier == TIER_WORKING


def test_belief_revision_entrenchment():
    base = BeliefBase(":memory:")
    weak = base.assert_belief("port is 8088", ENTRENCH_DEFAULT)
    new = base.revise("port is 9090", contradicts=weak)
    assert base.get(weak)["status"] == SUPERSEDED
    assert base.get(weak)["superseded_by"] == new
    assert [b["id"] for b in base.lineage(weak)] == [weak, new]

    owner = base.assert_belief("never deploy on fridays", ENTRENCH_OWNER)
    with pytest.raises(OwnerRequired):
        base.revise("deploy whenever", contradicts=owner)
    assert base.get(owner)["status"] == "ACTIVE"  # nothing changed


def test_retrieval_router():
    assert classify_query("when did we change the port?") == QUERY_TEMPORAL
    assert classify_query("why did we choose sqlite?") == QUERY_DECISION
    assert classify_query("explain how does the ledger work") == QUERY_CONCEPTUAL
    assert classify_query("what is the gateway port?") == QUERY_FACTUAL
    w = weights_for("when did we change the port?")
    assert w["rec"] > w["sim"] > w["conf"]
    from axiom.memory.retrieval import WEIGHT_PRESETS
    for preset in (QUERY_TEMPORAL, QUERY_FACTUAL, QUERY_CONCEPTUAL,
                   QUERY_DECISION):
        assert abs(sum(WEIGHT_PRESETS[preset].values()) - 1.0) < 1e-9


# ----------------------------------------------------------------- forge

def test_glicko2_matches_glickman_example():
    player = Rating(1500.0, 200.0, 0.06)
    new = update(player, [(1400.0, 30.0, WIN),
                          (1550.0, 100.0, LOSS),
                          (1700.0, 300.0, LOSS)])
    assert new.rating == pytest.approx(1464.05, abs=0.06)
    assert new.rd == pytest.approx(151.52, abs=0.05)
    assert new.vol == pytest.approx(0.06, abs=0.001)


def test_glicko2_rd_shrinks_with_games():
    player = Rating()
    assert player.rd == 350.0
    new = update(player, [(1500.0, 350.0, WIN)])
    assert new.rd < player.rd
    # And inflates (slightly) with inactivity.
    idle = update(new, [])
    assert idle.rd > new.rd


def test_map_elites_keeps_one_per_niche():
    archive = MapElites(bins_per_dim=4, dims=2)
    assert archive.add("a", fitness=1.0, descriptor=(0.1, 0.1)) is True
    assert archive.add("b", fitness=2.0, descriptor=(0.1, 0.1)) is True  # beats a
    assert archive.add("c", fitness=0.5, descriptor=(0.1, 0.1)) is False  # loses
    assert archive.add("d", fitness=0.1, descriptor=(0.9, 0.9)) is True  # new niche
    assert len(archive.elites()) == 2
    elite = archive.elite_at((0.1, 0.1))
    assert elite is not None and elite.candidate_id == "b"
    assert archive.coverage == pytest.approx(2 / 16)


def test_tournament_hard_gate_and_killswitch():
    ledger = Ledger(":memory:")
    t = Tournament(ledger)
    for cid in ("v1", "v2", "cheat"):
        t.add(Candidate(cid=cid))
    failed = t.gate(lambda c: c.cid != "cheat")
    assert failed == ["cheat"]
    assert t.candidates["cheat"].rating.rating == 0.0
    assert any(e["payload"]["cid"] == "cheat"
               for e in ledger.events("forge_gate_fail"))

    # Gate-failed candidates never duel.
    with pytest.raises(ValueError):
        t.duel("v1", "cheat", winner="cheat")

    t.duel("v1", "v2", winner="v2")
    assert t.champion().cid == "v2"

    # Kill-switch: inject an absurd rating so the next update jumps >400.
    t.candidates["v1"].rating = Rating(5000.0, 350.0, 0.06)
    with pytest.raises(KillSwitch):
        t.duel("v1", "v2", winner="v2")
    assert t.halted is True
    assert ledger.events("forge_kill_switch")


# ------------------------------------------------------------ orchestrator

def test_idempotent_job_runs_once():
    store = JobStore(":memory:")
    calls = []

    def work(inputs):
        calls.append(inputs)
        return {"sum": inputs["a"] + inputs["b"]}

    k1, r1, ran1 = store.run("add", {"a": 1, "b": 2}, work)
    k2, r2, ran2 = store.run("add", {"a": 1, "b": 2}, work)
    assert k1 == k2
    assert r1 == r2 == {"sum": 3}
    assert ran1 is True and ran2 is False
    assert len(calls) == 1
    assert store.status(k1) == "committed"
    # Different inputs are a different job.
    _, r3, ran3 = store.run("add", {"a": 2, "b": 2}, work)
    assert ran3 is True and r3 == {"sum": 4}


def test_blast_radius_profiles():
    low = Change("rename a local variable", loc=3, files=1)
    med = Change("new retrieval preset", loc=40, files=2, effects=("db.write",))
    high = Change("change default model routing", loc=200, files=8,
                  effects=("net", "db.write"), changes_default_behavior=True)
    assert classify(low) == RISK_LOW
    assert classify(med) == RISK_MED
    assert classify(high) == RISK_HIGH
    assert GATE_PROFILES[RISK_HIGH] == GATES  # HIGH runs all eight
    assert "OwnerApproval" not in GATE_PROFILES[RISK_LOW]
    assert "OwnerApproval" not in GATE_PROFILES[RISK_MED]
    assert set(GATE_PROFILES[RISK_LOW]) < set(GATE_PROFILES[RISK_MED]) \
        < set(GATE_PROFILES[RISK_HIGH])
