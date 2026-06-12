"""The ``/v1/game/*`` route family (SYNAPSE game substrate, master plan §4).

Unit tests exercise the handlers directly (isolated HERMES_HOME); one
hermetic integration block exercises bearer auth + a CRUD round-trip over a
live loopback server, mirroring ``test_cockpit_observatory.py``. Also
covers the additive Den fields on ``room_store`` items (design doc 08 §6.4
caps) since the game save's den section references room item ids.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

import gateway.cockpit.server as server_mod
from gateway.cockpit import game_store as gs
from gateway.cockpit import handlers as h
from gateway.cockpit import handlers_game as hg
from gateway.cockpit import room_store as rs

TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    yield tmp_path


def _post(slot: str, body: dict) -> h.JsonResponse:
    return hg.game_save_write(
        h.Request(method="POST", path="x", body=body, path_params={"slot": slot})
    )


def _get(slot: str) -> h.JsonResponse:
    return hg.game_save_get(
        h.Request(method="GET", path="x", path_params={"slot": slot})
    )


def _full_save_body() -> dict:
    return {
        "muse": {
            "name": "Lumen",
            "frame": "drifting",
            "material": "porcelain",
            "finish": "matte",
            "face": "crescent",
            "voice": "soft_static",
            "answers": [0, 1, 2, 0, 1],
        },
        "network": {
            "slots": {"core-1": "axiom", "core-2": "contrarian", "inner-1": "cipher"},
            "edges": [
                {"a": "core-1", "b": "core-2", "cost": 30},
                {"a": "core-2", "b": "inner-1", "cost": 30},
            ],
            "periphery": ["empath"],
        },
        "roster": [
            {"agent_id": "axiom", "resonance_level": 12, "promoted": False},
            {"agent_id": "contrarian", "resonance_level": 30, "promoted": True},
            {"agent_id": "cipher", "resonance_level": 8},
            {"agent_id": "empath", "resonance_level": 1},
        ],
        "den": {"stage": 2, "items": ["room_abc12345"]},
        "progress": {
            "zones_unlocked": ["the_stacks", "the_foundry"],
            "gauntlets_cleared": ["planning", "test"],
            "campaign_flags": {"met_the_deadlock": True},
        },
        "settings": {"difficulty": "standard"},
    }


# ── slot CRUD round-trip ─────────────────────────────────────────────────────


def test_slot_crud_round_trip(home: Path) -> None:
    # Empty slot: list shows 3 empty slots, GET 404s, DELETE 404s.
    res = hg.game_saves_list(h.Request(method="GET", path="x"))
    assert res.status == 200
    assert res.payload["max_slots"] == gs.MAX_SLOTS
    assert [s["exists"] for s in res.payload["slots"]] == [False, False, False]
    assert _get("1").status == 404
    assert _get("1").payload["error"] == "empty_slot"

    # Create: 201, full document persisted with version + timestamps.
    res = _post("1", _full_save_body())
    assert res.status == 201
    save = res.payload
    assert save["v"] == gs.SAVE_VERSION
    assert save["slot"] == 1
    assert save["created_at"] and save["updated_at"]
    assert save["muse"]["name"] == "Lumen"
    assert save["network"]["slots"]["core-1"] == "axiom"

    # Round-trip: GET returns what was written.
    res = _get("1")
    assert res.status == 200
    assert res.payload["roster"][1]["promoted"] is True
    assert res.payload["den"]["stage"] == 2

    # Summary reflects the save without shipping the full document.
    summary = hg.game_saves_list(h.Request(method="GET", path="x")).payload["slots"][0]
    assert summary == {
        "slot": 1,
        "exists": True,
        "created_at": save["created_at"],
        "updated_at": save["updated_at"],
        "muse_name": "Lumen",
        "roster_count": 4,
        "den_stage": 2,
        "gauntlets_cleared": 2,
    }

    # Delete: 200 then 404 on the second delete and on GET.
    res = hg.game_save_delete(
        h.Request(method="DELETE", path="x", path_params={"slot": "1"})
    )
    assert res.status == 200 and res.payload["deleted"] is True
    res = hg.game_save_delete(
        h.Request(method="DELETE", path="x", path_params={"slot": "1"})
    )
    assert res.status == 404
    assert _get("1").status == 404


def test_partial_update_merges_sections(home: Path) -> None:
    assert _post("2", _full_save_body()).status == 201
    # Update ONLY the network section; every other section must be untouched.
    res = _post(
        "2",
        {
            "network": {
                "slots": {"core-1": "axiom", "core-2": "empath"},
                "edges": [{"a": "core-1", "b": "core-2", "cost": 30}],
            }
        },
    )
    assert res.status == 200  # update, not create
    save = _get("2").payload
    assert save["network"]["slots"] == {"core-1": "axiom", "core-2": "empath"}
    assert save["muse"]["name"] == "Lumen"  # untouched
    assert save["den"]["stage"] == 2  # untouched
    assert save["settings"] == {"difficulty": "standard"}  # untouched


def test_rejected_write_changes_nothing(home: Path) -> None:
    _post("1", _full_save_body())
    before = _get("1").payload
    res = _post("1", {"den": {"stage": 4}, "settings": {"x": 1}})
    assert res.status == 400
    assert _get("1").payload == before  # validate-all-then-write


def test_synergy_summary_is_server_computed(home: Path) -> None:
    body = {
        "network": {
            "slots": {
                "core-1": "axiom",       # architecture
                "core-2": "contrarian",  # qa_test (ring-adjacent to architecture)
                "core-3": "nitpick",     # qa_test (same domain as contrarian)
                "inner-1": "empath",     # behavior_psych (ring-opposed to architecture)
            },
            "edges": [
                {"a": "core-1", "b": "core-2", "cost": 30},  # pipeline
                {"a": "core-2", "b": "core-3", "cost": 30},  # depth
                {"a": "core-1", "b": "inner-1", "cost": 30},  # tension
            ],
            # Client-supplied summaries are ignored — recomputed server-side.
            "synergy_summary": {"depth": 99},
        }
    }
    save = _post("3", body).payload
    assert save["network"]["synergy_summary"] == {
        "depth": 1,
        "pipeline": 1,
        "tension": 1,
        "integrity": 0,
        "edges": 3,
        "thread_spent": 90,
    }


# ── every validation constraint -> 400 with a specific message ───────────────


@pytest.mark.parametrize("slot", ["0", "4", "abc", ""])
def test_bad_slot_number_400(home: Path, slot: str) -> None:
    res = _get(slot)
    assert res.status == 400
    assert "slot" in res.payload["detail"]
    assert _post(slot, {"settings": {}}).status == 400


@pytest.mark.parametrize(
    ("body", "needle"),
    [
        # body / section shape
        ({}, "at least one section"),
        ({"loadout": {}}, "unknown section"),
        # network constraints (design doc 07)
        ({"network": {"slots": {"hub-1": "axiom"}}}, "unknown slot id"),
        ({"network": {"slots": {"core-1": "pikachu"}}}, "unknown agent id"),
        (
            {"network": {"slots": {"core-1": "axiom", "core-2": "axiom"}}},
            "more than one slot",
        ),
        (
            {
                "network": {
                    "slots": {"core-1": "axiom", "core-2": "empath"},
                    "edges": [{"a": "core-1", "b": "core-2", "cost": 15}],
                }
            },
            "10/20/30",
        ),
        (
            {
                "network": {
                    "slots": {"core-1": "axiom", "core-2": "empath"},
                    "edges": [{"a": "core-1", "b": "core-2", "cost": 10}],
                }
            },
            "core–core edge costs 30",
        ),
        (
            {
                "network": {
                    "slots": {"core-1": "axiom", "outer-1": "empath"},
                    "edges": [{"a": "core-1", "b": "outer-1", "cost": 30}],
                }
            },
            "never adjacent",
        ),
        (
            {
                "network": {
                    "slots": {"core-1": "axiom"},
                    "edges": [{"a": "core-1", "b": "core-2", "cost": 30}],
                }
            },
            "unoccupied",
        ),
        (
            {
                "network": {
                    "slots": {"core-1": "axiom"},
                    "edges": [{"a": "core-1", "b": "core-1", "cost": 30}],
                }
            },
            "itself",
        ),
        # roster constraints (07 §3: resonance 1-50)
        ({"roster": [{"agent_id": "axiom", "resonance_level": 0}]}, "1-50"),
        ({"roster": [{"agent_id": "axiom", "resonance_level": 51}]}, "1-50"),
        ({"roster": [{"agent_id": "axiom", "resonance_level": 5.5}]}, "1-50"),
        ({"roster": [{"agent_id": "mewtwo"}]}, "unknown agent id"),
        (
            {"roster": [{"agent_id": "axiom"}, {"agent_id": "axiom"}]},
            "duplicate agent",
        ),
        ({"roster": [{"agent_id": "axiom", "promoted": "yes"}]}, "boolean"),
        # den constraints (08 §7: stages 1-3)
        ({"den": {"stage": 4}}, "1, 2 or 3"),
        ({"den": {"stage": 0}}, "1, 2 or 3"),
        ({"den": {"stage": 1, "items": [42]}}, "room item id"),
        # progress constraints (master plan §4.9: 8 gauntlets, 5 zones)
        ({"progress": {"gauntlets_cleared": ["speedrun"]}}, "unknown gauntlet"),
        ({"progress": {"gauntlets_cleared": ["test", "test"]}}, "duplicate"),
        ({"progress": {"zones_unlocked": ["route-1"]}}, "unknown zone"),
        # muse constraints (08 §3.1)
        ({"muse": {"name": "x"}}, "2-16"),
        ({"muse": {"name": "x" * 17}}, "2-16"),
        ({"muse": {"voice": "screamo"}}, "muse.voice"),
        ({"muse": {"frame": "kaiju"}}, "muse.frame"),
        ({"muse": {"answers": [0, 1, 2, 0, 1, 2]}}, "at most 5"),
        # section type errors
        ({"settings": "loud"}, "must be an object"),
        ({"roster": {"axiom": 1}}, "must be a list"),
    ],
)
def test_constraint_violations_rejected_400(home: Path, body: dict, needle: str) -> None:
    res = _post("1", body)
    assert res.status == 400, f"expected 400 for {body!r}, got {res.status}"
    assert res.payload["error"] == "bad_request"
    assert needle in res.payload["detail"], (
        f"{needle!r} not in {res.payload['detail']!r}"
    )
    # Rejected create leaves the slot empty.
    assert _get("1").status == 404


def test_forged_agent_ids_are_wireable(home: Path) -> None:
    # Foundry rares wire into the network like any agent (09 §6).
    res = _post(
        "1",
        {
            "network": {"slots": {"core-1": "forged-bulwark01"}},
            "roster": [{"agent_id": "forged-bulwark01", "resonance_level": 7}],
        },
    )
    assert res.status == 201
    # Unknown domain -> classified honestly as integrity if wired.
    assert res.payload["network"]["synergy_summary"]["edges"] == 0


# ── design endpoint ──────────────────────────────────────────────────────────


def test_design_endpoint_shape(home: Path) -> None:
    res = hg.game_design(h.Request(method="GET", path="x"))
    assert res.status == 200
    design = res.payload
    assert len(design["lattice"]["slots"]) == 21
    assert design["lattice"]["tiers"] == {"core": 3, "inner": 6, "outer": 12}
    assert design["lattice"]["thread_costs"] == {
        "core-core": 30,
        "core-inner": 30,
        "inner-inner": 20,
        "inner-outer": 20,
        "outer-outer": 10,
    }
    assert len(design["domains"]) == 8
    assert len(design["agents"]) == 24
    assert design["agents"]["axiom"] == "architecture"
    assert design["gauntlets"] == [
        "planning", "build", "review", "test",
        "security", "release", "owner_approval", "rollback",
    ]
    assert design["resonance"] == {"min": 1, "max": 50}
    assert design["den"]["buff_pct_cap"] == 5
    assert design["max_save_slots"] == 3
    # Constants cite the design docs they were sourced from.
    assert design["sources"]["lattice"].endswith("07-progression-neural-network.md")
    assert design["sources"]["master_plan"].startswith("docs/plans/")


# ── room_store: additive Den fields (08 §6.4 caps) ───────────────────────────


def test_room_store_den_fields(home: Path) -> None:
    item = rs.generate_item("a lumen sprout", generator=lambda _t: b"\x89PNG")
    # New items carry NO den keys — manifests stay unchanged until opt-in.
    raw = json.loads((rs.room_dir() / "manifest.json").read_text(encoding="utf-8"))
    assert "den_stage" not in raw[0] and "buff" not in raw[0]

    assert rs.set_den_fields(item["id"], den_stage=2, buff={"stat": "resonance_gain", "pct": 2}) is True
    stored = rs.list_items()[0]
    assert stored["den_stage"] == 2
    assert stored["buff"] == {"stat": "resonance_gain", "pct": 2.0}

    assert rs.set_den_fields("room_nope", den_stage=1) is False
    with pytest.raises(ValueError, match="den_stage"):
        rs.set_den_fields(item["id"], den_stage=4)
    with pytest.raises(ValueError, match=r"\+5%"):
        rs.set_den_fields(item["id"], buff={"stat": "crit", "pct": 6})
    with pytest.raises(ValueError, match="buff.stat"):
        rs.set_den_fields(item["id"], buff={"stat": "", "pct": 1})
    with pytest.raises(ValueError, match="den_stage and/or buff"):
        rs.set_den_fields(item["id"])


# ── integration: live server (auth + round-trip) ─────────────────────────────


@pytest.fixture()
def server(home: Path):
    srv = server_mod.serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _http(server, method: str, path: str, body: dict | None = None, *, token: str | None = TOKEN):
    host, port = server.server_address
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"http://{host}:{port}{path}", data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/v1/game/design"),
        ("GET", "/v1/game/saves"),
        ("GET", "/v1/game/saves/1"),
        ("POST", "/v1/game/saves/1"),
        ("DELETE", "/v1/game/saves/1"),
    ],
)
def test_game_routes_require_bearer(server, method: str, path: str) -> None:
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}{path}", method=method)
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 401


def test_game_crud_over_http(server, home: Path) -> None:
    status, body = _http(server, "GET", "/v1/game/design")
    assert status == 200 and len(body["lattice"]["slots"]) == 21

    status, body = _http(server, "POST", "/v1/game/saves/1", _full_save_body())
    assert status == 201 and body["slot"] == 1

    status, body = _http(server, "GET", "/v1/game/saves/1")
    assert status == 200 and body["muse"]["name"] == "Lumen"

    status, body = _http(server, "DELETE", "/v1/game/saves/1")
    assert status == 200 and body["deleted"] is True

    with pytest.raises(urllib.error.HTTPError) as exc:
        _http(server, "GET", "/v1/game/saves/1")
    assert exc.value.code == 404
