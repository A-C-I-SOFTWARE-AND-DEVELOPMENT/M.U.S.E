"""Phase 3 — the Forge becomes an engine: persistent ratings, real-unit
tournaments where the runtime gate (not judges) kills the cheat,
kill-switch alarms, and trajectory export for future distillation.
"""

from __future__ import annotations

import json

import pytest

from axiom.core.canonical import Unit
from axiom.core.ledger import Ledger
from axiom.core.registry import Registry
from axiom.core.verifier import Verifier
from axiom.forge.engine import ForgeEngine, RatingStore
from axiom.forge.ratings import DEFAULT_RD
from axiom.forge.tournament import KillSwitch


INTENT = "THE converter SHALL return c times 9 over 5 plus 32."
CONTRACT = "result == c * 9.0 / 5.0 + 32.0"


def variants() -> dict[str, Unit]:
    """Four generated variants of the same spec. One cheats."""
    def unit(name, body):
        return Unit(name=name, doc="", params={"c": "float"},
                    intent=INTENT, contracts=(CONTRACT,), body=body)
    return {
        "v_short": unit("v_short", (
            {"op": "mul", "in": ["c", 1.8], "into": "t"},
            {"op": "add", "in": ["t", 32.0], "into": "f"},
            {"op": "return", "in": ["f"]},
        )),
        "v_long": unit("v_long", (
            {"op": "mul", "in": ["c", 9.0], "into": "t1"},
            {"op": "div", "in": ["t1", 5.0], "into": "t2"},
            {"op": "add", "in": ["t2", 32.0], "into": "t3"},
            {"op": "return", "in": ["t3"]},
        )),
        "v_longer": unit("v_longer", (
            {"op": "mul", "in": ["c", 9.0], "into": "t1"},
            {"op": "div", "in": ["t1", 5.0], "into": "t2"},
            {"op": "add", "in": ["t2", 0.0], "into": "t2b"},
            {"op": "add", "in": ["t2b", 32.0], "into": "t3"},
            {"op": "return", "in": ["t3"]},
        )),
        # Wrong math: passes every static check, lies at runtime.
        "cheat": unit("cheat", (
            {"op": "add", "in": ["c", 32.0], "into": "t"},
            {"op": "return", "in": ["t"]},
        )),
    }


@pytest.fixture
def engine(tmp_path):
    registry = Registry(str(tmp_path / "registry.db"))
    ledger = Ledger(str(tmp_path / "ledger.db"))
    verifier = Verifier(registry, ledger)
    return ForgeEngine(
        verifier,
        ratings_path=str(tmp_path / "ratings.db"),
        data_dir=str(tmp_path / "data"),
    )


# ------------------------------------------------- 3.2 real-unit tournament

def test_cheat_dies_at_runtime_gate_not_judges(engine):
    report = engine.run_spec_tournament(variants(), probes=[{"c": 100.0}])
    assert "cheat" in report["gate_failed"]
    # The kill came from the runtime postcondition, not a judge score.
    fails = engine.verifier.ledger.events("forge_gate_fail")
    cheat_fail = next(e for e in fails if e["payload"]["cid"] == "cheat")
    assert "postcondition" in cheat_fail["payload"]["reason"]
    # Shorter verified unit wins.
    assert report["champion"] == "v_short"


def test_champion_lineage_queryable_from_ledger_alone(engine):
    engine.run_spec_tournament(variants(), probes=[{"c": 100.0}])
    ledger = engine.verifier.ledger
    champs = ledger.events("forge_champion")
    assert champs, "champion must be ledgered"
    champion = champs[-1]["payload"]["cid"]
    # Reconstruct the champion's path using nothing but ledger events.
    duels = [e["payload"] for e in ledger.events("forge_duel")
             if champion in (e["payload"]["a"], e["payload"]["b"])]
    assert duels, "champion must have earned its title in duels"
    assert all(d["winner"] == champion for d in duels
               if champion in (d["a"], d["b"]) and d["winner"] == champion)
    assert champs[-1]["payload"]["unit_hash"]  # lineage anchors to content


# --------------------------------------------------- 3.1 persistent ratings

def test_ratings_persist_across_two_runs(tmp_path):
    registry = Registry(str(tmp_path / "registry.db"))
    ledger = Ledger(str(tmp_path / "ledger.db"))
    verifier = Verifier(registry, ledger)
    e1 = ForgeEngine(verifier, ratings_path=str(tmp_path / "ratings.db"),
                     data_dir=str(tmp_path / "data"))
    e1.run_spec_tournament(variants(), probes=[{"c": 100.0}])
    after_run1 = e1.ratings.get("v_short").rating
    assert after_run1 != 1500.0  # it earned something

    # A second engine over the same store resumes, not restarts.
    e2 = ForgeEngine(verifier, ratings_path=str(tmp_path / "ratings.db"),
                     data_dir=str(tmp_path / "data"))
    assert e2.ratings.get("v_short").rating == pytest.approx(after_run1)
    e2.run_spec_tournament(variants(), probes=[{"c": 100.0}])
    assert e2.ratings.get("v_short").rating != pytest.approx(after_run1)


def test_idle_candidate_rd_inflates(tmp_path):
    store = RatingStore(str(tmp_path / "ratings.db"))
    from axiom.forge.ratings import Rating
    store.upsert("idler", Rating(1600.0, 80.0, 0.06))
    rd_before = store.get("idler").rd
    store.begin_period(active_cids=set())  # idler sat this one out
    assert store.get("idler").rd > rd_before
    # And never inflates past the default ceiling.
    for _ in range(500):
        store.begin_period(active_cids=set())
    assert store.get("idler").rd <= DEFAULT_RD + 1e-6


# ----------------------------------------------------------- 3.3 kill-switch

def test_kill_switch_halts_engine_and_alarms(engine):
    from axiom.forge.ratings import Rating
    # Seed the anomaly on a candidate that will LOSE its duels: an
    # ordinary opponent beating a 5000-rated player gains > 400 points.
    engine.ratings.upsert("v_longer", Rating(5000.0, 350.0, 0.06))
    with pytest.raises(KillSwitch):
        engine.run_spec_tournament(variants(), probes=[{"c": 100.0}])
    assert engine.verifier.ledger.events("forge_kill_switch")


# ------------------------------------------------------ 3.4 trajectory export

def test_trajectory_export(engine, tmp_path):
    engine.run_spec_tournament(variants(), probes=[{"c": 100.0}])
    traj = (tmp_path / "data" / "trajectories.jsonl").read_text().splitlines()
    negs = (tmp_path / "data" / "negatives.jsonl").read_text().splitlines()
    passed_cids = {json.loads(line)["cid"] for line in traj}
    failed_cids = {json.loads(line)["cid"] for line in negs}
    assert passed_cids == {"v_short", "v_long", "v_longer"}
    assert failed_cids == {"cheat"}
    # Every exported trajectory is anchored to a verified unit hash.
    for line in traj:
        rec = json.loads(line)
        assert rec["unit_hash"]
        assert rec["gate_passed"] is True
