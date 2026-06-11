"""Observatory recommendation engine + ``/v1/observatory/recommendations*``.

Covers the spec §6 hard rule (no percentage/CI on a card unless n >= 50 in
BOTH counterfactual arms — below that, the explicit collecting state with
zero projected numbers), deterministic seeded validation, staging into the
EXISTING owner-gated proposals queue with the 409 idempotency guard, the
dormant-collector response, and bearer auth on both routes.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

import gateway.cockpit.server as server_mod
from gateway.cockpit import handlers as h
from gateway.cockpit import handlers_observatory_recs as hrec
from gateway.cockpit import observatory_metrics as om
from gateway.cockpit import observatory_recommend as rec

TOKEN = "test-cockpit-token-123"

# Any numeric percentage ("38%", "-31.5 %", "+0.4%") anywhere in a card.
_PERCENT_RE = re.compile(r"[-+]?\d+(?:\.\d+)?\s*%")


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    om.reset_collector()
    yield tmp_path
    om.reset_collector()


def _seed_two_arms(collector, *, n_local: int, n_hosted: int, klass: str = "code") -> None:
    """Synthetic measured events through the collector's PUBLIC API only:
    a hot worker stage on the class, plus per-tier model-call latency arms
    (local clearly faster than hosted)."""
    for i in range(om.MIN_HEAT_N):
        collector.record_job_stage(
            f"jb{i}", "worker", task_class=klass, stage_latency_ms=90_000 + i
        )
    for i in range(n_local):
        collector.record_model_call(
            "local", "qwen-coder-local", 800 + (i % 7), task_class=klass
        )
    for i in range(n_hosted):
        collector.record_model_call(
            "hosted", "claude-hosted", 2400 + (i % 11), task_class=klass
        )


def _route_pin_card(cards: list[dict]) -> dict:
    matches = [c for c in cards if c["delta"]["kind"] == "route_pin"]
    assert matches, f"no route_pin card in {[c['id'] for c in cards]}"
    return matches[0]


# ── hard rule: no percentage below the evidence threshold ────────────────────


def test_no_percentage_anywhere_below_min_n(home: Path) -> None:
    collector = om.get_collector()
    _seed_two_arms(collector, n_local=12, n_hosted=60)
    card = _route_pin_card(rec.build_cards(collector, "1h"))
    assert card["state"] == "insufficient_evidence"
    validation = card["validation"]
    assert validation["method"] == "recorded-events-counterfactual"
    assert validation["median_delta_pct"] is None
    assert validation["ci95"] is None
    assert validation["n_candidate"] == 12
    assert validation["n_baseline"] == 60
    # The explicit collecting state, with the real n.
    assert "insufficient evidence (n=12) — collecting" in card["note"]
    assert "insufficient evidence (n=12)" in card["title"]
    # Zero projected numbers: no percentage appears ANYWHERE on the card.
    assert not _PERCENT_RE.search(json.dumps(card, default=str))


def test_validated_card_appears_at_min_n_with_deterministic_ci(home: Path) -> None:
    collector = om.get_collector()
    _seed_two_arms(collector, n_local=rec.MIN_EVIDENCE_N, n_hosted=rec.MIN_EVIDENCE_N)
    card = _route_pin_card(rec.build_cards(collector, "1h"))
    assert card["state"] == "validated"
    v = card["validation"]
    assert v["n_baseline"] == rec.MIN_EVIDENCE_N
    assert v["n_candidate"] == rec.MIN_EVIDENCE_N
    assert v["metric"] == "latency_ms"
    # local (~800ms) vs hosted (~2400ms): a large measured negative delta.
    assert v["median_delta_pct"] < -50
    lo, hi = v["ci95"]
    assert lo <= v["median_delta_pct"] <= hi
    # Card id is the deterministic hash of the delta.
    assert card["id"].startswith("rec-")
    # Evidence refs point at the measured heat key + window.
    assert "stage:worker:code" in card["evidence_refs"]
    assert any(ref.startswith("window:") for ref in card["evidence_refs"])
    # Deterministic: recomputing yields the identical validation (fixed seed).
    again = _route_pin_card(rec.build_cards(collector, "1h"))
    assert again["id"] == card["id"]
    assert again["validation"] == v


def test_model_suggestions_are_structure_only_and_never_carry_numbers(
    home: Path,
) -> None:
    collector = om.get_collector()
    collector.record_model_call("local", "m", 100, task_class="docs")  # not dormant
    suggestion = {
        "kind": "route_pin",
        "task_class": "docs",
        "target_tier": "local",
        "target_model": "qwen-coder-local",
        "baseline_tier": "hosted",
        "claimed_improvement_pct": 40,  # a model-invented number — must drop
        "projected_ci": [30, 50],
    }
    cards = rec.build_cards(collector, "1h", model_suggestions=[suggestion])
    card = _route_pin_card(cards)
    assert card["delta"]["source"] == "model"
    assert "claimed_improvement_pct" not in card["delta"]
    assert "projected_ci" not in card["delta"]
    assert card["state"] == "insufficient_evidence"
    assert not _PERCENT_RE.search(json.dumps(card, default=str))


def test_replay_spec_emits_rows_in_memory_only(home: Path) -> None:
    collector = om.get_collector()
    _seed_two_arms(collector, n_local=3, n_hosted=3)
    card = _route_pin_card(rec.build_cards(collector, "1h"))
    spec = rec.replay_spec(card, window="1h")
    assert spec["harness"] == "batch_runner.py"
    assert spec["card_id"] == card["id"]
    assert spec["row_count"] == len(spec["rows"]) > 0
    assert all("kind" in row and "ts" in row for row in spec["rows"])
    # Nothing written to disk: HERMES_HOME holds only the collector's ring.
    written = {p.name for p in home.rglob("*") if p.is_file()}
    assert all(name.startswith("events-") for name in written)


# ── staging: the existing owner-gated proposals queue ────────────────────────


def test_stage_writes_existing_proposals_queue_and_409s_on_repeat(home: Path) -> None:
    collector = om.get_collector()
    _seed_two_arms(collector, n_local=rec.MIN_EVIDENCE_N, n_hosted=rec.MIN_EVIDENCE_N)
    card = _route_pin_card(rec.build_cards(collector, "1h"))

    res = hrec.observatory_recommendation_stage(
        h.Request(
            method="POST",
            path="x",
            query={"window": "1h"},
            path_params={"id": card["id"]},
        )
    )
    assert res.status == 201
    assert res.payload["state"] == "staged"
    proposal_id = res.payload["proposal_id"]
    assert res.payload["approval_ref"] == f"/v1/cockpit/approvals/{proposal_id}"

    # The proposal landed in the EXISTING queue file with owner gating intact.
    queue = home / "jarvis_prime" / "proposals.jsonl"
    assert queue.is_file()
    proposals = [json.loads(line) for line in queue.read_text().splitlines()]
    assert len(proposals) == 1
    assert proposals[0]["kind"] == rec.PROPOSAL_KIND
    assert proposals[0]["target_path"] == card["id"]
    assert proposals[0]["requires_owner_approval"] is True
    assert proposals[0]["status"] == "proposed"
    # It surfaces on the existing approvals queue (owner-phrase Apply path).
    approvals = h.approvals_list(h.Request(method="GET", path="x"))
    assert [a["id"] for a in approvals.payload["approvals"]] == [proposal_id]

    # Idempotency guard: staging the same card again is a 409, not a dupe.
    res = hrec.observatory_recommendation_stage(
        h.Request(
            method="POST",
            path="x",
            query={"window": "1h"},
            path_params={"id": card["id"]},
        )
    )
    assert res.status == 409
    assert res.payload["error"] == "already_staged"
    assert res.payload["proposal_id"] == proposal_id
    assert len((home / "jarvis_prime" / "proposals.jsonl").read_text().splitlines()) == 1

    # GET now reports the card as staged with its proposal id.
    listed = hrec.observatory_recommendations(
        h.Request(method="GET", path="x", query={"window": "1h"})
    )
    staged = [c for c in listed.payload["cards"] if c["id"] == card["id"]]
    assert staged and staged[0]["state"] == "staged"
    assert staged[0]["proposal_id"] == proposal_id


def test_stage_unknown_id_404(home: Path) -> None:
    om.get_collector().record_queue_depth(1)  # not dormant
    res = hrec.observatory_recommendation_stage(
        h.Request(method="POST", path="x", path_params={"id": "rec-ffffffffffff"})
    )
    assert res.status == 404
    assert res.payload["error"] == "unknown_recommendation"


# ── GET: dormant collector + param validation ────────────────────────────────


def test_recommendations_dormant_when_collector_disabled(home: Path) -> None:
    res = hrec.observatory_recommendations(h.Request(method="GET", path="x"))
    assert res.status == 200
    assert res.payload["status"] == "dormant"
    assert res.payload["cards"] == []
    assert res.payload["v"] == 1


def test_recommendations_rejects_bad_window(home: Path) -> None:
    res = hrec.observatory_recommendations(
        h.Request(method="GET", path="x", query={"window": "2h"})
    )
    assert res.status == 400
    assert res.payload["error"] == "bad_request"


# ── routes: registration + bearer auth on the live server ───────────────────


@pytest.fixture()
def server(home: Path):
    srv = server_mod.serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/v1/observatory/recommendations"),
        ("POST", "/v1/observatory/recommendations/rec-123/stage"),
    ],
)
def test_recommendation_routes_require_bearer(server, method: str, path: str) -> None:
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}{path}", method=method)
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 401


def test_recommendations_over_http_with_bearer(server, home: Path) -> None:
    host, port = server.server_address
    req = urllib.request.Request(
        f"http://{host}:{port}/v1/observatory/recommendations", method="GET"
    )
    req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200
        body = json.loads(resp.read())
    assert body["v"] == 1
    assert body["status"] == "dormant"  # nothing recorded -> honestly dormant
    assert body["cards"] == []
