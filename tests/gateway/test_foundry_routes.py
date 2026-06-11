"""The ``/v1/foundry/*`` route family (the Foundry loop spine, master plan
§4.7 / docs/synapse/design/09-foundry-spec.md).

Covers the honest-receipt rules: status stays ``pending`` with an empty
receipt until a real result is recorded; NO simulation numbers are ever
generated server-side; ship is refused (409) before validation and when
the numbers show no measured improvement; specs are allowlist-validated
against the vetted component library. One hermetic integration block
exercises bearer auth + the happy path over a live loopback server.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

import gateway.cockpit.server as server_mod
from gateway.cockpit import foundry_store as fs
from gateway.cockpit import handlers as h
from gateway.cockpit import handlers_game as hg

TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    yield tmp_path


def _spec(**overrides) -> dict:
    spec = {
        "name": "Bulwark-of-Threads",
        "domain": "security",
        "archetype": "INTERDICTOR",
        "stats": {"vitality": 80, "resilience": 64, "throughput": 30},
        "ability_ids": ["GA_Interrupt_T2", "GA_DamageShield_T2", "GA_Taunt_T1"],
        "personality_card": {"warmth": 0.7, "candor": 0.4, "patience": 0.8},
        "art_parts": ["SK_Quadruped_M", "P_Carapace_03", "PAL_Security_Cool", "FX_Shield_Hex"],
    }
    spec.update(overrides)
    return spec


def _observe(body: dict) -> h.JsonResponse:
    return hg.foundry_observe(h.Request(method="POST", path="x", body=body))


def _create(spec: dict, refs: list[str] | None = None) -> h.JsonResponse:
    return hg.foundry_candidate_create(
        h.Request(
            method="POST", path="x",
            body={"spec": spec, "source_pattern_refs": refs or []},
        )
    )


def _validate(cid: str, result: dict) -> h.JsonResponse:
    return hg.foundry_candidate_validation(
        h.Request(method="POST", path="x", body={"result": result}, path_params={"id": cid})
    )


def _ship(cid: str) -> h.JsonResponse:
    return hg.foundry_candidate_ship(
        h.Request(method="POST", path="x", path_params={"id": cid})
    )


def _real_result(**overrides) -> dict:
    result = {
        "status": "validated",
        "method": "ue-headless-sim",
        "n_simulations": 400,
        "baseline_survival": 0.31,
        "candidate_survival": 0.64,
        "receipt_text": (
            "In 400 simulations of your last 6 defeats at the Security "
            "Gauntlet, survival rose 31% -> 64%."
        ),
    }
    result.update(overrides)
    return result


# ── the loop: observe -> candidate -> validation -> ship ─────────────────────


def test_full_loop_happy_path(home: Path) -> None:
    # Observe a struggle pattern.
    res = _observe(
        {
            "save_slot": 1,
            "pattern": {"kind": "gauntlet_deaths", "context": {"gauntlet": "security", "wipes": 4}},
            "client": "ue",
        }
    )
    assert res.status == 201
    obs = res.payload["observation"]
    assert obs["id"].startswith("obs-")
    assert obs["pattern"]["kind"] == "gauntlet_deaths"
    assert obs["save_slot"] == 1 and obs["client"] == "ue" and obs["ts"]
    # Persisted to the JSONL log verbatim.
    assert fs.list_observations() == [obs]

    # Create a candidate sourced from that observation.
    res = _create(_spec(), refs=[obs["id"]])
    assert res.status == 201
    cand = res.payload
    assert cand["id"].startswith("fc-")
    assert cand["source_pattern_refs"] == [obs["id"]]
    # Honest pending state: no numbers, empty receipt, not shipped.
    assert cand["validation"] == {
        "status": "pending",
        "method": None,
        "n_simulations": 0,
        "baseline_survival": None,
        "candidate_survival": None,
        "receipt_text": "",
    }
    assert cand["shipped"] is False

    # Record the externally measured result (the honest receipt).
    res = _validate(cand["id"], _real_result())
    assert res.status == 200
    v = res.payload["validation"]
    assert v["status"] == "validated"
    assert v["n_simulations"] == 400
    assert v["baseline_survival"] == 0.31 and v["candidate_survival"] == 0.64
    assert "31% -> 64%" in v["receipt_text"]
    assert v["recorded_at"]

    # Ship: validated AND improving -> allowed.
    res = _ship(cand["id"])
    assert res.status == 200
    assert res.payload["shipped"] is True
    assert res.payload["shipped_at"]

    # status filter works.
    res = hg.foundry_candidates_list(
        h.Request(method="GET", path="x", query={"status": "validated"})
    )
    assert [c["id"] for c in res.payload["candidates"]] == [cand["id"]]
    res = hg.foundry_candidates_list(
        h.Request(method="GET", path="x", query={"status": "pending"})
    )
    assert res.payload["candidates"] == []


def test_ship_before_validation_409(home: Path) -> None:
    cand = _create(_spec()).payload
    res = _ship(cand["id"])
    assert res.status == 409
    assert res.payload["error"] == "ship_refused"
    assert "pending" in res.payload["detail"]
    # Still not shipped.
    assert fs.get_candidate(cand["id"])["shipped"] is False


def test_ship_with_non_improving_numbers_409(home: Path) -> None:
    cand = _create(_spec()).payload
    # A harness may honestly report status=validated with flat numbers;
    # the ship gate still requires candidate > baseline.
    _validate(
        cand["id"],
        _real_result(baseline_survival=0.5, candidate_survival=0.5),
    )
    res = _ship(cand["id"])
    assert res.status == 409
    assert "no measured improvement" in res.payload["detail"]

    # A rejected verdict can never ship either.
    _validate(cand["id"], _real_result(status="rejected"))
    res = _ship(cand["id"])
    assert res.status == 409
    assert "rejected" in res.payload["detail"]


def test_receipt_only_present_when_result_recorded(home: Path) -> None:
    cand = _create(_spec()).payload
    # Pending: empty receipt, null numbers — the server invented nothing.
    listed = hg.foundry_candidates_list(h.Request(method="GET", path="x")).payload
    pending = listed["candidates"][0]
    assert pending["validation"]["receipt_text"] == ""
    assert pending["validation"]["baseline_survival"] is None
    assert pending["validation"]["candidate_survival"] is None
    # After a real result is recorded, the receipt is exactly what was given.
    _validate(cand["id"], _real_result())
    after = fs.get_candidate(cand["id"])["validation"]
    assert after["receipt_text"].startswith("In 400 simulations")


# ── allowlist + shape rejections (400 with specific messages) ────────────────


@pytest.mark.parametrize(
    ("spec", "needle"),
    [
        (_spec(ability_ids=["GA_Interrupt_T2", "GA_Fireball_T9"]), "vetted GAS component"),
        (_spec(ability_ids=[]), "1-4 vetted ability ids"),
        (_spec(ability_ids=["GA_Interrupt_T2"] * 2), "duplicate ability"),
        (_spec(art_parts=["SK_Quadruped_M", "P_DragonWings_99"]), "part bank"),
        (_spec(domain="dragon"), "spec.domain"),
        (_spec(archetype="SUMMONER"), "closed library of 12"),
        (_spec(name=""), "spec.name"),
        (_spec(stats={"luck": 9}), "unknown stat"),
        (_spec(personality_card={"warmth": 1.5}), "[0, 1]"),
        (_spec(personality_card={"chaos": 0.5}), "five bounded axes"),
    ],
)
def test_candidate_spec_rejections(home: Path, spec: dict, needle: str) -> None:
    res = _create(spec)
    assert res.status == 400
    assert res.payload["error"] == "bad_request"
    assert needle in res.payload["detail"]
    # Nothing was stored.
    assert fs.list_candidates() == []


@pytest.mark.parametrize(
    ("body", "needle"),
    [
        ({"save_slot": 1, "pattern": {"kind": "rage_quit"}, "client": "ue"}, "pattern.kind"),
        ({"save_slot": 1, "pattern": {"kind": "custom"}, "client": "steam"}, "client"),
        ({"save_slot": 9, "pattern": {"kind": "custom"}, "client": "ue"}, "save_slot"),
        ({"save_slot": 1, "pattern": "died a lot", "client": "ue"}, "pattern"),
    ],
)
def test_observe_rejections(home: Path, body: dict, needle: str) -> None:
    res = _observe(body)
    assert res.status == 400
    assert needle in res.payload["detail"]
    assert fs.list_observations() == []


@pytest.mark.parametrize(
    ("result", "needle"),
    [
        (_real_result(status="great"), "result.status"),
        (_real_result(status="pending"), "result.status"),
        (_real_result(n_simulations=0), "positive integer"),
        (_real_result(baseline_survival=1.5), "[0, 1]"),
        (_real_result(candidate_survival=-0.1), "[0, 1]"),
        (_real_result(method=""), "result.method"),
    ],
)
def test_validation_result_rejections(home: Path, result: dict, needle: str) -> None:
    cand = _create(_spec()).payload
    res = _validate(cand["id"], result)
    assert res.status == 400
    assert needle in res.payload["detail"]
    # The candidate stays honestly pending.
    assert fs.get_candidate(cand["id"])["validation"]["status"] == "pending"


def test_unknown_candidate_404(home: Path) -> None:
    assert _validate("fc-nope", _real_result()).status == 404
    assert _ship("fc-nope").status == 404


def test_bad_status_filter_400(home: Path) -> None:
    res = hg.foundry_candidates_list(
        h.Request(method="GET", path="x", query={"status": "shiny"})
    )
    assert res.status == 400
    assert "status" in res.payload["detail"]


# ── integration: live server (auth + the loop over HTTP) ─────────────────────


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
        ("POST", "/v1/foundry/observe"),
        ("GET", "/v1/foundry/candidates"),
        ("POST", "/v1/foundry/candidates"),
        ("POST", "/v1/foundry/candidates/fc-1/validation"),
        ("POST", "/v1/foundry/candidates/fc-1/ship"),
    ],
)
def test_foundry_routes_require_bearer(server, method: str, path: str) -> None:
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}{path}", method=method)
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 401


def test_foundry_loop_over_http(server, home: Path) -> None:
    status, body = _http(
        server, "POST", "/v1/foundry/observe",
        {"save_slot": 2, "pattern": {"kind": "failed_parley", "context": {"domain": "security"}}, "client": "web"},
    )
    assert status == 201
    obs_id = body["observation"]["id"]

    status, cand = _http(
        server, "POST", "/v1/foundry/candidates",
        {"spec": _spec(), "source_pattern_refs": [obs_id]},
    )
    assert status == 201 and cand["validation"]["status"] == "pending"

    # Ship before validation -> 409 over the wire.
    with pytest.raises(urllib.error.HTTPError) as exc:
        _http(server, "POST", f"/v1/foundry/candidates/{cand['id']}/ship")
    assert exc.value.code == 409

    status, _ = _http(
        server, "POST", f"/v1/foundry/candidates/{cand['id']}/validation",
        {"result": _real_result()},
    )
    assert status == 200

    status, shipped = _http(server, "POST", f"/v1/foundry/candidates/{cand['id']}/ship")
    assert status == 200 and shipped["shipped"] is True

    status, listed = _http(server, "GET", "/v1/foundry/candidates?status=validated")
    assert status == 200 and len(listed["candidates"]) == 1
